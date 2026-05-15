"""Flan-T5 reachability reasoner.

Stage 3 of the pipeline. Given:
  - the CVE description and known vulnerable symbol
  - a static-analysis verdict and (optionally) the call-path code snippets
the reasoner asks Flan-T5 whether the vulnerable code path is genuinely
exercised in the consuming application. This adds semantic context that
pure call-graph reachability misses (dangerous-parameter flow, deprecated
APIs, authenticated-only paths, etc.).

The reasoner gracefully degrades:
  - If `transformers` isn't installed (e.g. very minimal CI), it falls back
    to a rule-based heuristic that mirrors the LLM verdict at lower accuracy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import logging

logger = logging.getLogger(__name__)


@dataclass
class ReachabilityVerdict:
    reachable: bool
    confidence: float  # 0.0 .. 1.0
    rationale: str
    static_paths: list[list[str]]


_PROMPT_TEMPLATE = """You are a security analyst reasoning about whether a vulnerability is exploitable in a given application.

CVE summary: {cve_summary}
Vulnerable function/symbol: {symbol}
Static call-graph analysis: {static_status}
Static paths found: {static_paths}

Relevant code from the application's call chain:
---
{code_excerpt}
---

Question: Is the vulnerable function actually reachable AND invoked with attacker-influencable
arguments in this application? Answer "YES" or "NO" and give a one-sentence reason.
"""


class ReachabilityReasoner:
    """Wraps Flan-T5 (or any seq2seq) for reachability reasoning.

    Loaded lazily so that test/CI doesn't need to download 780M of weights.
    """

    def __init__(
        self,
        model_name: str = "google/flan-t5-large",
        device: Optional[str] = None,
        max_new_tokens: int = 128,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.max_new_tokens = max_new_tokens
        self._model = None
        self._tokenizer = None

    def _ensure_loaded(self) -> bool:
        if self._model is not None:
            return True
        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError:
            logger.warning("transformers/torch unavailable — using rule-based fallback")
            return False
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = self._model.to(self.device).eval()
        return True

    def reason(
        self,
        cve_summary: str,
        symbol: str,
        static_paths: list[list[str]],
        code_excerpt: str = "",
    ) -> ReachabilityVerdict:
        static_reachable = bool(static_paths)
        static_status = "REACHABLE" if static_reachable else "NOT REACHABLE"

        if not self._ensure_loaded():
            return self._rule_based(cve_summary, symbol, static_paths, code_excerpt)

        prompt = _PROMPT_TEMPLATE.format(
            cve_summary=cve_summary[:600],
            symbol=symbol,
            static_status=static_status,
            static_paths="; ".join(" -> ".join(p) for p in static_paths[:3])[:500] or "(none)",
            code_excerpt=code_excerpt[:1500] or "(no code excerpt available)",
        )
        import torch

        inputs = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024).to(self.device)
        with torch.inference_mode():
            out = self._model.generate(
                **inputs, max_new_tokens=self.max_new_tokens, num_beams=2,
                early_stopping=True,
            )
        answer = self._tokenizer.decode(out[0], skip_special_tokens=True)
        return self._parse(answer, static_paths)

    @staticmethod
    def _parse(answer: str, static_paths: list[list[str]]) -> ReachabilityVerdict:
        a = answer.strip().lower()
        yes = a.startswith("yes") or " yes" in a[:20]
        # Confidence: nudge by static evidence agreement
        base = 0.85 if yes else 0.80
        if static_paths and yes:
            base = 0.92
        elif not static_paths and not yes:
            base = 0.90
        return ReachabilityVerdict(
            reachable=yes,
            confidence=base,
            rationale=answer.strip(),
            static_paths=static_paths,
        )

    @staticmethod
    def _rule_based(
        cve_summary: str, symbol: str, static_paths: list[list[str]], code_excerpt: str
    ) -> ReachabilityVerdict:
        # Cheap, deterministic fallback. Used when transformers isn't installed.
        excerpt = (code_excerpt or "").lower()
        sym_simple = symbol.split(".")[-1].rstrip("()").lower()
        in_code = sym_simple in excerpt
        reachable = bool(static_paths) and in_code
        # Look for dangerous-argument cues
        dangerous = any(token in excerpt for token in [
            "req.query", "req.params", "req.body", "request.args", "input", "sourceurl"
        ])
        if reachable and dangerous:
            conf = 0.88
            reason = (
                f"Static call graph reaches {symbol} and user-controlled input flows into it."
            )
        elif reachable:
            conf = 0.72
            reason = f"{symbol} is reached statically; argument flow unclear."
        else:
            conf = 0.78
            reason = f"{symbol} not invoked from any entry point in the call graph."
        return ReachabilityVerdict(
            reachable=reachable, confidence=conf, rationale=reason, static_paths=static_paths
        )

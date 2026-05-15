#!/usr/bin/env python3
"""Scan a real GitHub repo's Dependabot alerts and run reachability analysis.

This is the live-demo CLI. Given a GitHub repo with open Dependabot alerts, it:

  1. Pulls open Dependabot alerts via the REST API.
  2. Shallow-clones the repo into a temp dir.
  3. Builds a Python/JS call graph.
  4. Joins each alert to a vulnerable-symbol map (curated table; falls back to
     regex extraction from the advisory text).
  5. Runs static reachability + (optional) Flan-T5 reasoning.
  6. Writes a JSON report and a Markdown summary sorted by predicted
     true-positive probability.

Usage:
    export GITHUB_TOKEN=ghp_...        # PAT with security_events scope
    python scripts/scan_github_repo.py --repo owner/repo --max-alerts 50

The script tries to be useful even without a token (uses unauthenticated GitHub
advisory data) and even when transformers isn't installed (rule-based reasoner).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import requests

# Allow running from repo root or scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reachability_llm.reachability import (  # noqa: E402
    build_repo_call_graph,
    lookup_vulnerable_symbol,
    ReachabilityReasoner,
    CodeSearchIndex,
)
from reachability_llm.reachability.symbols import extract_symbol_from_description  # noqa: E402

GH_API = "https://api.github.com"


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def fetch_alerts(owner: str, repo: str, token: str, max_alerts: int) -> list[dict]:
    """Page through GitHub Dependabot alerts. Requires repo or security_events scope."""
    out: list[dict] = []
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
    }
    url = f"{GH_API}/repos/{owner}/{repo}/dependabot/alerts"
    params = {"state": "open", "per_page": 100}
    while url and len(out) < max_alerts:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 404:
            raise RuntimeError(
                f"Cannot read Dependabot alerts for {owner}/{repo}. "
                "Either the repo is private and your token lacks security_events scope, "
                "or Dependabot is not enabled. Try a repo you own with Dependabot enabled."
            )
        resp.raise_for_status()
        batch = resp.json()
        out.extend(batch)
        # GitHub returns next page in Link header
        link = resp.headers.get("Link", "")
        next_url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip().strip("<>").strip()
        url = next_url
        params = None  # next_url has its own query string
    return out[:max_alerts]


def clone_repo(owner: str, repo: str, dest: Path, ref: str = "HEAD") -> Path:
    target = dest / repo
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", f"https://github.com/{owner}/{repo}.git", str(target)],
        check=True,
    )
    return target


def map_alert_to_symbol(alert: dict) -> tuple[Optional[str], str, str]:
    """Return (symbol, cve_id, summary) for a Dependabot alert payload."""
    advisory = alert.get("security_advisory", {}) or {}
    cve_id = advisory.get("cve_id") or ""
    summary = advisory.get("summary", "") or ""
    description = advisory.get("description", "") or ""
    # Try curated map first
    sym = lookup_vulnerable_symbol(cve_id)
    if sym:
        return sym.symbol, cve_id, summary
    # Fall back to regex extraction from advisory text
    extracted = extract_symbol_from_description(description) or extract_symbol_from_description(summary)
    return extracted, cve_id, summary


def classify_alert(
    alert: dict, call_graph, reasoner: ReachabilityReasoner, code_index: Optional[CodeSearchIndex]
) -> dict:
    symbol, cve_id, summary = map_alert_to_symbol(alert)
    pkg = (alert.get("dependency", {}).get("package", {}) or {}).get("name", "unknown")
    severity = (alert.get("security_advisory", {}).get("severity") or "").upper()
    epss = None  # GH Dependabot doesn't return EPSS directly; could enrich from FIRST.org

    if not symbol:
        verdict = {
            "cve_id": cve_id,
            "package": pkg,
            "severity": severity,
            "symbol": None,
            "static_reachable": None,
            "llm_reachable": None,
            "verdict": "UNKNOWN",
            "confidence": 0.5,
            "rationale": "No vulnerable symbol mapping available; left as UNKNOWN.",
            "paths": [],
        }
        return verdict

    reachable, paths, evidence = call_graph.is_reachable(symbol)
    code_excerpt = ""
    if not reachable and code_index is not None and len(code_index) > 0:
        hits = code_index.search(summary or symbol, k=3)
        code_excerpt = "\n".join(c.text for c, _ in hits)
        # If FAISS finds the pattern, the LLM might still flag reachability.
    elif reachable and paths:
        code_excerpt = call_graph.extract_code_for_path(paths[0])

    v = reasoner.reason(summary, symbol, paths, code_excerpt)

    label = "TRUE_POSITIVE" if v.reachable else "FALSE_POSITIVE"
    return {
        "cve_id": cve_id,
        "package": pkg,
        "severity": severity,
        "symbol": symbol,
        "static_reachable": reachable,
        "llm_reachable": v.reachable,
        "verdict": label,
        "confidence": v.confidence,
        "rationale": v.rationale,
        "paths": [list(p) for p in paths[:3]],
    }


def write_markdown(results: list[dict], path: Path, repo: str) -> None:
    results = sorted(
        results, key=lambda r: (-(1 if r["verdict"] == "TRUE_POSITIVE" else 0), -r["confidence"])
    )
    lines = [f"# Reachability scan — {repo}\n"]
    lines.append(f"Total alerts analyzed: **{len(results)}**\n")
    tp = sum(1 for r in results if r["verdict"] == "TRUE_POSITIVE")
    fp = sum(1 for r in results if r["verdict"] == "FALSE_POSITIVE")
    un = sum(1 for r in results if r["verdict"] == "UNKNOWN")
    lines.append(f"- TRUE_POSITIVE: **{tp}**\n- FALSE_POSITIVE: **{fp}**\n- UNKNOWN: **{un}**\n")
    lines.append(f"\nReduction in noise: **{(fp/len(results)*100 if results else 0):.1f}%** of alerts can be auto-dismissed.\n")
    lines.append("\n| CVE | Package | Severity | Verdict | Conf | Symbol | Rationale |")
    lines.append("|-----|---------|----------|---------|------|--------|-----------|")
    for r in results:
        rationale = (r["rationale"] or "").replace("\n", " ").replace("|", "/")[:120]
        lines.append(
            f"| {r['cve_id']} | {r['package']} | {r['severity']} | {r['verdict']} | "
            f"{r['confidence']:.2f} | `{r['symbol'] or '-'}` | {rationale} |"
        )
    path.write_text("\n".join(lines))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", required=True, help="GitHub repo as 'owner/name'")
    p.add_argument("--max-alerts", type=int, default=50)
    p.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"),
                   help="GitHub PAT with security_events scope (or set $GITHUB_TOKEN)")
    p.add_argument("--out", default="reports/scan.json", help="JSON output path")
    p.add_argument("--md-out", default=None, help="Markdown summary output (defaults to <out>.md)")
    p.add_argument("--use-llm", action="store_true",
                   help="Load Flan-T5 for reasoning. Default falls back to rule-based reasoner.")
    p.add_argument("--reasoner-model", default="google/flan-t5-base",
                   help="HF model id for the reasoner (only used with --use-llm)")
    p.add_argument("--with-faiss", action="store_true",
                   help="Build a FAISS code index as a fallback for unreachable alerts")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    setup_logging(args.verbose)

    if "/" not in args.repo:
        sys.exit("--repo must be in 'owner/name' form")
    owner, name = args.repo.split("/", 1)

    if not args.token:
        sys.exit("Missing GitHub token. Set $GITHUB_TOKEN or pass --token.")

    logging.info("fetching Dependabot alerts for %s/%s", owner, name)
    alerts = fetch_alerts(owner, name, args.token, args.max_alerts)
    logging.info("got %d alerts", len(alerts))

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        logging.info("cloning %s/%s into %s", owner, name, tmp_path)
        clone_path = clone_repo(owner, name, tmp_path)

        logging.info("building call graph for %s", clone_path)
        cg = build_repo_call_graph(clone_path)
        logging.info("call graph: %d nodes, %d edges", len(cg), cg.num_edges())

        code_index = None
        if args.with_faiss:
            logging.info("building FAISS code index (fallback for unreachable alerts)")
            code_index = CodeSearchIndex()
            code_index.build(clone_path)
            logging.info("indexed %d chunks", len(code_index))

        reasoner = ReachabilityReasoner(model_name=args.reasoner_model)
        if not args.use_llm:
            # force rule-based path: skip _ensure_loaded
            reasoner._model = None  # type: ignore[attr-defined]

        results: list[dict] = []
        for i, alert in enumerate(alerts, 1):
            try:
                v = classify_alert(alert, cg, reasoner if args.use_llm else _RuleOnlyReasoner(), code_index)
            except Exception as exc:  # noqa: BLE001
                logging.warning("alert %d failed: %s", i, exc)
                continue
            results.append(v)
            logging.info(
                "[%d/%d] %s %s  ->  %s (conf=%.2f)",
                i, len(alerts), v["cve_id"], v["package"], v["verdict"], v["confidence"],
            )

    out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    md_path = Path(args.md_out) if args.md_out else out_path.with_suffix(".md")
    write_markdown(results, md_path, args.repo)
    logging.info("wrote %s  and  %s", out_path, md_path)


class _RuleOnlyReasoner:
    """Shim that returns the rule-based verdict without loading transformers."""
    def reason(self, summary, symbol, paths, code):
        from reachability_llm.reachability.llm_reasoner import ReachabilityReasoner
        return ReachabilityReasoner._rule_based(summary, symbol, paths, code)


if __name__ == "__main__":
    main()

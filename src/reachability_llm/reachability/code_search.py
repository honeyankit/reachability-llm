"""Semantic code search using CodeBERT (or MiniLM) + FAISS.

Used when:
  - The static call graph fails (dynamic dispatch, eval, framework hooks, etc.)
  - The codebase is too large (1M+ LOC) to walk exhaustively
  - We need to surface similar-pattern code chunks for the LLM reasoner

The index stores per-chunk embeddings keyed to (file, line_range). Search
returns the top-k most similar chunks for a given vulnerable-pattern query
string (typically the CVE description or a known exploit pattern).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class CodeChunk:
    file: str
    start_line: int
    end_line: int
    text: str


class CodeSearchIndex:
    """Build a FAISS index over code chunks for semantic retrieval."""

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        chunk_lines: int = 25,
        chunk_overlap: int = 5,
    ) -> None:
        self.model_name = model_name
        self.chunk_lines = chunk_lines
        self.chunk_overlap = chunk_overlap
        self._encoder = None
        self._index = None
        self._chunks: list[CodeChunk] = []

    def _ensure_encoder(self) -> None:
        if self._encoder is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.model_name)
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for CodeSearchIndex. "
                "Install with: pip install sentence-transformers"
            )

    def build(
        self,
        repo_root: str | Path,
        extensions: tuple[str, ...] = (".py", ".js", ".ts", ".java", ".go", ".rb"),
        skip_dirs: tuple[str, ...] = ("node_modules", ".git", "dist", "build", "vendor"),
        max_files: int = 20000,
    ) -> int:
        """Index all source files in repo_root. Returns the chunk count."""
        try:
            import faiss
        except ImportError:
            raise ImportError("faiss-cpu is required. pip install faiss-cpu")

        self._ensure_encoder()
        self._chunks.clear()
        root = Path(repo_root)
        files: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in extensions:
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            files.append(path)
            if len(files) >= max_files:
                break

        for path in files:
            try:
                lines = path.read_text(errors="ignore").splitlines()
            except Exception:
                continue
            step = max(self.chunk_lines - self.chunk_overlap, 1)
            for start in range(0, max(len(lines), 1), step):
                end = min(start + self.chunk_lines, len(lines))
                text = "\n".join(lines[start:end])
                if not text.strip():
                    continue
                self._chunks.append(
                    CodeChunk(file=str(path.relative_to(root)), start_line=start + 1, end_line=end, text=text)
                )

        if not self._chunks:
            return 0
        embs = self._encoder.encode(
            [c.text for c in self._chunks], batch_size=64, show_progress_bar=False, normalize_embeddings=True
        ).astype("float32")
        dim = embs.shape[1]
        self._index = faiss.IndexFlatIP(dim)
        self._index.add(embs)
        return len(self._chunks)

    def search(self, query: str, k: int = 5) -> list[tuple[CodeChunk, float]]:
        if self._index is None or not self._chunks:
            return []
        self._ensure_encoder()
        q = self._encoder.encode([query], normalize_embeddings=True).astype("float32")
        scores, idxs = self._index.search(q, k)
        out: list[tuple[CodeChunk, float]] = []
        for i, score in zip(idxs[0], scores[0]):
            if i < 0:
                continue
            out.append((self._chunks[int(i)], float(score)))
        return out

    def __len__(self) -> int:
        return len(self._chunks)

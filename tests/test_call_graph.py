"""Smoke tests for static call-graph construction and reachability."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from reachability_llm.reachability import (  # noqa: E402
    build_js_call_graph,
    build_python_call_graph,
    lookup_vulnerable_symbol,
)

SAMPLE_JS_SAFE = ROOT / "data/sample/apps_js/lodash_safe.js"
SAMPLE_JS_VULN = ROOT / "data/sample/apps_js/lodash_vuln.js"
SAMPLE_PY_SAFE = ROOT / "data/sample/apps_py/yaml_safe.py"
SAMPLE_PY_VULN = ROOT / "data/sample/apps_py/yaml_vuln.py"


def _tmpdir_with(file_path: Path, tmp_path) -> Path:
    target = tmp_path / file_path.name
    target.write_text(file_path.read_text())
    return tmp_path


def test_js_safe_does_not_reach_template(tmp_path):
    root = _tmpdir_with(SAMPLE_JS_SAFE, tmp_path)
    cg = build_js_call_graph(root)
    sym = lookup_vulnerable_symbol("CVE-2021-23337")
    reach, paths, _ = cg.is_reachable(sym.symbol)
    assert reach is False
    assert paths == []


def test_js_vuln_reaches_template(tmp_path):
    root = _tmpdir_with(SAMPLE_JS_VULN, tmp_path)
    cg = build_js_call_graph(root)
    sym = lookup_vulnerable_symbol("CVE-2021-23337")
    reach, paths, _ = cg.is_reachable(sym.symbol)
    assert reach is True
    assert any("_.template" in node or "lodash.template" in node
               for path in paths for node in path)


def test_python_safe_does_not_reach_yaml_load(tmp_path):
    root = _tmpdir_with(SAMPLE_PY_SAFE, tmp_path)
    cg = build_python_call_graph(root)
    sym = lookup_vulnerable_symbol("CVE-2020-1747")
    reach, _paths, _ev = cg.is_reachable(sym.symbol)
    assert reach is False


def test_python_vuln_reaches_yaml_load(tmp_path):
    root = _tmpdir_with(SAMPLE_PY_VULN, tmp_path)
    cg = build_python_call_graph(root)
    sym = lookup_vulnerable_symbol("CVE-2020-1747")
    reach, paths, _ = cg.is_reachable(sym.symbol)
    assert reach is True
    assert any("yaml.load" in node for path in paths for node in path)


def test_symbol_lookup_known_cve():
    sym = lookup_vulnerable_symbol("CVE-2021-44228")
    assert sym is not None
    assert sym.symbol == "JndiManager.lookup"


def test_symbol_lookup_unknown_cve():
    assert lookup_vulnerable_symbol("CVE-0000-0000") is None

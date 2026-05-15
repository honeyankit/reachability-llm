#!/usr/bin/env python3
"""End-to-end worked example for CVE-2021-23337 (lodash command injection).

Runs in <10s, no GPU, no network. Demonstrates:
  - Static call-graph reachability
  - LLM (rule-based fallback) reasoning
  - Same CVE → different verdicts based on how the app uses lodash
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reachability_llm.reachability import (
    build_js_call_graph,
    lookup_vulnerable_symbol,
    ReachabilityReasoner,
)

ROOT = Path(__file__).resolve().parent.parent
SAFE_JS = ROOT / "data/sample/apps_js/lodash_safe.js"
VULN_JS = ROOT / "data/sample/apps_js/lodash_vuln.js"


def scan(app_dir: Path, label: str) -> None:
    cg = build_js_call_graph(app_dir)
    vsym = lookup_vulnerable_symbol("CVE-2021-23337")
    reachable, paths, evidence = cg.is_reachable(vsym.symbol)

    code_text = "\n".join(p.read_text() for p in app_dir.rglob("*.js"))
    # Force the rule-based reasoner for a fast offline demo. Drop _force_rule to
    # use the full Flan-T5 path (needs GPU + ~3GB download).
    v = ReachabilityReasoner._rule_based(
        "Command injection in lodash via sourceURL option of _.template()",
        vsym.symbol, paths, code_text,
    )

    print(f"\n=== {label} ===")
    print(f"  CVE:                CVE-2021-23337  ({vsym.description})")
    print(f"  Package:            lodash @ 4.17.20")
    print(f"  Vulnerable symbol:  {vsym.symbol}")
    print(f"  Static reachable:   {reachable}")
    if reachable and evidence:
        print(f"  Path:               {evidence[0]}")
    print(f"  LLM verdict:        {'TRUE_POSITIVE' if v.reachable else 'FALSE_POSITIVE'}")
    print(f"  Confidence:         {v.confidence:.2f}")
    print(f"  Rationale:          {v.rationale}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        safe_dir = tmp_path / "safe"; safe_dir.mkdir()
        vuln_dir = tmp_path / "vuln"; vuln_dir.mkdir()
        shutil.copy(SAFE_JS, safe_dir / SAFE_JS.name)
        shutil.copy(VULN_JS, vuln_dir / VULN_JS.name)

        print("CVE-2021-23337 worked example — same CVE, two apps")
        print("=" * 60)
        scan(safe_dir, "App A — uses _.map / _.capitalize / _.filter only")
        scan(vuln_dir, "App B — calls _.template(tpl, {sourceURL: req.query.src})")
        print()
        print("Conclusion: CVSS=7.2 and EPSS=0.00234 for both alerts.")
        print("Only reachability distinguishes the FALSE_POSITIVE from the TRUE_POSITIVE.")


if __name__ == "__main__":
    main()

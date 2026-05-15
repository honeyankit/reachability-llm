#!/usr/bin/env python3
"""Production reachability scanner for Dependabot alerts.

Loads the artifacts trained in `notebooks/FalsePositive_SupplyChain_Honey.ipynb`
(the RoBERTa fine-tune and the 775-d combined classifier head) and applies the
full pipeline to every open Dependabot alert on a given repository.

Output: a per-alert verdict table plus a noise-reduction summary, written as
both Markdown and JSON.

Usage:
    export GITHUB_TOKEN=ghp_pat_with_dependabot_alerts_read
    python scripts/scan_dependabot.py \\
        --owner  yourorg \\
        --repo   yourrepo \\
        --artifacts hf://honeyankit/reachability-llm-v1 \\
        --deep \\
        --out reports/yourrepo_scan.md

    # Or with a local Drive mirror of the artifacts:
    python scripts/scan_dependabot.py \\
        --owner yourorg --repo yourrepo \\
        --artifacts /Volumes/GoogleDrive/MyDrive/reachability-llm-artifacts

The artifacts spec accepts either:
    /path/to/dir              filesystem path containing MANIFEST.json
    hf://owner/repo           HuggingFace Hub repo (snapshot-downloaded on first use)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd
import requests

# Make src/ importable when running from the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from reachability_llm.models import CombinedClassifier, RobertaFineTuner  # noqa: E402
from reachability_llm.reachability import (  # noqa: E402
    ReachabilityReasoner,
    build_repo_call_graph,
    lookup_vulnerable_symbol,
)
from reachability_llm.reachability.symbols import (  # noqa: E402
    VulnSymbol,
    extract_symbol_from_description,
)


GITHUB_API = "https://api.github.com"
LOCKFILE_RE = re.compile(
    r"(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|"
    r"poetry\.lock|Pipfile\.lock|Gemfile\.lock|go\.sum)$"
)
ECOSYSTEM_ID = {"npm": 0, "pip": 1, "maven": 2, "rubygems": 3, "go": 4,
                "nuget": 5, "composer": 6}


# ─── Artifact loading ───────────────────────────────────────────────────────

def load_artifacts(spec: str) -> tuple[RobertaFineTuner, CombinedClassifier, dict]:
    """Load RoBERTa + CombinedClassifier from a local path or HF Hub repo."""
    if spec.startswith("hf://"):
        from huggingface_hub import snapshot_download
        repo_id = spec[len("hf://"):]
        print(f"  downloading artifacts from HuggingFace Hub: {repo_id}")
        root = Path(snapshot_download(repo_id=repo_id))
    else:
        root = Path(spec)
        if not root.exists():
            raise FileNotFoundError(f"artifacts directory not found: {root}")

    # HF Hub layout puts roberta files at the repo root; the notebook layout
    # puts them under roberta-cve/. Auto-detect.
    manifest_path = root / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        roberta_dir = root / manifest.get("roberta_dir", "roberta-cve")
        clf_path = root / manifest.get("classifier_file", "combined_classifier.joblib")
    else:
        roberta_dir = root
        clf_path = root / "combined_classifier.joblib"

    roberta = RobertaFineTuner.load(roberta_dir)
    clf = CombinedClassifier.from_joblib(clf_path)
    card = clf.model_card if hasattr(clf, "model_card") else {}
    print(f"  loaded RoBERTa from {roberta_dir}")
    print(f"  loaded classifier (test F1 = {card.get('test_f1', 'n/a')}, "
          f"version {card.get('version', 'n/a')})")
    return roberta, clf, card


# ─── GitHub Dependabot API ──────────────────────────────────────────────────

def gh_headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_alerts(owner: str, repo: str, token: str, state: str = "open") -> list[dict]:
    """Paginate through Dependabot alerts. Handles rate-limit back-off."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/dependabot/alerts"
    alerts: list[dict] = []
    page = 1
    while True:
        r = requests.get(
            url,
            headers=gh_headers(token),
            params={"state": state, "per_page": 100, "page": page},
            timeout=30,
        )
        if r.status_code == 403 and "rate limit" in r.text.lower():
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1) + 1
            print(f"  rate-limited, sleeping {wait:.0f}s ...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        alerts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return alerts


def shallow_clone(owner: str, repo: str, token: str, target: Path) -> Path:
    """Token-auth shallow clone so private repos work too."""
    if target.exists():
        shutil.rmtree(target)
    auth_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    subprocess.run(
        ["git", "clone", "--depth", "1", auth_url, str(target)],
        check=True, capture_output=True,
    )
    return target


def install_deps(repo_dir: Path, ecosystem: str) -> bool:
    """Run npm install / pip install so transitive code lands on disk."""
    try:
        if ecosystem == "npm":
            subprocess.run(
                ["npm", "install", "--no-audit", "--no-fund", "--ignore-scripts"],
                cwd=repo_dir, check=True, capture_output=True, timeout=300,
            )
        elif ecosystem == "pip":
            req = repo_dir / "requirements.txt"
            if req.exists():
                subprocess.run(
                    ["pip", "install", "-q", "-r", str(req),
                     "--target", str(repo_dir / ".deps")],
                    check=True, capture_output=True, timeout=600,
                )
        else:
            return False
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


# ─── Per-alert helpers ──────────────────────────────────────────────────────

def alert_scope(alert: dict) -> str:
    """'direct' or 'transitive' based on the alert's manifest_path."""
    path = (alert.get("dependency") or {}).get("manifest_path") or ""
    return "transitive" if LOCKFILE_RE.search(path) else "direct"


def resolve_symbol(alert: dict) -> Optional[VulnSymbol]:
    """Try curated map first, regex-from-description fallback."""
    adv = alert.get("security_advisory") or {}
    cve_id = adv.get("cve_id") or ""
    pkg = ((alert.get("dependency") or {}).get("package") or {}).get("name", "")
    eco = ((alert.get("dependency") or {}).get("package") or {}).get("ecosystem", "")
    summary = adv.get("summary", "")
    description = adv.get("description", "")
    if cve_id:
        v = lookup_vulnerable_symbol(cve_id)
        if v:
            return v
    sym = extract_symbol_from_description(description) or extract_symbol_from_description(summary)
    if sym:
        return VulnSymbol(
            cve_id=cve_id or "(unknown)", package=pkg, ecosystem=eco,
            symbol=sym, description=summary, cwe="",
        )
    return None


def first_epss(adv: dict) -> float:
    epss = adv.get("epss") or []
    if isinstance(epss, list) and epss:
        return float((epss[0] or {}).get("percentage", 0.001))
    return 0.001


# ─── Main scan ──────────────────────────────────────────────────────────────

def scan(
    owner: str, repo: str, token: str, *,
    deep: bool, use_llm: bool,
    roberta: RobertaFineTuner, clf: CombinedClassifier,
    max_alerts: int = 200,
) -> pd.DataFrame:
    print(f"\n[1/6] Fetching open Dependabot alerts for {owner}/{repo} ...")
    alerts = fetch_alerts(owner, repo, token, state="open")
    print(f"      pulled {len(alerts)} alerts")
    if not alerts:
        return pd.DataFrame()
    alerts = alerts[:max_alerts]

    target = Path(f"/tmp/{repo}_scan")
    print(f"[2/6] Cloning {owner}/{repo} to {target} ...")
    shallow_clone(owner, repo, token, target)

    # Detect dominant ecosystem
    eco_counts: dict[str, int] = {}
    for a in alerts:
        e = ((a.get("dependency") or {}).get("package") or {}).get("ecosystem", "").lower()
        eco_counts[e] = eco_counts.get(e, 0) + 1
    primary_eco = max(eco_counts, key=eco_counts.get) if eco_counts else "npm"
    parser_eco = "pip" if primary_eco in ("pip", "pypi") else primary_eco
    eco_id = ECOSYSTEM_ID.get(parser_eco, 7)
    print(f"      primary ecosystem: {primary_eco} ({eco_counts.get(primary_eco, 0)} alerts)")

    installed = False
    if deep:
        print("[3/6] Installing deps for transitive reachability ...")
        installed = install_deps(target, parser_eco)
        print(f"      {'installed' if installed else 'install skipped'}")
    else:
        print("[3/6] Deep scan disabled (transitive deps will be marked needs-deep-scan).")

    print("[4/6] Building call graph ...")
    cg = build_repo_call_graph(target)
    print(f"      {len(cg)} nodes, {cg.num_edges()} edges")

    reasoner: Optional[ReachabilityReasoner] = None
    if use_llm:
        try:
            import torch  # noqa: F401
            reasoner = ReachabilityReasoner(
                model_name="google/flan-t5-large",
                device="cuda" if "CUDA_VISIBLE_DEVICES" in os.environ else "cpu",
            )
        except Exception as e:
            print(f"      LLM reasoner unavailable ({type(e).__name__}); using rule-based fallback")

    # Pre-index imports for the fast-mode transitive heuristic.
    imported_packages: set[str] = set()
    if not installed:
        for ext in ("*.js", "*.mjs", "*.cjs", "*.jsx", "*.ts", "*.tsx", "*.py"):
            for path in target.rglob(ext):
                if any(p in path.parts for p in ("node_modules", "site-packages", ".deps")):
                    continue
                try:
                    src = path.read_text(errors="ignore")
                except Exception:
                    continue
                for m in re.finditer(r"""require\(\s*['"]([^'"./][^'"]*)['"]""", src):
                    imported_packages.add(m.group(1).split("/")[0])
                for m in re.finditer(r"""from\s+['"]([^'"./][^'"]*)['"]""", src):
                    imported_packages.add(m.group(1).split("/")[0])
                for m in re.finditer(r"""^\s*(?:from|import)\s+([\w_]+)""", src, re.MULTILINE):
                    imported_packages.add(m.group(1))

    print(f"[5/6] Running 775-d fusion classifier per alert ...")
    rows = []
    for i, alert in enumerate(alerts, 1):
        adv = alert.get("security_advisory") or {}
        dep = alert.get("dependency") or {}
        pkg = (dep.get("package") or {}).get("name", "")
        scope = alert_scope(alert)
        cve_id = adv.get("cve_id") or adv.get("ghsa_id") or "(no id)"
        sev = (adv.get("severity") or "").upper()
        cvss = float((adv.get("cvss") or {}).get("score") or 5.0)
        epss = first_epss(adv)
        text = ((adv.get("summary", "") or "") + ". "
                + (adv.get("description", "") or ""))[:2000]

        # ── Reachability ──
        vsym = resolve_symbol(alert)
        static_reach = 0
        llm_reach = 0
        needs_deep = False
        if vsym is not None:
            if scope == "transitive" and not installed:
                # Heuristic: was the package even imported anywhere in user code?
                if pkg.split("/")[-1] in imported_packages:
                    static_reach = 1
                    needs_deep = True
                else:
                    static_reach = 0
                llm_reach = static_reach
            else:
                sr, paths, _ = cg.is_reachable(vsym.symbol)
                static_reach = int(sr)
                llm_reach = static_reach
                if reasoner is not None and sr:
                    first_path = paths[0] if paths else []
                    code = ""
                    seen = set()
                    for n in first_path[:5]:
                        f = cg.graph.nodes[n].get("file") if n in cg.graph.nodes else None
                        if f and f not in seen:
                            seen.add(f)
                            p = target / f
                            if p.exists() and p.stat().st_size < 100_000:
                                code += p.read_text(errors="ignore")[:1500] + "\n---\n"
                    v = reasoner.reason(
                        adv.get("summary", "")[:500], vsym.symbol, paths, code,
                    )
                    llm_reach = int(v.reachable)

        # ── 775-d feature vector for THIS alert ──
        embedding = roberta.embed(pd.DataFrame([{"text": text}]))[0]
        structured = np.array(
            [cvss, epss, 365.0, 1 if vsym is not None else 0, float(eco_id)],
            dtype=np.float32,
        )
        reach_vec = np.array([static_reach, llm_reach], dtype=np.float32)
        feature_vec = np.concatenate([embedding, structured, reach_vec])[None, :]

        proba = clf.predict_proba(feature_vec)[0]
        p_tp = float(proba[1])
        if needs_deep:
            verdict = "NEEDS_DEEP_SCAN"
        elif vsym is None:
            verdict = "UNKNOWN"
        else:
            verdict = "TRUE_POSITIVE" if p_tp > 0.5 else "FALSE_POSITIVE"

        rows.append({
            "cve_id": cve_id, "package": pkg, "scope": scope, "severity": sev,
            "cvss": round(cvss, 1), "epss": round(epss, 4),
            "static_reach": bool(static_reach), "llm_reach": bool(llm_reach),
            "p_true_positive": round(p_tp, 4),
            "verdict": verdict,
            "vuln_symbol": vsym.symbol if vsym else "(unresolved)",
            "manifest": (dep.get("manifest_path") or "").rsplit("/", 1)[-1],
        })
        if i % 10 == 0:
            print(f"      processed {i}/{len(alerts)}")

    print("[6/6] Done.")
    return pd.DataFrame(rows)


# ─── Report writing ─────────────────────────────────────────────────────────

def write_reports(
    results: pd.DataFrame, out_path: Path,
    owner: str, repo: str, card: dict,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = len(results)
    if total == 0:
        out_path.write_text(f"# Reachability scan: {owner}/{repo}\n\nNo open alerts.\n")
        return

    tp = int((results["verdict"] == "TRUE_POSITIVE").sum())
    fp = int((results["verdict"] == "FALSE_POSITIVE").sum())
    unknown = int(results["verdict"].isin(["UNKNOWN", "NEEDS_DEEP_SCAN"]).sum())

    direct = int((results["scope"] == "direct").sum())
    transitive = int((results["scope"] == "transitive").sum())

    md = [
        f"# Reachability scan: {owner}/{repo}",
        "",
        f"Scanned with model **{card.get('version', 'v?')}** "
        f"(test F1 {card.get('test_f1', '?')}, "
        f"trained on {card.get('trained_on', '?')}).",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total alerts | {total} |",
        f"| Direct dependencies | {direct} |",
        f"| Transitive dependencies | {transitive} |",
        f"| True positive (action) | {tp} ({tp/total*100:.1f}%) |",
        f"| False positive (auto-dismiss) | {fp} ({fp/total*100:.1f}%) |",
        f"| Unknown / needs review | {unknown} ({unknown/total*100:.1f}%) |",
        f"| **Noise reduction** | **{fp/total*100:.1f}%** |",
        "",
        "## Per-alert verdicts",
        "",
        results.to_markdown(index=False),
    ]
    out_path.write_text("\n".join(md))
    out_path.with_suffix(".json").write_text(
        results.to_json(orient="records", indent=2)
    )
    print(f"\nReports written:\n  {out_path}\n  {out_path.with_suffix('.json')}")


# ─── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--owner", required=True, help="org or user owning the repo")
    ap.add_argument("--repo", required=True, help="repo name")
    ap.add_argument(
        "--token", default=os.environ.get("GITHUB_TOKEN"),
        help="PAT with dependabot_alerts:read + contents:read (or env GITHUB_TOKEN)",
    )
    ap.add_argument(
        "--artifacts", required=True,
        help="path to artifacts dir, or 'hf://owner/repo' for HuggingFace Hub",
    )
    ap.add_argument(
        "--deep", action="store_true",
        help="npm install / pip install for accurate transitive reachability",
    )
    ap.add_argument(
        "--no-llm", action="store_true",
        help="skip the Flan-T5 reasoner (faster, slightly less accurate)",
    )
    ap.add_argument(
        "--max-alerts", type=int, default=200,
        help="cap alerts processed (default 200)",
    )
    ap.add_argument(
        "--out", default="reports/scan.md",
        help="output Markdown path (a sibling .json file is written too)",
    )
    args = ap.parse_args()

    if not args.token:
        sys.exit("ERROR: GITHUB_TOKEN missing. Set env or pass --token.")

    print(f"Loading artifacts from {args.artifacts} ...")
    roberta, clf, card = load_artifacts(args.artifacts)

    results = scan(
        args.owner, args.repo, args.token,
        deep=args.deep, use_llm=not args.no_llm,
        roberta=roberta, clf=clf,
        max_alerts=args.max_alerts,
    )

    write_reports(results, Path(args.out), args.owner, args.repo, card)

    total = len(results)
    if total:
        fp = int((results["verdict"] == "FALSE_POSITIVE").sum())
        print(f"\nNOISE REDUCTION: {fp/total*100:.1f}% of {total} alerts "
              f"can be auto-dismissed.")


if __name__ == "__main__":
    main()

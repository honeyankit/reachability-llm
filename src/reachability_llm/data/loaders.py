"""Loaders for GitHub Advisory DB, NVD, and EPSS.

All loaders return pandas DataFrames keyed on the CVE id when possible.
They tolerate missing fields and provide a small-sample mode for local dev.
"""
from __future__ import annotations

import io
import json
import gzip
import subprocess
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import requests
from tqdm import tqdm


GH_ADVISORY_REPO = "https://github.com/github/advisory-database.git"
EPSS_LATEST_URL = "https://epss.cyentia.com/epss_scores-current.csv.gz"
NVD_RECENT_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


# ---------- GitHub Advisory Database ----------

def _iter_advisory_files(advisory_root: Path) -> Iterable[Path]:
    """Yield reviewed advisory JSON files. Skips unreviewed/withdrawn."""
    reviewed = advisory_root / "advisories" / "github-reviewed"
    if not reviewed.exists():
        # repo cloned to root layout
        reviewed = advisory_root
    yield from reviewed.rglob("*.json")


def load_advisories(
    advisory_root: str | Path,
    ecosystems: Optional[set[str]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """Parse the cloned advisory-database repo into a DataFrame.

    Args:
        advisory_root: path to a clone of github/advisory-database
        ecosystems: optional filter, e.g. {"npm", "pip", "maven", "rubygems", "go"}
        limit: cap on number of advisories (useful for dev)
    """
    root = Path(advisory_root)
    rows: list[dict] = []
    eco_lower = {e.lower() for e in ecosystems} if ecosystems else None

    for i, path in enumerate(tqdm(_iter_advisory_files(root), desc="advisories")):
        if limit and len(rows) >= limit:
            break
        try:
            adv = json.loads(path.read_text())
        except Exception:
            continue
        if adv.get("withdrawn"):
            continue
        cve = next(
            (a.get("value") for a in adv.get("aliases", []) if a.startswith("CVE-")),
            None,
        ) or next(
            (a.get("value") for a in adv.get("references", []) if a.get("value", "").startswith("CVE-")),
            None,
        )
        affected = adv.get("affected", []) or []
        if not affected:
            continue
        first = affected[0]
        eco = (first.get("package", {}).get("ecosystem") or "").lower()
        if eco_lower and eco not in eco_lower:
            continue
        pkg = first.get("package", {}).get("name", "")
        severity = (adv.get("database_specific", {}).get("severity") or "").upper()
        cvss = _extract_cvss(adv)
        cwes = adv.get("database_specific", {}).get("cwe_ids") or []
        rows.append(
            {
                "ghsa_id": adv.get("id"),
                "cve_id": cve,
                "package": pkg,
                "ecosystem": eco,
                "summary": adv.get("summary", ""),
                "description": adv.get("details", ""),
                "severity": severity,
                "cvss_score": cvss,
                "cwe_ids": ",".join(cwes),
                "published": adv.get("published"),
                "modified": adv.get("modified"),
            }
        )

    return pd.DataFrame(rows)


def _extract_cvss(advisory: dict) -> Optional[float]:
    sev = advisory.get("severity") or []
    for s in sev:
        if s.get("type") in ("CVSS_V3", "CVSS_V4"):
            score = s.get("score")
            if isinstance(score, str) and "/" in score:  # vector string
                continue
            try:
                return float(score) if score is not None else None
            except (TypeError, ValueError):
                continue
    # fall back to database_specific
    return advisory.get("database_specific", {}).get("cvss", {}).get("score")


def clone_advisory_db(target_dir: str | Path, depth: int = 1) -> Path:
    """Shallow-clone github/advisory-database. Returns the local path."""
    target = Path(target_dir)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", str(depth), GH_ADVISORY_REPO, str(target)],
        check=True,
    )
    return target


# ---------- EPSS ----------

def load_epss(url: str = EPSS_LATEST_URL, cache_path: Optional[str | Path] = None) -> pd.DataFrame:
    """Fetch latest EPSS scores. Columns: cve, epss, percentile."""
    if cache_path and Path(cache_path).exists():
        return pd.read_parquet(cache_path)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    raw = gzip.decompress(resp.content).decode("utf-8")
    # File has a comment line as row 1; pandas handles via comment='#'
    df = pd.read_csv(io.StringIO(raw), comment="#")
    df = df.rename(columns={"cve": "cve_id"})
    df["epss"] = df["epss"].astype(float)
    df["percentile"] = df["percentile"].astype(float)
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path)
    return df


# ---------- NVD ----------

def load_nvd_cve(cve_id: str, api_key: Optional[str] = None) -> dict:
    """Fetch a single CVE record from NVD 2.0 API.

    Honor the NVD rate limit (5 req / 30 s without key). For batch use, prefer
    downloading the JSON feeds and parsing locally.
    """
    headers = {"apiKey": api_key} if api_key else {}
    resp = requests.get(NVD_RECENT_URL, params={"cveId": cve_id}, headers=headers, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("vulnerabilities", [])
    return items[0]["cve"] if items else {}

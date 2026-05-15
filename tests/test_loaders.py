"""Regression tests for the GitHub Advisory DB / OSV-Schema parser."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from reachability_llm.data import load_advisories  # noqa: E402

# Real-shape fixture matching the OSV-Schema (used by github/advisory-database).
GHSA_FIXTURE = {
    "schema_version": "1.4.0",
    "id": "GHSA-35jh-r3h4-6jhm",
    "modified": "2023-11-27T20:09:25Z",
    "published": "2021-02-15T19:34:12Z",
    "aliases": ["CVE-2021-23337"],          # strings, NOT {"value": "..."} dicts
    "summary": "Command Injection in lodash",
    "details": "Versions of lodash prior to 4.17.21 are vulnerable...",
    "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
    "affected": [
        {"package": {"ecosystem": "npm", "name": "lodash"},
         "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "4.17.21"}]}]}
    ],
    "references": [
        {"type": "WEB", "url": "https://github.com/lodash/lodash/issues/4744"},
        {"type": "ADVISORY", "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-23337"},
    ],
    "database_specific": {
        "cwe_ids": ["CWE-78", "CWE-94"],
        "severity": "HIGH",
        "github_reviewed": True,
    },
}


def _write_fixture(root: Path, advisory: dict) -> None:
    leaf = root / "advisories" / "github-reviewed" / "2021" / advisory["id"]
    leaf.mkdir(parents=True, exist_ok=True)
    (leaf / f"{advisory['id']}.json").write_text(json.dumps(advisory))


def test_parses_osv_aliases_as_strings(tmp_path):
    _write_fixture(tmp_path, GHSA_FIXTURE)
    df = load_advisories(tmp_path, ecosystems={"npm"}, limit=10)
    assert len(df) == 1
    row = df.iloc[0].to_dict()
    assert row["cve_id"] == "CVE-2021-23337"
    assert row["ghsa_id"] == "GHSA-35jh-r3h4-6jhm"
    assert row["package"] == "lodash"
    assert row["ecosystem"] == "npm"
    assert row["severity"] == "HIGH"
    assert row["cvss_score"] == 7.5    # from severity-label fallback
    assert row["cwe_ids"] == "CWE-78,CWE-94"


def test_recovers_cve_from_reference_url_when_aliases_missing(tmp_path):
    """Some advisories don't list a CVE in aliases but reference one by URL."""
    adv = {**GHSA_FIXTURE, "id": "GHSA-test-noalias", "aliases": []}
    _write_fixture(tmp_path, adv)
    df = load_advisories(tmp_path, ecosystems={"npm"}, limit=10)
    assert len(df) == 1
    assert df.iloc[0]["cve_id"] == "CVE-2021-23337"   # extracted from references


def test_skips_withdrawn_advisories(tmp_path):
    adv = {**GHSA_FIXTURE, "id": "GHSA-withdrawn", "withdrawn": "2023-01-01T00:00:00Z"}
    _write_fixture(tmp_path, adv)
    df = load_advisories(tmp_path, ecosystems={"npm"}, limit=10)
    assert len(df) == 0


def test_filters_by_ecosystem(tmp_path):
    npm_adv = {**GHSA_FIXTURE, "id": "GHSA-npm-one"}
    pip_adv = {**GHSA_FIXTURE, "id": "GHSA-pip-one"}
    pip_adv["affected"] = [{"package": {"ecosystem": "pip", "name": "requests"}}]
    _write_fixture(tmp_path, npm_adv)
    _write_fixture(tmp_path, pip_adv)
    df = load_advisories(tmp_path, ecosystems={"npm"}, limit=10)
    assert len(df) == 1
    assert df.iloc[0]["ecosystem"] == "npm"

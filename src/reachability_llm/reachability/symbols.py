"""CVE → vulnerable symbol map.

In production this is sourced from a hybrid of curated datasets (VulnCode-DB,
OSV-Schema patch data, internal Dependabot annotations), AI-assisted extraction
from advisory references and patch commits, and manual curation for critical
CVEs. Here we ship a curated table for the most common CVEs used in demos and
expose hooks for AI-assisted extraction at scan time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class VulnSymbol:
    cve_id: str
    package: str
    ecosystem: str
    symbol: str
    description: str
    cwe: str


# A small but representative curated map. Real systems ship ~10K+ entries.
VULN_SYMBOL_MAP: dict[str, VulnSymbol] = {
    "CVE-2021-23337": VulnSymbol(
        cve_id="CVE-2021-23337",
        package="lodash",
        ecosystem="npm",
        symbol="_.template",
        description="Command injection via the sourceURL option of _.template().",
        cwe="CWE-78",
    ),
    "CVE-2019-11358": VulnSymbol(
        cve_id="CVE-2019-11358",
        package="jquery",
        ecosystem="npm",
        symbol="$.extend",
        description="Prototype pollution via $.extend(true, {}, attackerJson).",
        cwe="CWE-1321",
    ),
    "CVE-2021-44228": VulnSymbol(
        cve_id="CVE-2021-44228",
        package="log4j-core",
        ecosystem="maven",
        symbol="JndiManager.lookup",
        description="Log4Shell — JNDI lookup in message formatting allows RCE.",
        cwe="CWE-502",
    ),
    "CVE-2020-1747": VulnSymbol(
        cve_id="CVE-2020-1747",
        package="pyyaml",
        ecosystem="pip",
        symbol="yaml.load",
        description="Arbitrary code execution via yaml.load() with the default Loader.",
        cwe="CWE-502",
    ),
    "CVE-2019-12384": VulnSymbol(
        cve_id="CVE-2019-12384",
        package="jackson-databind",
        ecosystem="maven",
        symbol="ObjectMapper.readValue",
        description="Deserialization gadget via polymorphic typing.",
        cwe="CWE-502",
    ),
    "CVE-2022-23529": VulnSymbol(
        cve_id="CVE-2022-23529",
        package="jsonwebtoken",
        ecosystem="npm",
        symbol="jwt.verify",
        description="Weak verification of signature when secretOrPublicKey is non-string.",
        cwe="CWE-347",
    ),
    "CVE-2020-7660": VulnSymbol(
        cve_id="CVE-2020-7660",
        package="serialize-javascript",
        ecosystem="npm",
        symbol="serialize",
        description="XSS via unescaped UTF-8 character in regex source.",
        cwe="CWE-79",
    ),
    "CVE-2017-16026": VulnSymbol(
        cve_id="CVE-2017-16026",
        package="request",
        ecosystem="npm",
        symbol="request.get",
        description="Sensitive data leak when redirecting cross-protocol.",
        cwe="CWE-200",
    ),
    "CVE-2021-3737": VulnSymbol(
        cve_id="CVE-2021-3737",
        package="urllib3",
        ecosystem="pip",
        symbol="HTTPConnection.request",
        description="Infinite loop on malformed Content-Length headers.",
        cwe="CWE-835",
    ),
    "CVE-2022-22965": VulnSymbol(
        cve_id="CVE-2022-22965",
        package="spring-beans",
        ecosystem="maven",
        symbol="DataBinder.bind",
        description="Spring4Shell — RCE via class loader manipulation.",
        cwe="CWE-94",
    ),
}


def lookup_vulnerable_symbol(cve_id: str) -> Optional[VulnSymbol]:
    """Return the curated vulnerable symbol for a CVE, if known."""
    return VULN_SYMBOL_MAP.get(cve_id.strip().upper())


# Heuristics for fallback extraction when no curated entry exists.
_FN_HINT_RE = re.compile(r"""(?:function|method|API|call)\s+`?([A-Za-z_][\w.$]+\(?\)?)`?""", re.I)
_BACKTICK_RE = re.compile(r"`([A-Za-z_][\w.$]+\(?\)?)`")


def extract_symbol_from_description(text: str) -> Optional[str]:
    """Best-effort extraction of a vulnerable symbol from advisory text.

    This is a regex-only first pass intended as a baseline. A production
    pipeline replaces this with a Flan-T5 prompt that extracts the symbol
    and returns confidence; see llm_reasoner.extract_symbol().
    """
    if not text:
        return None
    for m in _BACKTICK_RE.finditer(text):
        cand = m.group(1).rstrip("()")
        if "." in cand or cand.endswith("()"):
            return cand.rstrip("()")
    m = _FN_HINT_RE.search(text)
    if m:
        return m.group(1).rstrip("()")
    return None

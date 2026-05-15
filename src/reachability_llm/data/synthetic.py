"""Synthetic dataset generator.

Used when the real Advisory DB clone is unavailable (offline dev, CI tests,
quick demos). Produces a DataFrame with the same schema as build_dataset().
The text is templated from real CWE patterns so the RoBERTa fine-tune actually
learns something distinguishable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

ECOSYSTEMS = ["npm", "pip", "maven", "rubygems", "go"]
SEVERITIES = ["LOW", "MODERATE", "HIGH", "CRITICAL"]

# CWE-keyed templates: (true_positive_template, false_positive_template, base_cvss, base_epss)
CWE_TEMPLATES = {
    "CWE-79": (
        "Cross-site scripting (XSS) in {pkg}: {fn} fails to sanitize user-controlled input, "
        "allowing remote attackers to inject arbitrary HTML or JavaScript via crafted requests. "
        "Actively observed in production exploitation against CI/CD pipelines.",
        "Theoretical XSS in {pkg}: an edge case in {fn} could allow script injection only when "
        "the function is invoked with user input AND output is rendered without escaping. "
        "No proof-of-concept exists; the affected code path is rarely reachable.",
        7.5, 0.15,
    ),
    "CWE-78": (
        "OS command injection in {pkg}: the {fn} function passes user-controlled arguments to "
        "a shell interpreter without escaping, enabling arbitrary command execution. Exploited "
        "in the wild against build systems.",
        "Command injection in {pkg}.{fn} requires attacker control over a specific configuration "
        "option that is not exposed to network-facing code. Likely unreachable in default usage.",
        9.1, 0.30,
    ),
    "CWE-89": (
        "SQL injection in {pkg}: {fn} concatenates user input directly into queries, allowing "
        "data exfiltration and authentication bypass. Multiple public exploits available.",
        "SQL injection in {pkg}.{fn} only triggers when raw-query mode is explicitly enabled, "
        "which is off by default. Practical exploitability requires non-default config.",
        8.2, 0.20,
    ),
    "CWE-22": (
        "Path traversal in {pkg}: {fn} accepts unsanitized path components and allows reading "
        "arbitrary files outside the intended directory. Actively scanned in opportunistic attacks.",
        "Theoretical path traversal in {pkg}.{fn} blocked by built-in canonicalization. The "
        "vulnerable branch only triggers on a deprecated API with no active users.",
        7.5, 0.12,
    ),
    "CWE-502": (
        "Insecure deserialization in {pkg}: {fn} unsafely deserializes attacker-controlled "
        "payloads. Used in ransomware campaigns targeting public-facing services.",
        "Deserialization gadget in {pkg}.{fn} requires an attacker to control the input stream "
        "AND specify the class loader, which is gated behind authenticated admin role.",
        9.8, 0.45,
    ),
    "CWE-918": (
        "Server-side request forgery in {pkg}: {fn} performs HTTP requests to attacker-supplied "
        "URLs without validation, allowing internal network reconnaissance.",
        "SSRF in {pkg}.{fn} only fires when the deprecated 'follow_redirects=unsafe' option is "
        "set, which generates a warning and is not used in any current example code.",
        7.2, 0.10,
    ),
    "CWE-400": (
        "Denial of service via algorithmic complexity in {pkg}: {fn} exhibits quadratic behavior "
        "on attacker-controlled inputs, enabling resource exhaustion.",
        "DoS in {pkg}.{fn} requires the attacker to send inputs >10MB and only impacts a "
        "non-critical worker. Most callers limit input size at the framework layer.",
        5.3, 0.04,
    ),
    "CWE-295": (
        "Improper certificate validation in {pkg}: {fn} accepts self-signed certificates by "
        "default, exposing TLS connections to MITM attacks.",
        "Certificate validation bug in {pkg}.{fn} only affects a deprecated codepath used by "
        "tests; production traffic uses the strict-mode wrapper.",
        7.4, 0.08,
    ),
    "CWE-94": (
        "Code injection in {pkg}: {fn} evaluates attacker-controlled strings via eval(). "
        "Actively exploited in supply-chain attacks against build tooling.",
        "Code injection in {pkg}.{fn} requires a specially crafted template AND the user must "
        "supply the sourceURL option, which is not used by any common framework integration.",
        9.8, 0.40,
    ),
    "CWE-352": (
        "Cross-site request forgery in {pkg}: {fn} lacks anti-CSRF tokens on state-changing "
        "operations, enabling authenticated session abuse.",
        "CSRF in {pkg}.{fn} blocked by default same-site cookies in modern browsers; affects "
        "only legacy embed mode that is off by default.",
        6.5, 0.06,
    ),
}

PACKAGES = {
    "npm": [("lodash", "_.template"), ("express", "send"), ("axios", "request"), ("jsonwebtoken", "verify")],
    "pip": [("pyyaml", "load"), ("requests", "get"), ("pillow", "Image.open"), ("urllib3", "PoolManager")],
    "maven": [("log4j-core", "JndiManager.lookup"), ("jackson-databind", "readValue"), ("spring-core", "bind")],
    "rubygems": [("rails", "send_file"), ("nokogiri", "XML.parse"), ("actionpack", "params")],
    "go": [("net/http", "ServeMux"), ("gopkg.in/yaml.v2", "Unmarshal"), ("crypto/tls", "Config")],
}


def generate_synthetic_dataset(n: int = 1000, seed: int = 42, noise: float = 0.15) -> pd.DataFrame:
    """Build a synthetic advisory dataset of size n with realistic templates.

    Args:
        n: number of rows
        seed: RNG seed
        noise: probability of swapping the TP/FP template for a given row,
               simulating label noise so the F1 comparison across stages is
               non-trivial. Real production data is much noisier than this.
    """
    rng = np.random.default_rng(seed)
    rows = []
    cwes = list(CWE_TEMPLATES.keys())
    today = datetime.now(timezone.utc).replace(tzinfo=None)

    for i in range(n):
        cwe = rng.choice(cwes)
        eco = rng.choice(ECOSYSTEMS)
        pkg, fn = PACKAGES[eco][rng.integers(0, len(PACKAGES[eco]))]
        tp_tpl, fp_tpl, base_cvss, base_epss = CWE_TEMPLATES[cwe]
        is_tp = rng.random() < 0.5
        # Inject label noise: with probability `noise`, render the
        # *opposite* template — so the text is ambiguous w.r.t. the label.
        text_is_tp = is_tp if rng.random() >= noise else (not is_tp)
        tpl = tp_tpl if text_is_tp else fp_tpl
        text = tpl.format(pkg=pkg, fn=fn)
        if is_tp:
            cvss = float(np.clip(base_cvss + rng.normal(0, 0.8), 0, 10))
            epss = float(np.clip(base_epss + rng.normal(0, 0.05), 0, 1))
            severity = "CRITICAL" if cvss >= 9 else "HIGH" if cvss >= 7 else "MODERATE"
        else:
            cvss = float(np.clip(base_cvss - 1.0 + rng.normal(0, 0.8), 0, 10))
            epss = float(np.clip(0.005 + rng.exponential(0.01), 0, 0.05))
            severity = "MODERATE" if cvss >= 6 else "LOW"
        days = int(rng.integers(1, 1500))
        published = (today - timedelta(days=days)).isoformat()
        rows.append({
            "ghsa_id": f"GHSA-{rng.integers(1000, 9999):04d}-syn{i:05d}",
            "cve_id": f"CVE-{2020 + (i % 6)}-{10000 + i}",
            "package": pkg,
            "ecosystem": eco,
            "summary": text[:200],
            "description": text,
            "severity": severity,
            "cvss_score": round(cvss, 1),
            "cwe_ids": cwe,
            "published": published,
            "modified": published,
            "label": int(is_tp),  # ground truth for synthetic mode
        })

    df = pd.DataFrame(rows)
    return df

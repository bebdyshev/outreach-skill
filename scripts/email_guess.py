"""Guess a person's work email from their name and company domain (no paid API)."""
from __future__ import annotations

import re
import unicodedata

import dns.exception
import dns.resolver

# Most common B2B patterns first.
PATTERNS = ["first", "first.last", "firstlast", "flast", "first_last"]


def fold(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", ascii_name.lower())


def split_name(full: str) -> tuple[str, str]:
    parts = full.split()
    if not parts:
        return "", ""
    return parts[0], parts[-1] if len(parts) > 1 else ""


def render(pattern: str, first: str, last: str) -> str:
    f, l = fold(first), fold(last)
    return {
        "first": f,
        "first.last": f"{f}.{l}",
        "firstlast": f"{f}{l}",
        "flast": f"{f[:1]}{l}",
        "first_last": f"{f}_{l}",
    }[pattern]


def _usable(pattern: str, last: str) -> bool:
    return bool(fold(last)) or pattern == "first"


def detect_pattern(known: list[dict], domain: str) -> str | None:
    """Find the pattern a company uses from real {name, email} pairs on its domain."""
    for entry in known:
        local, _, entry_domain = entry.get("email", "").strip().lower().partition("@")
        if entry_domain != domain or not local:
            continue
        first, last = split_name(entry.get("name", ""))
        if not fold(first):
            continue
        for pattern in PATTERNS:
            if _usable(pattern, last) and render(pattern, first, last) == local:
                return pattern
    return None


def has_mx(domain: str) -> bool:
    try:
        return len(dns.resolver.resolve(domain, "MX")) > 0
    except dns.exception.DNSException:
        return False


def guess(first: str, last: str, domain: str, known: list[dict] | None = None) -> dict:
    domain = domain.strip().lower()
    mx_ok = has_mx(domain)
    if not fold(first) or not mx_ok:
        return {"email": None, "confidence": "unknown", "candidates": [], "mx_ok": mx_ok}

    usable = [p for p in PATTERNS if _usable(p, last)]
    candidates = list(dict.fromkeys(f"{render(p, first, last)}@{domain}" for p in usable))

    pattern = detect_pattern(known or [], domain)
    if pattern in usable:
        email = f"{render(pattern, first, last)}@{domain}"
        candidates.remove(email)
        candidates.insert(0, email)
        return {"email": email, "confidence": "pattern-inferred",
                "candidates": candidates, "mx_ok": True}

    return {"email": candidates[0], "confidence": "pattern-guess",
            "candidates": candidates, "mx_ok": True}

# Outreach Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code skill that finds B2B leads, researches them, writes personalized cold emails, and saves them as Gmail drafts, backed by small Python helpers for lead storage and email guessing.

**Architecture:** `SKILL.md` + three reference docs carry the judgment-heavy workflow (Claude does search, research, writing, and Gmail drafts via the connector). Deterministic work lives in Python CLIs that print JSON: `leads.py` (CSV store, dedupe), `enrich.py` → `providers/` → `email_guess.py` (pattern guessing + MX check). User data lives in `~/.outreach/`, never in the repo.

**Tech Stack:** Python 3.9+ (macOS system Python is 3.9.6; files using `X | None` hints need `from __future__ import annotations`), `dnspython`, `pytest`, Claude Code skills, Gmail connector (`create_draft`).

**Spec:** `docs/superpowers/specs/2026-11-03-outreach-skill-design.md`

## Global Constraints

- User data dir: `~/.outreach/`, overridable via `OUTREACH_HOME` env var. Nothing user-specific is committed.
- `leads.csv` columns, in order: `id, company, domain, person, role, email, email_confidence, status, fit_reason, hooks, sources, draft_id, batch, created_at, updated_at`
- Statuses: `found`, `approved`, `rejected`, `no-hook`, `drafted`, `written`.
- Confidence labels: `found-on-web`, `pattern-inferred`, `pattern-guess`, `unknown`.
- Fallback pattern order: `first`, `first.last`, `firstlast`, `flast`, `first_last`.
- Dedupe key: normalized domain (lowercase, no scheme, no `www.`, no path/port).
- `hooks` and `sources` stored `|`-separated.
- All CLIs print JSON to stdout on success; on error print `{"error": "..."}` to stderr and exit 1.
- Never send email. Gmail drafts only. No SMTP mailbox probing.
- Email body ≤120 words; LinkedIn note ≤300 characters.
- Scripts run with the repo's venv: `.venv/bin/python`.

## File Structure

```
outreach-skill/
├── .gitignore
├── requirements.txt
├── README.md
├── SKILL.md
├── references/
│   ├── profile-interview.md
│   ├── research.md
│   └── writing.md
├── scripts/
│   ├── paths.py           # data_dir(): resolves + creates ~/.outreach
│   ├── leads.py           # lead store library + CLI
│   ├── email_guess.py     # fold/split/render/detect/has_mx/guess
│   ├── enrich.py          # CLI over providers.enrich
│   └── providers/
│       ├── __init__.py    # enrich() dispatch from config.json
│       └── guess.py       # default provider
└── tests/
    ├── conftest.py
    ├── test_leads.py
    ├── test_email_guess.py
    └── test_providers.py
```

---

### Task 1: Project setup + lead store (`paths.py`, `leads.py`)

**Files:**
- Create: `.gitignore`, `requirements.txt`, `scripts/paths.py`, `scripts/leads.py`, `tests/conftest.py`, `tests/test_leads.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `paths.data_dir() -> pathlib.Path` (creates the dir and `drafts/` subdir)
  - `leads.COLUMNS: list[str]`, `leads.STATUSES: set[str]`, `leads.LeadError(Exception)`
  - `leads.normalize_domain(value: str) -> str`
  - `leads.check(domain: str) -> {"exists": bool, "status": str | None}`
  - `leads.add(fields: dict) -> dict` (full row)
  - `leads.update(lead_id: str, fields: dict) -> dict` (full row)
  - `leads.list_rows(batch: str | None = None, status: str | None = None) -> list[dict]`
  - CLI: `leads.py home | check <domain> | add --json '<obj>' | update <id> --json '<obj>' | list [--batch B] [--status S]`
  - `tests/conftest.py` fixture `outreach_home` (autouse): sets `OUTREACH_HOME` to `tmp_path`, puts `scripts/` on `sys.path`.

- [ ] **Step 1: Create setup files and venv**

`.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
```

`requirements.txt`:
```
dnspython>=2.6
pytest>=8.0
```

Run:
```bash
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
```
Expected: exits 0.

- [ ] **Step 2: Write `tests/conftest.py`**

```python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture(autouse=True)
def outreach_home(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTREACH_HOME", str(tmp_path))
    return tmp_path
```

- [ ] **Step 3: Write the failing tests `tests/test_leads.py`**

```python
import csv
import json

import pytest

import leads


def row(**overrides):
    base = {"company": "Acme", "domain": "https://www.Acme.com/about", "batch": "b1"}
    base.update(overrides)
    return base


def test_normalize_domain():
    assert leads.normalize_domain("https://www.Acme.com/about?x=1") == "acme.com"
    assert leads.normalize_domain("acme.com:443") == "acme.com"
    assert leads.normalize_domain("  WWW.acme.io ") == "acme.io"


def test_check_when_no_file():
    assert leads.check("acme.com") == {"exists": False, "status": None}


def test_add_then_check():
    added = leads.add(row())
    assert added["domain"] == "acme.com"
    assert added["status"] == "found"
    assert len(added["id"]) == 8
    assert added["created_at"] == added["updated_at"] != ""
    assert leads.check("www.acme.com") == {"exists": True, "status": "found"}


def test_add_duplicate_domain_rejected():
    leads.add(row())
    with pytest.raises(leads.LeadError, match="already"):
        leads.add(row(company="Acme Inc", domain="acme.com"))


def test_add_requires_company_and_domain():
    with pytest.raises(leads.LeadError, match="domain"):
        leads.add({"company": "Acme"})


def test_add_rejects_unknown_field():
    with pytest.raises(leads.LeadError, match="unknown fields: foo"):
        leads.add(row(foo="x"))


def test_add_rejects_bad_status():
    with pytest.raises(leads.LeadError, match="status"):
        leads.add(row(status="sent"))


def test_add_joins_list_fields():
    added = leads.add(row(hooks=["raised seed", "hiring SDRs"]))
    assert added["hooks"] == "raised seed|hiring SDRs"


def test_update_changes_fields():
    added = leads.add(row())
    updated = leads.update(added["id"], {"status": "approved", "person": "Jane Doe"})
    assert updated["status"] == "approved"
    assert updated["person"] == "Jane Doe"
    assert leads.list_rows(status="approved")[0]["id"] == added["id"]


def test_update_unknown_id():
    with pytest.raises(leads.LeadError, match="no lead"):
        leads.update("nope", {"status": "approved"})


def test_update_protected_field():
    added = leads.add(row())
    with pytest.raises(leads.LeadError, match="cannot change"):
        leads.update(added["id"], {"domain": "other.com"})


def test_update_bad_status():
    added = leads.add(row())
    with pytest.raises(leads.LeadError, match="status"):
        leads.update(added["id"], {"status": "sent"})


def test_list_filters():
    leads.add(row(batch="b1"))
    leads.add(row(company="Beta", domain="beta.com", batch="b2"))
    assert [r["company"] for r in leads.list_rows()] == ["Acme", "Beta"]
    assert [r["company"] for r in leads.list_rows(batch="b2")] == ["Beta"]


def test_save_keeps_backup(outreach_home):
    leads.add(row())
    leads.add(row(company="Beta", domain="beta.com"))
    with (outreach_home / "leads.csv.bak").open(newline="") as f:
        assert len(list(csv.DictReader(f))) == 1


def test_header_mismatch_aborts(outreach_home):
    (outreach_home / "leads.csv").write_text("a,b\n1,2\n")
    with pytest.raises(leads.LeadError, match="header"):
        leads.check("acme.com")


def test_cli_add_check_and_home(capsys, outreach_home):
    assert leads.main(["add", "--json", json.dumps(row())]) == 0
    capsys.readouterr()
    assert leads.main(["check", "acme.com"]) == 0
    assert json.loads(capsys.readouterr().out) == {"exists": True, "status": "found"}
    assert leads.main(["home"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "home": str(outreach_home),
        "profile_exists": False,
    }


def test_cli_error_exit(capsys):
    assert leads.main(["update", "nope", "--json", "{}"]) == 1
    assert "error" in json.loads(capsys.readouterr().err)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_leads.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'leads'`.

- [ ] **Step 5: Write `scripts/paths.py`**

```python
"""Where the outreach skill keeps user data (profile, leads, drafts)."""
import os
from pathlib import Path


def data_dir() -> Path:
    """Return ~/.outreach (or $OUTREACH_HOME), creating it and drafts/ if needed."""
    home = Path(os.environ.get("OUTREACH_HOME") or Path.home() / ".outreach")
    (home / "drafts").mkdir(parents=True, exist_ok=True)
    return home
```

- [ ] **Step 6: Write `scripts/leads.py`**

```python
"""Lead store for the outreach skill: one CSV row per company, deduped by domain."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone

from paths import data_dir

COLUMNS = [
    "id", "company", "domain", "person", "role", "email", "email_confidence",
    "status", "fit_reason", "hooks", "sources", "draft_id", "batch",
    "created_at", "updated_at",
]
STATUSES = {"found", "approved", "rejected", "no-hook", "drafted", "written"}
SYSTEM_FIELDS = {"id", "created_at", "updated_at"}


class LeadError(Exception):
    pass


def normalize_domain(value: str) -> str:
    d = value.strip().lower()
    d = re.sub(r"^[a-z]+://", "", d)
    d = re.split(r"[/?#]", d, maxsplit=1)[0]
    d = d.split(":")[0]
    if d.startswith("www."):
        d = d[4:]
    return d


def _csv_path():
    return data_dir() / "leads.csv"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load() -> list[dict]:
    path = _csv_path()
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise LeadError(
                f"{path} header does not match expected columns; fix it by hand. "
                f"Expected: {','.join(COLUMNS)}"
            )
        return list(reader)


def save(rows: list[dict]) -> None:
    path = _csv_path()
    if path.exists():
        shutil.copy2(path, path.with_name("leads.csv.bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def _clean(fields) -> dict:
    if not isinstance(fields, dict):
        raise LeadError("fields must be a JSON object")
    unknown = set(fields) - set(COLUMNS)
    if unknown:
        raise LeadError(f"unknown fields: {', '.join(sorted(unknown))}")
    clean = {}
    for key, value in fields.items():
        if isinstance(value, list):
            value = "|".join(str(v) for v in value)
        clean[key] = "" if value is None else str(value)
    if "status" in clean and clean["status"] not in STATUSES:
        raise LeadError(f"invalid status '{clean['status']}'; use one of {sorted(STATUSES)}")
    return clean


def check(domain: str) -> dict:
    d = normalize_domain(domain)
    for r in load():
        if r["domain"] == d:
            return {"exists": True, "status": r["status"]}
    return {"exists": False, "status": None}


def add(fields: dict) -> dict:
    clean = _clean(fields)
    blocked = SYSTEM_FIELDS & set(clean)
    if blocked:
        raise LeadError(f"cannot set {', '.join(sorted(blocked))} on add")
    for key in ("company", "domain"):
        if not clean.get(key, "").strip():
            raise LeadError(f"missing required field: {key}")
    clean["domain"] = normalize_domain(clean["domain"])
    rows = load()
    if any(r["domain"] == clean["domain"] for r in rows):
        raise LeadError(f"{clean['domain']} already in leads.csv")
    now = _now()
    row = {c: "" for c in COLUMNS}
    row.update(clean)
    row.update(id=uuid.uuid4().hex[:8], status=clean.get("status") or "found",
               created_at=now, updated_at=now)
    rows.append(row)
    save(rows)
    return row


def update(lead_id: str, fields: dict) -> dict:
    clean = _clean(fields)
    blocked = (SYSTEM_FIELDS | {"domain"}) & set(clean)
    if blocked:
        raise LeadError(f"cannot change {', '.join(sorted(blocked))}")
    rows = load()
    for r in rows:
        if r["id"] == lead_id:
            r.update(clean)
            r["updated_at"] = _now()
            save(rows)
            return r
    raise LeadError(f"no lead with id {lead_id}")


def list_rows(batch: str | None = None, status: str | None = None) -> list[dict]:
    return [
        r for r in load()
        if (batch is None or r["batch"] == batch) and (status is None or r["status"] == status)
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="leads.py", description="Outreach lead store")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("home", help="show data dir and whether profile.md exists")
    p = sub.add_parser("check", help="is this domain already a lead?")
    p.add_argument("domain")
    p = sub.add_parser("add", help="add a lead row")
    p.add_argument("--json", required=True)
    p = sub.add_parser("update", help="update fields on a lead")
    p.add_argument("id")
    p.add_argument("--json", required=True)
    p = sub.add_parser("list", help="list leads")
    p.add_argument("--batch")
    p.add_argument("--status")
    args = parser.parse_args(argv)

    try:
        if args.cmd == "home":
            home = data_dir()
            result = {"home": str(home), "profile_exists": (home / "profile.md").exists()}
        elif args.cmd == "check":
            result = check(args.domain)
        elif args.cmd == "add":
            result = add(json.loads(args.json))
        elif args.cmd == "update":
            result = update(args.id, json.loads(args.json))
        else:
            result = list_rows(args.batch, args.status)
    except (LeadError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_leads.py -q`
Expected: `17 passed`.

- [ ] **Step 8: Commit**

```bash
git add .gitignore requirements.txt scripts/paths.py scripts/leads.py tests/conftest.py tests/test_leads.py
git commit -m "feat: add lead store with domain dedupe and atomic CSV writes"
```

---

### Task 2: Email guesser (`email_guess.py`)

**Files:**
- Create: `scripts/email_guess.py`, `tests/test_email_guess.py`

**Interfaces:**
- Consumes: `tests/conftest.py` (sys.path setup).
- Produces:
  - `email_guess.PATTERNS: list[str]` = `["first", "first.last", "firstlast", "flast", "first_last"]`
  - `email_guess.fold(name: str) -> str` (ASCII lowercase letters only)
  - `email_guess.split_name(full: str) -> tuple[str, str]` (first token, last token or `""`)
  - `email_guess.render(pattern: str, first: str, last: str) -> str` (local part)
  - `email_guess.detect_pattern(known: list[dict], domain: str) -> str | None`
  - `email_guess.has_mx(domain: str) -> bool`
  - `email_guess.guess(first: str, last: str, domain: str, known: list[dict] | None = None) -> {"email": str | None, "confidence": str, "candidates": list[str], "mx_ok": bool}`

- [ ] **Step 1: Write the failing tests `tests/test_email_guess.py`**

```python
import dns.exception
import pytest

import email_guess as eg


@pytest.fixture
def mx(monkeypatch):
    state = {"ok": True}
    monkeypatch.setattr(eg, "has_mx", lambda domain: state["ok"])
    return state


def test_fold():
    assert eg.fold("José") == "jose"
    assert eg.fold("O'Brien-Smith") == "obriensmith"


def test_split_name():
    assert eg.split_name("Jane van Doe") == ("Jane", "Doe")
    assert eg.split_name("  Madonna ") == ("Madonna", "")
    assert eg.split_name("") == ("", "")


def test_render_all_patterns():
    got = [eg.render(p, "Jane", "Doe") for p in eg.PATTERNS]
    assert got == ["jane", "jane.doe", "janedoe", "jdoe", "jane_doe"]


def test_detect_pattern_from_colleague():
    known = [{"name": "John Smith", "email": "JSmith@acme.com"}]
    assert eg.detect_pattern(known, "acme.com") == "flast"


def test_detect_pattern_ignores_other_domains_and_generic_inboxes():
    known = [
        {"name": "John Smith", "email": "jsmith@gmail.com"},
        {"name": "Support Team", "email": "info@acme.com"},
    ]
    assert eg.detect_pattern(known, "acme.com") is None


def test_guess_fallback(mx):
    r = eg.guess("Jane", "Doe", "Acme.com")
    assert r == {
        "email": "jane@acme.com",
        "confidence": "pattern-guess",
        "candidates": [
            "jane@acme.com", "jane.doe@acme.com", "janedoe@acme.com",
            "jdoe@acme.com", "jane_doe@acme.com",
        ],
        "mx_ok": True,
    }


def test_guess_inferred_from_colleague(mx):
    known = [{"name": "John Smith", "email": "john.smith@acme.com"}]
    r = eg.guess("Jane", "Doe", "acme.com", known)
    assert r["email"] == "jane.doe@acme.com"
    assert r["confidence"] == "pattern-inferred"
    assert r["candidates"][0] == "jane.doe@acme.com"
    assert len(r["candidates"]) == 5


def test_guess_no_mx(mx):
    mx["ok"] = False
    r = eg.guess("Jane", "Doe", "acme.com")
    assert r == {"email": None, "confidence": "unknown", "candidates": [], "mx_ok": False}


def test_guess_no_first_name(mx):
    assert eg.guess("", "Doe", "acme.com")["confidence"] == "unknown"


def test_guess_single_name(mx):
    r = eg.guess("Madonna", "", "acme.com")
    assert r["email"] == "madonna@acme.com"
    assert r["candidates"] == ["madonna@acme.com"]


def test_has_mx_true(monkeypatch):
    monkeypatch.setattr(eg.dns.resolver, "resolve", lambda domain, rtype: ["mx1"])
    assert eg.has_mx("acme.com") is True


def test_has_mx_false_on_dns_error(monkeypatch):
    def boom(domain, rtype):
        raise dns.exception.Timeout()

    monkeypatch.setattr(eg.dns.resolver, "resolve", boom)
    assert eg.has_mx("acme.com") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_email_guess.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'email_guess'`.

- [ ] **Step 3: Write `scripts/email_guess.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_email_guess.py -q`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/email_guess.py tests/test_email_guess.py
git commit -m "feat: add email pattern guesser with MX check"
```

---

### Task 3: Provider dispatch + `enrich.py` CLI

**Files:**
- Create: `scripts/providers/__init__.py`, `scripts/providers/guess.py`, `scripts/enrich.py`, `tests/test_providers.py`

**Interfaces:**
- Consumes: `paths.data_dir()` (Task 1); `email_guess.split_name`, `email_guess.guess` (Task 2).
- Produces:
  - `providers.ProviderError(Exception)`
  - `providers.provider_name() -> str` (from `config.json`, default `"guess"`)
  - `providers.enrich(company: str, domain: str, person: str, known: list[dict] | None = None) -> {"email": str | None, "confidence": str, "source": str, ...}`
  - Provider module contract: `providers/<name>.py` exposes `enrich(company, domain, person, known) -> dict` with at least `email`, `confidence`, `source`.
  - CLI: `enrich.py --company C --domain D [--person "First Last"] [--known '<json list of {name,email}>']`

- [ ] **Step 1: Write the failing tests `tests/test_providers.py`**

```python
import json

import pytest

import enrich as enrich_cli
import providers


@pytest.fixture(autouse=True)
def mx_ok(monkeypatch):
    monkeypatch.setattr("email_guess.has_mx", lambda domain: True)


def test_default_provider_is_guess():
    assert providers.provider_name() == "guess"
    r = providers.enrich("Acme", "acme.com", "Jane Doe")
    assert r["email"] == "jane@acme.com"
    assert r["confidence"] == "pattern-guess"
    assert r["source"] == "guess"
    assert len(r["candidates"]) == 5


def test_known_pairs_passed_through():
    known = [{"name": "John Smith", "email": "jsmith@acme.com"}]
    r = providers.enrich("Acme", "acme.com", "Jane Doe", known)
    assert r["email"] == "jdoe@acme.com"
    assert r["confidence"] == "pattern-inferred"


def test_unknown_provider(outreach_home):
    (outreach_home / "config.json").write_text(json.dumps({"provider": "nope"}))
    with pytest.raises(providers.ProviderError, match="unknown provider 'nope'"):
        providers.enrich("Acme", "acme.com", "Jane Doe")


def test_invalid_provider_name(outreach_home):
    (outreach_home / "config.json").write_text(json.dumps({"provider": "../evil"}))
    with pytest.raises(providers.ProviderError, match="invalid provider"):
        providers.enrich("Acme", "acme.com", "Jane Doe")


def test_bad_config_json(outreach_home):
    (outreach_home / "config.json").write_text("{not json")
    with pytest.raises(providers.ProviderError, match="not valid JSON"):
        providers.provider_name()


def test_cli_success(capsys):
    assert enrich_cli.main(["--company", "Acme", "--domain", "acme.com", "--person", "Jane Doe"]) == 0
    assert json.loads(capsys.readouterr().out)["email"] == "jane@acme.com"


def test_cli_bad_known_json(capsys):
    assert enrich_cli.main(["--company", "Acme", "--domain", "acme.com", "--known", "[oops"]) == 1
    assert "error" in json.loads(capsys.readouterr().err)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_providers.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'enrich'`.

- [ ] **Step 3: Write `scripts/providers/__init__.py`**

```python
"""Pick the email provider named in config.json and call its enrich()."""
from __future__ import annotations

import importlib
import json
import re

from paths import data_dir

DEFAULT_PROVIDER = "guess"


class ProviderError(Exception):
    pass


def provider_name() -> str:
    path = data_dir() / "config.json"
    if not path.exists():
        return DEFAULT_PROVIDER
    try:
        return json.loads(path.read_text()).get("provider", DEFAULT_PROVIDER)
    except json.JSONDecodeError as e:
        raise ProviderError(f"{path} is not valid JSON: {e}") from e


def enrich(company: str, domain: str, person: str, known: list[dict] | None = None) -> dict:
    name = provider_name()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ProviderError(f"invalid provider name '{name}' in config.json")
    module_name = f"providers.{name}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name != module_name:
            raise
        raise ProviderError(f"unknown provider '{name}' in config.json") from e
    return module.enrich(company, domain, person, known or [])
```

- [ ] **Step 4: Write `scripts/providers/guess.py`**

```python
"""Default provider: free pattern guessing + MX check."""
import email_guess


def enrich(company: str, domain: str, person: str, known: list[dict]) -> dict:
    first, last = email_guess.split_name(person)
    result = email_guess.guess(first, last, domain, known)
    return {
        "email": result["email"],
        "confidence": result["confidence"],
        "source": "guess",
        "candidates": result["candidates"],
    }
```

- [ ] **Step 5: Write `scripts/enrich.py`**

```python
"""CLI: find a likely email for a person at a company using the configured provider."""
import argparse
import json
import sys

from providers import ProviderError, enrich


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="enrich.py", description=__doc__)
    parser.add_argument("--company", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--person", default="", help='full name, e.g. "Jane Doe"')
    parser.add_argument("--known", default="[]",
                        help='JSON list of real addresses seen: [{"name": "...", "email": "..."}]')
    args = parser.parse_args(argv)

    try:
        result = enrich(args.company, args.domain, args.person, json.loads(args.known))
    except (ProviderError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `36 passed`.

- [ ] **Step 7: Smoke-test the CLIs against real DNS**

Run:
```bash
OUTREACH_HOME=$(mktemp -d) .venv/bin/python scripts/enrich.py --company Stripe --domain stripe.com --person "Jane Doe"
OUTREACH_HOME=$(mktemp -d) .venv/bin/python scripts/leads.py home
```
Expected: first prints JSON with `"email": "jane@stripe.com"` and `"confidence": "pattern-guess"`; second prints `{"home": "...", "profile_exists": false}`.

- [ ] **Step 8: Commit**

```bash
git add scripts/providers scripts/enrich.py tests/test_providers.py
git commit -m "feat: add pluggable email provider dispatch and enrich CLI"
```

---

### Task 4: Reference docs

**Files:**
- Create: `references/profile-interview.md`, `references/research.md`, `references/writing.md`

**Interfaces:**
- Consumes: nothing.
- Produces: docs that `SKILL.md` (Task 5) points to by these exact paths. `profile-interview.md` defines the `profile.md` template, with headings `## Product`, `## Ideal customer`, `## Pains we solve`, `## Proof`, `## Tone`, `## Example email`, `## Sender`.

- [ ] **Step 1: Write `references/profile-interview.md`**

````markdown
# Profile interview

Run this when `profile.md` doesn't exist in the data dir, or when the user asks to redo their profile. Ask **one question at a time**. Accept short answers and don't push for polish. If an answer is vague, ask one follow-up at most.

1. **Product:** "What does your startup do, in one or two sentences, the way you'd say it to a smart friend?"
2. **Ideal customer:** "Who buys it? Industry, company size or stage, geography, and the job title of the person who says yes."
3. **Pains:** "What problem does it solve for them? What are they doing today instead (spreadsheets, a competitor, hiring someone)?"
4. **Proof:** "What can you point to? Customers, pilots, metrics, investors, your own background. 'Nothing yet' is a fine answer."
5. **Tone:** "How do you want to sound? For example: casual founder-to-founder, crisp and formal, technical."
6. **Example email (optional):** "Paste a cold email you've sent that got a reply, if you have one."
7. **Sender:** "What name, title, and signature should the emails use? Include a calendar link if you want one."
8. **Never say:** "Anything to avoid? Claims you can't make, competitors not to name, words you hate."

Then write `profile.md` in the data dir using this template, show it to the user, and ask whether anything should change:

```markdown
# Founder profile

## Product
<1–2 sentences>

## Ideal customer
- Industry:
- Size / stage:
- Geography:
- Buyer title(s):

## Pains we solve
- <pain> — today they <current workaround>

## Proof
- <customer / metric / credential>

## Tone
<description>

## Example email
<pasted email or "none">

## Sender
<name, title, signature, optional calendar link>

## Never say
- <item>
```
````

- [ ] **Step 2: Write `references/research.md`**

```markdown
# Research guide

## Finding companies (Step 1)

- Turn the brief + ideal customer into 3–5 different search queries. Vary the angle: industry lists ("top logistics SaaS startups 2026"), funding news ("raised Series A logistics"), directories (Crunchbase, YC company list, Product Hunt), job boards (companies hiring for a role your product replaces or supports).
- For each candidate, open its website to confirm what it does and that it's still operating. Record the canonical domain.
- Write a fit reason that ties the company to a specific line of the profile. "Logistics startup" alone isn't a fit reason. "Runs a freight marketplace, so it reconciles carrier invoices by hand: our core pain" is.
- Skip: agencies reselling the space, companies clearly too big or small for the profile, dead or acquired companies.

## Finding the person (Step 2)

- Under ~50 people: founder or CEO. Otherwise: head of the function the offer serves (VP Ops, Head of Finance, CTO, ...).
- Look in this order: the company team/about page, LinkedIn profiles surfaced by web search (`"<company>" "<title>" site:linkedin.com/in`), press releases and podcasts.
- Confirm the person still works there. A current LinkedIn headline or a recent post or article is enough.
- **Collect real addresses:** whenever any `@<domain>` address appears on the site, a press page, GitHub, or a blog, record it with its owner's name. Generic inboxes (info@, hello@, sales@) are useless for pattern detection, so skip them.
- If the target's own exact address appears publicly, use it with confidence `found-on-web` and don't call `enrich.py`.

## Hooks (Step 3)

A hook is a specific, recent, verifiable fact that makes the email obviously written for this person.

**Good hooks** (prefer the last ~6 months):
- Funding round, launch, new market or major customer announcement
- A job posting that signals the pain (e.g. hiring "AP specialist" → invoice pain)
- Something the person wrote or said: a post, talk, podcast, or interview quote
- A visible product gap or complaint (reviews, changelog, public roadmap)

**Not hooks:** "I love what you're building", their company tagline, generic industry trends, anything you can't link to.

Rules:
- Every hook needs a source URL. Store hooks and their URLs in the same order.
- 2–4 hooks per lead. The email uses the strongest one; the rest are backup.
- If nothing qualifies, set `status=no-hook`. Don't write a generic email.
```

- [ ] **Step 3: Write `references/writing.md`**

```markdown
# Writing guide

## Cold email

**Subject:** 2–5 words, lowercase is fine, specific to them. Example: `invoice recon at freightco`. No clickbait, no "quick question".

**Body: 120 words max.** Structure:
1. **Hook (1 sentence):** the strongest hook, stated plainly. "Saw FreightCo just opened a Rotterdam hub."
2. **Pain (1–2 sentences):** the problem that hook implies for them, in their terms.
3. **Solution (1 sentence):** what you do, tied to that pain. No feature lists.
4. **Proof (1 sentence, if the profile has any):** the most relevant customer or metric.
5. **Ask (1 sentence):** low friction. "Worth a 15-min call next week?" or "Want me to send a 2-min Loom?"
6. **Signature:** from the profile's Sender section.

**Style:**
- Write how the profile's Tone describes: short sentences, plain words.
- One idea per email. One ask.
- "You/your" should outnumber "we/our".
- No links except an optional calendar link in the signature (links hurt deliverability on first touch).
- Respect the profile's "Never say" list.

**Banned:**
- "I hope this email finds you well" / "I hope you're doing well"
- "Quick question" / "Just reaching out" / "I wanted to touch base"
- "I came across your profile" / "I was impressed by"
- Fake familiarity ("as you know", "like we discussed")
- Invented facts, invented mutual connections, unlinkable claims
- "Revolutionary", "game-changing", "cutting-edge", "synergy", "leverage"
- Em-dash chains and triple-adjective lists

## LinkedIn note

300 characters max (connection request limit). Hook + one-line reason to connect. No pitch and no ask for a call.

## Self-check before saving

- [ ] Under the word or character limit (count it)
- [ ] The hook matches a stored source URL
- [ ] Nothing from the banned list
- [ ] The person's name, company name and title are spelled exactly as on their site
```

- [ ] **Step 4: Commit**

```bash
git add references
git commit -m "docs: add profile interview, research, and writing guides"
```

---

### Task 5: `SKILL.md`, README, and install

**Files:**
- Create: `SKILL.md`, `README.md`

**Interfaces:**
- Consumes: CLIs from Tasks 1 and 3 (`leads.py home|check|add|update|list`, `enrich.py`), docs from Task 4.
- Produces: an installed skill at `~/.claude/skills/outreach`.

- [ ] **Step 1: Write `SKILL.md`**

````markdown
---
name: outreach
description: B2B cold outreach for startup founders. Finds target companies and the right decision-maker, researches specific recent hooks, writes short personalized cold emails (plus optional LinkedIn notes), and saves them as Gmail drafts. Use when the user wants to find leads or prospects, build an outreach list, or write cold emails or LinkedIn messages to businesses.
---

# Outreach

Turn a short brief ("10 Series A logistics startups in the US, pitch the API angle") into reviewed leads and Gmail drafts.

**Never send email.** Only create drafts.

## Running the scripts

`<skill>` is this skill's base directory. All scripts print JSON; on failure they print `{"error": ...}` to stderr and exit 1.

```bash
PY=<skill>/.venv/bin/python
$PY <skill>/scripts/leads.py home                       # data dir + profile_exists
$PY <skill>/scripts/leads.py check <domain>             # already contacted?
$PY <skill>/scripts/leads.py add --json '{...}'         # new row (status=found)
$PY <skill>/scripts/leads.py update <id> --json '{...}'
$PY <skill>/scripts/leads.py list [--batch B] [--status S]
$PY <skill>/scripts/enrich.py --company C --domain D --person "First Last" --known '[{"name":"...","email":"..."}]'
```

If `.venv` is missing, tell the user to run the install steps in `<skill>/README.md`.

## Workflow

**Batch name:** `YYYY-MM-DD-<short-slug-of-brief>`. If the user asks to continue a batch, run `leads.py list --batch <name>` and resume from each lead's status.

### Step 0: Profile
Run `leads.py home`. If `profile_exists` is false, run the interview in `references/profile-interview.md` and save `profile.md` to the data dir. Otherwise read it. The brief overrides the profile where they conflict. Default count is 10.

### Step 1: Find companies
Follow `references/research.md` → "Finding companies". Aim for ~1.5× the requested count, rounded up. Run `leads.py check` on each domain and drop any that exist (any status). If you can't find enough good fits, say so and suggest a broader brief. Never pad with weak fits.

### Step 2: Find the person and email
Follow `references/research.md` → "Finding the person". For each company:
- Exact address found publicly → `email_confidence=found-on-web`.
- Otherwise run `enrich.py` with any `{name, email}` pairs you collected, and use its `email` and `confidence`.
- No person found → leave `person` empty.

Save each with `leads.py add` (`company, domain, person, role, email, email_confidence, fit_reason, batch`).

### ⏸ Checkpoint
Show a table: `# · company · person · role · email · confidence · fit reason`. Mark `pattern-guess` emails 🟡. Ask the user which to keep, drop, or fix. **Wait for their answer.**
- Kept → `status=approved`. Dropped → `status=rejected`.
- Emails the user supplies → `email_confidence=found-on-web`.
- A kept lead still lacking a person stays `approved` but gets no email (see Step 5).

### Step 3: Research
For each `approved` lead, follow `references/research.md` → "Hooks". Save with `leads.py update <id> --json '{"hooks": [...], "sources": [...]}'`. No qualifying hook → `status=no-hook` and skip the lead from here on.

### Step 4: Write
For each lead with hooks, write the email (and the LinkedIn note if the brief asks for one, or the lead has no usable email) per `references/writing.md`. Run its self-check.

### Step 5: Deliver
- **Email present and confidence not `unknown`:** create a Gmail draft with the Gmail connector's `create_draft` tool (load it through ToolSearch if it's deferred). Then `update` with `status=drafted, draft_id=<id>`.
- **Otherwise:** `status=written`.
- **If the Gmail connector is unavailable or errors:** don't abort. Mark those leads `written` and tell the user.
- **Always:** write every message (subject, body, LinkedIn note, hooks with URLs) to `<data dir>/drafts/<batch>.md`.

Finish with a summary: drafted count, written-only count, skipped (`no-hook`, `rejected`) with reasons, 🟡 list of `pattern-guess` emails to double-check, and the path to the batch file.
````

- [ ] **Step 2: Write `README.md`**

````markdown
# outreach

A Claude Code skill for B2B cold outreach: find leads → research hooks → write emails → Gmail drafts. Nothing is ever sent automatically.

## Install

```bash
git clone <this repo> && cd outreach-skill
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p ~/.claude/skills && ln -s "$PWD" ~/.claude/skills/outreach
```

Connect Gmail in Claude (claude.ai connectors) for drafts. Without it, messages are saved to files only.

## Use

In Claude Code: *"Use outreach: find 10 seed-stage fintech startups in the UK, pitch the compliance angle."*

The first run interviews you and saves `~/.outreach/profile.md`. Edit it anytime.

## Data

`~/.outreach/`: `profile.md`, `leads.csv` (open it in any spreadsheet app), `config.json`, `drafts/`.

## Adding a paid email provider

Create `scripts/providers/<name>.py` with `enrich(company, domain, person, known) -> {"email", "confidence", "source"}`, then set `~/.outreach/config.json` to `{"provider": "<name>"}`.

## Tests

```bash
.venv/bin/python -m pytest -q
```
````

- [ ] **Step 3: Install the skill locally**

Run:
```bash
mkdir -p ~/.claude/skills && ln -sfn "$PWD" ~/.claude/skills/outreach && ls -l ~/.claude/skills/outreach
```
Expected: a symlink pointing to the repo.

- [ ] **Step 4: Run the full test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: `36 passed`.

- [ ] **Step 5: Commit**

```bash
git add SKILL.md README.md
git commit -m "feat: add outreach SKILL.md and README"
```

---

### Task 6: Manual end-to-end check (with the user)

**Files:** none (a fix found here goes into the relevant file plus its own commit).

**Interfaces:**
- Consumes: the installed skill.
- Produces: a verified working run.

- [ ] **Step 1:** In a fresh Claude Code session, ask: *"Use outreach: find 3 seed-stage B2B SaaS startups in Europe."* Confirm the profile interview runs (if no `~/.outreach/profile.md` exists) and `profile.md` gets saved.
- [ ] **Step 2:** Confirm the checkpoint table appears and the run waits. Reject one lead.
- [ ] **Step 3:** After approval, confirm `~/.outreach/leads.csv` shows the rejected row as `rejected`, and the others as `drafted`, `written` or `no-hook`, with hooks and sources filled in.
- [ ] **Step 4:** Open Gmail Drafts and confirm one draft per `drafted` row. Check each body is ≤120 words and has none of the banned phrases from `writing.md`.
- [ ] **Step 5:** Confirm `~/.outreach/drafts/<batch>.md` exists and contains every message.
- [ ] **Step 6:** Re-run the same brief and confirm the earlier companies are skipped (dedupe).

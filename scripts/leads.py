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
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise LeadError(
                f"{path} header does not match expected columns; fix it by hand. "
                f"Expected: {','.join(COLUMNS)}"
            )
        rows = list(reader)
    for n, r in enumerate(rows, 1):
        if None in r:
            raise LeadError(f"row {n} has more cells than the header; fix leads.csv by hand")
    return rows


def save(rows: list[dict]) -> None:
    path = _csv_path()
    if path.exists():
        shutil.copy2(path, path.with_name("leads.csv.bak"))
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _clean(fields) -> dict:
    if not isinstance(fields, dict):
        raise LeadError("fields must be a JSON object")
    unknown = set(fields) - set(COLUMNS)
    if unknown:
        raise LeadError(f"unknown fields: {', '.join(sorted(unknown))}")
    clean = {}
    for key, value in fields.items():
        if isinstance(value, dict):
            raise LeadError(f"{key} must be a string, number, or list of plain strings")
        if isinstance(value, list):
            for v in value:
                if not isinstance(v, (str, int, float)) or isinstance(v, bool):
                    raise LeadError(f"{key} items must be plain strings")
                if "|" in str(v):
                    raise LeadError(f"{key} items must not contain '|' (the list separator)")
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
    if not clean["domain"]:
        raise LeadError("missing required field: domain")
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


def _payload(value: str):
    """Parse a JSON payload; '-' reads it from stdin."""
    return json.loads(sys.stdin.read() if value == "-" else value)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="leads.py", description="Outreach lead store")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("home", help="show data dir and whether profile.md exists")
    p = sub.add_parser("check", help="is this domain already a lead?")
    p.add_argument("domain")
    p = sub.add_parser("add", help="add a lead row")
    p.add_argument("--json", required=True, help="JSON object, or - to read stdin")
    p = sub.add_parser("update", help="update fields on a lead")
    p.add_argument("id")
    p.add_argument("--json", required=True, help="JSON object, or - to read stdin")
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
            result = add(_payload(args.json))
        elif args.cmd == "update":
            result = update(args.id, _payload(args.json))
        else:
            result = list_rows(args.batch, args.status)
    except (LeadError, OSError, UnicodeDecodeError, csv.Error, ValueError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

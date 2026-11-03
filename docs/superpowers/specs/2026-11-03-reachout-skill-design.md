# Reachout Skill — Design Spec

**Date:** 2026-11-03
**Status:** Draft, pending user review

## Goal

A Claude Code skill that helps startup founders do B2B cold outreach. Given a short brief, it finds target companies, identifies the right person at each, researches specific hooks, writes personalized cold emails, and places them as Gmail drafts for the founder to review and send.

**In scope (v1):** lead finding, prospect research, message writing, Gmail drafts, lead tracking to prevent duplicate outreach.

**Out of scope (v1):** follow-up sequencing, automatic sending, LinkedIn automation, SMTP mailbox verification, paid data providers (interface only; no adapter shipped).

## Decisions

| Topic | Decision |
|---|---|
| Data source | Web search only in v1; pluggable provider interface for a paid API later |
| Output | `leads.csv` + one Gmail draft per lead with a usable email; optional LinkedIn note (≤300 chars) |
| Founder context | Saved `profile.md` (created by onboarding interview) + per-run brief that overrides it |
| Control | One approval checkpoint after the lead list, before research/writing |
| Architecture | Prompt skill + small Python helper scripts for deterministic work |

## Workflow

Triggered by a brief, e.g. *"find 10 Series A logistics startups in the US, pitch the API angle."* The brief may request a count; default is 10.

**Step 0 — Profile.** If `~/.reachout/profile.md` is missing, run the onboarding interview (`references/profile-interview.md`): product, ideal customer, pains solved, proof/traction, tone, an example cold email that worked (optional), sender name and signature. Save it. Otherwise load it. The brief overrides the profile wherever they conflict.

**Step 1 — Find companies.** Web search for companies matching brief + profile. For each: name, domain, one-line description, fit reason. Run `leads.py check <domain>` and drop any company already in `leads.csv` (any status). Collect about 1.5× the requested count, rounded up.

**Step 2 — Find the person.** For each company, identify the best decision-maker: founder/CEO for companies under ~50 people, otherwise the head of the function the offer serves. Sources: team/about pages, LinkedIn results surfaced in search, press. While browsing, record any real email addresses seen on the company's domain together with the owner's name (`{name, email}` pairs). Call the provider (`enrich` via `scripts/enrich.py`) to get an email and confidence label. Add rows via `leads.py add` with `status=found`.

**Checkpoint.** Show a table: `# · company · person · role · email · confidence · fit reason`. The user replies with edits (drop rows, swap a person, correct an email). Mark kept rows `approved` and dropped rows `rejected`. Do not continue until the user confirms.

**Step 3 — Research (approved only).** For each lead, gather 2–4 hooks that are specific, recent (ideally within ~6 months), and verifiable: launches, funding, hiring posts, things the person wrote or said, visible pain points. Every hook needs a source URL. If no hook qualifies, mark the lead `no-hook` and skip writing for it. Never invent a hook or fall back to generic flattery.

**Step 4 — Write.** Per `references/writing.md`:
- Email: subject line + body ≤120 words. Structure: specific hook → relevant pain → one-line solution → proof → low-friction ask.
- Optional LinkedIn note ≤300 characters, when the brief asks for it or the lead has no usable email.
- Use the profile's tone and signature. Avoid the banned-pattern list in `writing.md` (e.g. "I hope this finds you well", "quick question", fake familiarity).

**Step 5 — Deliver.** For each lead with an email of confidence other than `unknown`, create a Gmail draft (never send). Update the row to `status=drafted` with `draft_id`, `hooks`, `sources`. Leads without a usable email get `status=written` and their message is saved in the batch file only. Always write the full batch (all messages, including LinkedIn notes) to `~/.reachout/drafts/<batch>.md`. Print a summary: drafted count, skipped and why, 🟡 flag on every `pattern-guess` email.

## Files

### Repo (the skill)

Installed by symlinking the repo to `~/.claude/skills/reachout`.

```
reachout-skill/
├── SKILL.md
├── references/
│   ├── profile-interview.md
│   ├── research.md
│   └── writing.md
├── scripts/
│   ├── leads.py
│   ├── paths.py              # data dir resolution (REACHOUT_HOME override)
│   ├── email_guess.py
│   ├── enrich.py             # CLI over providers.enrich
│   └── providers/
│       ├── __init__.py
│       └── guess.py
├── tests/
├── requirements.txt          # dnspython, pytest (installed into .venv/)
└── .gitignore
```

### User data (outside repo)

```
~/.reachout/
├── profile.md
├── leads.csv
├── leads.csv.bak
├── config.json               # {"provider": "guess"}
└── drafts/<batch>.md
```

Created on first run if missing. Location can be overridden with the `REACHOUT_HOME` env var (used by tests). `<batch>` is `YYYY-MM-DD-<slug-of-brief>`.

### `leads.csv`

Columns: `id, company, domain, person, role, email, email_confidence, status, fit_reason, hooks, sources, draft_id, batch, created_at, updated_at`

- `status`: `found → approved → drafted` (Gmail draft created) or `written` (message in batch file only, no usable email), or `rejected`, or `no-hook`.
- Dedupe key: normalized domain (lowercase, strip scheme, `www.`, path).
- `hooks` and `sources` are `|`-separated within the cell.

## Components

### `scripts/leads.py` (CLI, JSON output)

- `check <domain>` → `{"exists": bool, "status": str|null}`
- `add --json '<row>'` → adds a row with new `id`; fails if the domain exists
- `update <id> --json '<fields>'` → merges fields, bumps `updated_at`
- `list [--batch B] [--status S]` → rows as JSON

Writes are atomic: copy current file to `leads.csv.bak`, write to a temp file, `os.replace` into place. If the CSV header doesn't match the expected columns, exit non-zero with a clear message rather than rewriting.

### `scripts/email_guess.py`

`guess(first, last, domain, known=None) -> {"email", "confidence", "candidates", "mx_ok"}` where `known` is a list of `{"name", "email"}` pairs for real addresses seen on the web.

1. MX lookup via `dnspython`. No MX → `confidence=unknown`, `email=None`.
2. If `known` contains addresses on the domain, detect their pattern by matching each owner's name against the pattern list and apply it → `pattern-inferred`.
3. Otherwise rank: `first`, `first.last`, `firstlast`, `flast`, `first_last` → top candidate, `pattern-guess`.
4. If the exact target address was seen on the web, Claude records it directly as `found-on-web` without calling the guesser.

Names are lowercased and ASCII-folded (e.g. `José` → `jose`). The skill calls it through `scripts/enrich.py`, not directly.

### `scripts/providers/`

`enrich(company, domain, person, known=None) -> {"email", "confidence", "source", ...}` (providers may add extra keys, e.g. `candidates`)

`__init__.py` reads `provider` from `~/.reachout/config.json` (default `guess`) and dispatches. `guess.py` wraps `email_guess.guess`. A future `apollo.py` implements the same function; no other code changes.

### Confidence labels

| Label | Meaning | Draft? |
|---|---|---|
| `found-on-web` | Exact address seen publicly | Yes |
| `pattern-inferred` | Derived from a colleague's real address | Yes |
| `pattern-guess` | Common-pattern fallback | Yes, flagged 🟡 |
| `unknown` | No MX or no person | No |

SMTP mailbox probing is deliberately excluded: unreliable (catch-alls, blocking) and it risks getting the user's IP flagged.

## Error handling

- **Too few companies found:** report what was found, suggest broadening the brief. Never pad the list with weak fits.
- **No decision-maker found:** keep the row with an empty `person`, show it at the checkpoint so the user can fill it in, and exclude it from drafts if still empty.
- **No qualifying hook:** `status=no-hook`, listed in the summary.
- **Gmail connector unavailable or erroring:** fall back to the batch file only and report it. The run doesn't abort.
- **CSV issues:** atomic writes + `.bak`; header mismatch aborts with a message.
- **Interrupted run:** status is updated per lead, so re-running the same batch resumes. Leads already `drafted` or `written` are skipped.

## Testing

- `pytest` for `leads.py`: add/check/update/list, domain normalization, duplicate rejection, atomic write + backup, header-mismatch abort.
- `pytest` for `email_guess.py`: pattern detection from known emails, fallback ranking, ASCII folding, MX success/failure with mocked DNS.
- `pytest` for provider dispatch: default to `guess`, unknown provider → clear error.
- Manual end-to-end: one real run with a 3-lead brief, verifying checkpoint behavior, CSV state, and Gmail drafts.

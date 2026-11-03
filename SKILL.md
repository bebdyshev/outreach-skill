---
name: reachout
description: B2B cold outreach for startup founders. Finds target companies and the right decision-maker, researches specific recent hooks, writes short personalized cold emails (plus optional LinkedIn notes), and saves them as Gmail drafts. Use when the user wants to find leads or prospects, build an outreach list, or write cold emails or LinkedIn messages to businesses.
---

# Reachout

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

**Batch name:** `YYYY-MM-DD-<short-slug-of-brief>`. If the user asks to continue a batch, run `leads.py list --batch <name>` and resume each lead from its status:
- `found` → the checkpoint
- `approved` with empty `hooks` → Step 3
- `approved` with `hooks` → Step 4
- `drafted`, `written`, `no-hook`, `rejected` → skip (never create a second draft for a lead)

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
- Every kept lead needs a person. If one has none, ask the user to name someone (then re-run `enrich.py` for the email) or drop it as `rejected`.

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

# Agent guide

This repo is the **outreach** Claude Code skill: `SKILL.md` and `references/` tell Claude how to run B2B cold outreach, and `scripts/` holds small Python CLIs for the parts that must be exact. Read `README.md` for what it does and `docs/superpowers/specs/2026-11-03-outreach-skill-design.md` for why.

## Layout

- `SKILL.md` - the workflow Claude follows. Treat it as code: wording changes change behavior.
- `references/` - guides Claude reads mid-run (`profile-interview.md`, `research.md`, `writing.md`).
- `scripts/` - `leads.py` (lead store), `email_guess.py`, `enrich.py`, `providers/`, `paths.py`.
- `docs/` - `RELEASE-NOTES.md`, the original `brainstorm.md`, and the design spec and plan under `docs/superpowers/`. `.github/CONTRIBUTING.md` has the contribution guide.
- `tests/` - pytest. `tests/conftest.py` puts `scripts/` on `sys.path` and points `OUTREACH_HOME` at a temp dir for every test.
- User data lives in `~/.outreach/` (or `$OUTREACH_HOME`), never in the repo. Never commit profile, leads or drafts.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

## Rules that must keep holding

- **Never send email.** Gmail drafts only.
- **Python 3.9.** Files that use `X | None` or `list[dict]` hints start with `from __future__ import annotations`.
- **CLI contract.** Scripts print JSON to stdout on success. On any failure they print `{"error": "..."}` to stderr and exit 1, never a traceback.
- **No web text in shell arguments.** Names, hooks and the like reach the scripts only as JSON on stdin through a quoted heredoc (`--json -`). If you add a CLI, give it the same input path.
- **Fixed vocabularies.** Statuses: `found`, `approved`, `rejected`, `no-hook`, `drafted`, `written`. Email confidence: `found-on-web`, `pattern-inferred`, `pattern-guess`, `unknown`. `SKILL.md`, the reference docs and the code must agree on these.
- **`leads.csv` columns** are defined once, in `scripts/leads.py` (`COLUMNS`). `hooks` and `sources` are `|`-separated lists of plain strings.
- **Limits.** Email body 120 words or fewer, LinkedIn note 300 characters or fewer.
- **Honesty.** A hook needs a source URL. No verifiable hook means the lead is skipped, never padded.

## Working here

- Write the failing test first for any script change.
- Tests cannot check instruction wording. After editing `SKILL.md` or `references/`, run the skill on a small brief (3 leads) in a new Claude Code session and read the output.
- Keep changes small and match the surrounding style.

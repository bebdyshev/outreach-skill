# Release Notes

## v0.1.0 (2026-11-03)

First release.

### Skill

- Brief-driven workflow: find companies, find the decision-maker, checkpoint, research hooks, write, deliver Gmail drafts.
- One-time profile interview, saved to `~/.outreach/profile.md`, with the brief overriding it per run.
- One approval checkpoint after the lead list, shown as three lines per candidate with 🟡 and ⚠ flags.
- Hooks must be specific, sourced and verifiable. A lead with no qualifying hook is skipped, not written generically.
- Emails of 120 words or fewer, optional LinkedIn notes of 300 characters or fewer. Drafts only, never sent.
- Resumable batches. Leads already `drafted` or `written` are skipped on a re-run, and the batch file is append-only.

### Scripts

- `leads.py`: lead store deduplicated by domain, atomic writes with a backup, tolerant of Excel-saved CSVs.
- `email_guess.py`: address patterns, inference from real colleague addresses, MX check.
- `enrich.py` and `providers/`: pluggable email provider, default is the free guesser.
- All scripts print JSON and report errors as JSON on stderr. Input arrives as JSON on stdin, never as shell arguments.

### Tests

- 57 tests, run with `.venv/bin/python -m pytest -q`.

### Known limits

- Without a paid provider, most addresses are pattern guesses. They are marked 🟡 and can bounce.
- Follow-up sequences are not included.

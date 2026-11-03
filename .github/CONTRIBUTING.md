# Contributing

Thanks for helping. This project is small on purpose, so a short, focused change is the best kind.

## Before you start

- Open an issue first for anything bigger than a bug fix or a wording tweak, so we can agree on the approach.
- Read [AGENTS.md](../AGENTS.md). It lists the rules the code and the skill text must keep, such as never sending email and passing JSON through stdin.

## Process

1. Fork the repository.
2. Create a branch for your work.
3. Set up and run the tests:

   ```bash
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m pytest -q
   ```

4. Make your change.
   - **Script changes:** write the failing test first, then the code.
   - **`SKILL.md` or `references/` changes:** tests can't cover these. Run the skill on a 3-lead brief in a fresh Claude Code session and include what you saw in the PR.
5. Open a pull request. Say what changed and why, in your own words, and how you checked it.

## What fits well

- Bug fixes, with a test that fails before the fix.
- New email providers under `scripts/providers/` (see the README for the interface).
- Clearer wording in the reference docs, when you can point to a run where the old wording went wrong.

## What to avoid

- New dependencies without discussing them first.
- Anything that sends email, or makes sending easier than reviewing a draft.
- Changes that put personal data (profiles, leads, drafts) into the repo.

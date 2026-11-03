# reachout

A Claude Code skill for B2B cold outreach: find leads → research hooks → write emails → Gmail drafts. Nothing is ever sent automatically.

## Install

```bash
git clone <this repo> && cd reachout-skill
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p ~/.claude/skills && ln -s "$PWD" ~/.claude/skills/reachout
```

Connect Gmail in Claude (claude.ai connectors) for drafts. Without it, messages are saved to files only.

## Use

In Claude Code: *"Use reachout: find 10 seed-stage fintech startups in the UK, pitch the compliance angle."*

The first run interviews you and saves `~/.reachout/profile.md`. Edit it anytime.

## Data

`~/.reachout/`: `profile.md`, `leads.csv` (open it in any spreadsheet app), `config.json`, `drafts/`.

## Adding a paid email provider

Create `scripts/providers/<name>.py` with `enrich(company, domain, person, known) -> {"email", "confidence", "source"}`, then set `~/.reachout/config.json` to `{"provider": "<name>"}`.

## Tests

```bash
.venv/bin/python -m pytest -q
```

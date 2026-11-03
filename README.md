# Outreach

Outreach is a B2B cold outreach skill for startup founders, built for Claude Code. It finds companies that fit what you sell, finds the right person at each one, researches something specific to say to them, and leaves a short email waiting in your Gmail drafts. It never sends anything.

## Table of Contents

- [How it works](#how-it-works)
- [Installation](#installation)
- [The Basic Workflow](#the-basic-workflow)
- [Your data](#your-data)
- [When something goes wrong](#when-something-goes-wrong)
- [What's Inside](#whats-inside)
- [Philosophy](#philosophy)
- [Responsible use](#responsible-use)
- [Contributing](#contributing)
- [Updating](#updating)
- [License](#license)

## How it works

You give it a one-line brief: *"find 10 seed-stage fintech startups in the UK, pitch the compliance angle."*

The first time, it interviews you about your startup: what you sell, who buys it, what pain it fixes, what proof you have, how you sound. It saves the answers to a profile you can edit. Every later run reuses that profile, and the brief on top of it wins wherever the two disagree.

Then it searches the web for companies that fit, picks the decision-maker at each (the founder at a small company, the head of the relevant function at a larger one), and works out an email address. It shows you the candidates as a short list and **stops**. You keep, drop or fix leads, and only then does it spend time on research and writing.

For each lead you approved, it collects two to four specific, recent, sourced facts. If it can't find one that checks out, it skips the lead instead of writing generic flattery. It writes an email of 120 words or fewer around the strongest fact, and puts it in your Gmail drafts. You read it, edit it and send it yourself.

Every lead is recorded in one spreadsheet-friendly file, so you never pitch the same company twice, and an interrupted batch picks up where it stopped.

## Installation

Requirements: [Claude Code](https://claude.com/claude-code), Python 3.9 or newer, and (for drafts) the Gmail connector enabled in your Claude account. Without Gmail, the messages are saved to a file instead.

```bash
git clone https://github.com/Bebdyshev/outreach-skill.git && cd outreach-skill
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p ~/.claude/skills && ln -sfn "$PWD" ~/.claude/skills/outreach
```

Start a new Claude Code session and ask for it by name:

```text
Use outreach: find 10 seed-stage fintech startups in the UK, pitch the compliance angle.
```

## The Basic Workflow

1. **Profile** - Runs once. A short interview saves `profile.md`. Later runs just load it.
2. **Find companies** - Searches the web for fits, collects about 1.5x the number you asked for, and skips any company already in your lead file.
3. **Find the person** - Picks the decision-maker and looks for their real address. If none is public, it guesses from the company's address pattern and checks the domain accepts mail. Guessed addresses are marked 🟡.
4. **Checkpoint** - Shows each candidate in three lines and waits. Reply *"keep 1-4, drop 5"*.
5. **Research** - For approved leads only: two to four recent, verifiable facts, each with a source link. No fact, no email.
6. **Write** - A subject and a body of 120 words or fewer: a specific fact, the pain it implies, how you solve it, proof if you have any, one easy ask. Optionally a LinkedIn note of 300 characters or fewer.
7. **Deliver** - One Gmail draft per lead with a usable address. Every message is also saved to a batch file, and you get a summary of what was drafted and what was skipped and why.

The checkpoint looks like this:

```text
Batch 2026-11-03-freight-saas · 3 candidates

1. Northwind Freight · Jane Doe (CEO)
   jane.doe@northwind.example · found on web
   Fit: runs a carrier marketplace; reconciles invoices by hand

2. Harbor Logistics · Sam Lee (COO)
   sam@harbor.example · 🟡 guessed
   Fit: hiring two AP clerks; mentions month-end backlog

3. Blue Route · Pat Kim (founder)
   info@blueroute.example · ⚠ shared inbox
   Fit: weak; already uses an invoice-automation vendor

Suggest: keep 1-2, drop 3.
Reply e.g. "keep 1-2, drop 3".
```

## Your data

Everything about you and your leads lives in `~/.outreach/`, outside this repo, so nothing personal is ever committed. Set `OUTREACH_HOME` to use a different folder.

| File | What it is |
|---|---|
| `profile.md` | Your startup context. Plain Markdown, edit it anytime. |
| `leads.csv` | Every lead ever touched, one row per company. Opens in Excel or Google Sheets. |
| `drafts/<batch>.md` | Every message from a batch, with its sources. |
| `config.json` | Which email provider to use. Default: `{"provider": "guess"}`. |

Lead statuses run `found` → `approved` → `drafted`. A lead can also end as `written` (message saved, no usable address), `no-hook` (nothing specific to say) or `rejected`.

## When something goes wrong

- **A message looks off.** Open `drafts/<batch>.md`. Each hook sits next to its source link, so you can check what the email claims.
- **An address looks wrong.** `leads.csv` has an `email_confidence` column: `found-on-web`, `pattern-inferred`, `pattern-guess` or `unknown`. Treat `pattern-guess` as a guess.
- **A run stopped halfway.** Ask to continue the batch by name. Leads that are already `drafted` or `written` are skipped, so you won't get duplicate drafts.
- **The scripts misbehave.** They print JSON errors you can read. Run `.venv/bin/python -m pytest -q` to check the install.

## What's Inside

### The skill

- **`SKILL.md`** - The workflow Claude follows, step by step, and the exact commands it runs.

### References

Claude reads these while it works.

- **`references/profile-interview.md`** - The onboarding questions and the profile template.
- **`references/research.md`** - How to find companies and people, and what counts as a good hook.
- **`references/writing.md`** - Email structure, length limits, a list of phrases to avoid, a self-check.

### Scripts

Small Python tools for the parts that must be exact. They print JSON and have tests.

- **`scripts/leads.py`** - The lead file: add, update, list, and the check that stops you pitching a company twice. Writes are atomic and keep a backup.
- **`scripts/email_guess.py`** - Turns a name and a domain into likely addresses. Learns the company's pattern from real colleague addresses, and checks that the domain accepts mail.
- **`scripts/enrich.py`** and **`scripts/providers/`** - The slot where a paid email provider plugs in. The default provider is the free guesser.

### Adding a paid email provider

Create `scripts/providers/<name>.py` with:

```python
def enrich(company, domain, person, known):
    return {"email": "...", "confidence": "...", "source": "<name>"}
```

Then set `~/.outreach/config.json` to `{"provider": "<name>"}`. Nothing else changes.

## Philosophy

- **Specific or silent** - A real, sourced fact or no email. Never invented flattery.
- **You stay in control** - One checkpoint before the expensive work, and drafts instead of sends.
- **Judgment for Claude, bookkeeping for code** - Choosing leads and wording belongs to the model. Dedupe, CSV safety and address patterns belong to tested scripts.
- **Say what you don't know** - Guessed addresses are flagged. Unconfirmed claims are marked.

## Responsible use

Cold email is regulated. You are the sender, so you are responsible for following the rules where you and your recipients are, such as CAN-SPAM in the US, GDPR and PECR in Europe and the UK, and CASL in Canada. In practice:

- Say who you are and why you are writing. Don't disguise the sender or the subject.
- Offer a clear way to opt out, and honor it. Don't contact someone twice after they decline.
- Use real, relevant business contacts. Don't buy or scrape bulk lists.
- Send small batches and read every draft. Guessed addresses can bounce, and too many bounces hurt your domain's reputation.

Outreach only looks at publicly available information and never sends email, but nothing in it makes a message compliant for you.

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md). Agents working in this repo should read [AGENTS.md](AGENTS.md) first.

## Updating

```bash
cd outreach-skill && git pull && .venv/bin/pip install -r requirements.txt
```

The skill is installed as a link to this folder, so a pull is all it takes. See [docs/RELEASE-NOTES.md](docs/RELEASE-NOTES.md) for what changed.

## License

MIT License - see [LICENSE](LICENSE) for details.

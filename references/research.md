# Research guide

## Finding companies (Step 1)

- Turn the brief + ideal customer into 3–5 different search queries. Vary the angle: industry lists ("top logistics SaaS startups 2026"), funding news ("raised Series A logistics"), directories (Crunchbase, YC company list, Product Hunt), job boards (companies hiring for a role your product replaces or supports).
- For each candidate, open its website to confirm what it does and that it's still operating. Record the canonical domain.
- Write a fit reason that ties the company to a specific line of the profile. "Logistics startup" alone isn't a fit reason. "Runs a freight marketplace, so it reconciles carrier invoices by hand: our core pain" is.
- **Already-does-it check.** While you have the company's site, channel or product pages open, note whether they already do what the profile's product does, or already use a vendor for it (featured clips on an episode page, an in-house team, a named tool). Write it into the fit reason, and flag it at the checkpoint. A partial overlap (timestamps but no vertical clips) is not a reason to drop the lead, but the email must acknowledge it (see `references/writing.md` → "Overlap"). A full overlap with an incumbent vendor is a weak fit: suggest dropping it.
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

**Scale facts** (episode count, episode length, team size, audience size) are weaker than events but still count, with one condition: the email must tie the fact to the pain ("1,900 episodes is a lot of footage to clip by hand"). A scale fact that isn't tied to the pain is not a hook. Treat every lead the same way: if one lead qualifies on a scale fact, so does another.

Rules:
- Dated hooks: use the date only if the event is within the last ~6 months. Older than that, state the fact without the date, or find a fresher one. Never write "went up in May" about a six-month-old item.
- Every hook needs a source URL. Store hooks and their URLs in the same order; they're saved `|`-separated, so never put a literal `|` inside a hook.
- Aim for 2–4 hooks per lead. The email uses the strongest one; the rest are backup. One qualifying hook is enough to proceed.
- If nothing qualifies, set `status=no-hook`. Don't write a generic email.

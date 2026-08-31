# Daily World News → Snapchat

Every morning: pulls world-news RSS, has Claude pick and summarize the top stories,
renders them as 1080×1920 Story cards, and posts them to your Snapchat Public Profile.
Runs on GitHub Actions, so there's no server to maintain and nothing for you to do daily.

```
RSS feeds ──▶ Claude (rank + summarize) ──▶ Pillow (1080×1920 cards) ──▶ Snapchat Story
```

---

## Setup (about 30 minutes)

### 1. Snapchat Public Profile

A personal Snapchat account **cannot** be posted to by any API. You need a Public
Profile, which is free: in the Snapchat app go to **Profile → Settings → Public Profile**
and create one. This is the account the bot will post to.

### 2. A posting provider

Snapchat's own Public Profile API is allowlist-only — you'd need a Snap business
organization, an OAuth app, and a Snap contact to approve it. Faster route: a provider
that's already approved and resells access. This project uses **Ayrshare**
(`https://www.ayrshare.com`); Late and Zernio expose near-identical endpoints if you
prefer one of those — you'd only change the two functions under section 4 of `news_bot.py`.

Sign up, connect your Snapchat Public Profile in their dashboard, and copy your API key.

### 3. Anthropic API key

Get one at `https://console.anthropic.com`. Cost for this job is small — a few
cents a day at most, since it's one short request per run. Switch
`CLAUDE_MODEL` to `claude-haiku-4-5-20251001` to make it cheaper still.

### 4. Push this repo and add secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|---|---|
| `ANTHROPIC_API_KEY` | from the Anthropic console |
| `AYRSHARE_API_KEY` | from your Ayrshare dashboard |

### 5. Test before you let it loose

Locally, with no keys needed for rendering:

```bash
pip install -r requirements.txt
DRY_RUN=1 ANTHROPIC_API_KEY=sk-... python news_bot.py
open out/          # inspect the cards it would have posted
```

Then in GitHub: **Actions → Daily news to Snapchat → Run workflow**, with
*dry run* ticked. Download the `cards` artifact and check the output. Untick it when
you're happy, and from then on it runs on its own at 06:30 UTC daily.

---

## Story-to-Snapchat cost-control operation

The long-form Story workflow uses a stricter cost model than the daily-news bot.
Editorial generation is revision-scoped and fail-closed: a normal revision may reserve
at most one paid editorial model call. An approved brief is cached only after the
deterministic editorial-quality gate passes.

GitHub **Story to Snapchat** dispatch exposes three operation modes:

- `auto` — reuse an `EDITORIAL_LOCKED` cache when present; otherwise allow the one
  guarded editorial call for that revision.
- `visual_only` — require a locked cached brief and make zero editorial-model calls;
  approved visual slots are reused and only failed slots reopen the visual ladder.
- `regenerate_editorial` — explicit paid regeneration only. Supply a new
  `regeneration_nonce`; reusing the same nonce is idempotent and does not buy the
  revision twice.

Keep `post=false` / `POST_TO_SNAPCHAT=0` during verification. The child renderer also
suppresses intermediate Telegram albums; only a final `READY` or genuine `REVIEW`
candidate is eligible, and unchanged deck hashes are deduplicated.

Local reporting is read-only and makes no API calls:

```bash
python story_cost_report.py --last 10
```

The report includes paid editorial calls, cache hits, visual-only runs, blocked second
calls, estimated cost when token prices are configured, and final READY/REVIEW/BLOCKED
states.

The safe 10-category control-plane proof also uses no external APIs and never posts:

```bash
POST_TO_SNAPCHAT=0 python story_cost_pilot.py --output /tmp/story-cost-pilot.json
```

This pilot proves call/cache mechanics only; it deliberately does **not** claim that its
fixture stories have been evaluated for publication quality. Run a paid editorial pilot
only after reviewing the expected budget.

For a bounded publication-quality check, manually dispatch **Three Story Cost Pilot**.
It processes Riyadh, SAMA, and Madam C. J. Walker sequentially in guarded `auto` mode,
uploads every available frame plus a three-story cost report, and cannot publish because
both `POST_TO_SNAPCHAT=0` and `DRY_RUN=1` are fixed in the workflow. It has no schedule.

---

## Tuning

| Env var | Default | What it does |
|---|---|---|
| `STORIES_PER_DAY` | `3` | How many cards per Story |
| `LOOKBACK_HOURS` | `30` | How far back a headline can be |
| `CLAUDE_MODEL` | `claude-sonnet-5` | Model used for editing |
| `DRY_RUN` | unset | Any non-empty value skips posting |

**Feeds** — edit the `FEEDS` list at the top of `news_bot.py`. Any RSS or Atom URL works.
**Editorial voice** — `SYSTEM_PROMPT` is where you set what counts as interesting and
how the summaries read. This is the highest-leverage thing to tweak.
**Look** — colours and fonts are the constants near the top; the layout is `render_card`.

## Things worth knowing

- **The schedule is UTC.** `30 6 * * *` is 09:30 in Riyadh, 07:30 in London.
- **Feeds go down.** A failing feed is logged and skipped; the run aborts rather than
  posting if fewer than 5 items come back in total.
- **Accuracy.** The prompt tells Claude to stay within what the headline and blurb say,
  but it is still a model summarizing a summary. If you're posting under your own name,
  it's worth reading the artifact for the first week before trusting it unattended.
- **Spotlight needs video.** Stories accept images, which is what this posts. If you want
  Spotlight reach later, you'd render a short MP4 instead — same pipeline, different
  render step.

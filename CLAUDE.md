# daily-news-snap

Three bots that build Arabic cards and post them to a Snapchat Public Profile,
run by GitHub Actions on a schedule. Everything is Python + Pillow, no framework.

## The bots

| File | What it does | Schedule (KSA) |
|---|---|---|
| `news_bot.py` | One business/tech news story per run, as a single card | 07:00, 12:00, 17:00, 21:00 |
| `topic_bot.py` | One researched explainer per day, chosen by a scoring system | 09:00 |
| `story_bot.py` | One narrative told across 6 frames | Thu + Sat 20:00 |
| `ask_card.py` | Asks followers what they want covered | manual only |

`news_bot.py` is also the shared library: rendering, fonts, Arabic shaping,
image sources, posting, Telegram. The other bots import from it. **If you change
a shared function, check all three bots still import cleanly.**

## Content files (edit these, not the code, to change what gets posted)

- `topics.txt` — ~275 explainer topics, optional `| trigger, keywords` per line
- `seasons.txt` — 46 seasons: Ramadan/Hajj (hijri), monthly payday cycle,
  exhibitions, a weekly football slot. Format: `## name | spec | before | after`
- `stories.txt` — 74 narrative subjects
- `requests.txt` — topics followers asked for; these outrank everything
- `voice.txt` — sample lines the writing should imitate

## Rules that must not be broken

1. **Every card and every frame has a picture.** No text-only output. If a
   frame can't get one, the story is skipped rather than published bare.
2. **No generated images for news or stories.** Generation is topic-cards only,
   last resort, and always labelled `صورة مولّدة بالذكاء الاصطناعي`.
3. **No misleading photos.** Blocklists reject weapons/military/police/protest
   imagery; foreign landmarks are penalised on Saudi stories; logo cards and
   infographics are rejected by a pixel check.
4. **Numbers carry a unit, a date and a source.** There is a checker that warns
   about bare numbers — don't remove it.
5. **Arabic script for Saudi and Arab names** (مرايا، أرامكو، نيوم), Latin for
   foreign companies (NVIDIA, OpenAI, CNBC).
6. **Latin digits** (2027, not ٢٠٢٧). The sanitizer enforces this.

## Design

Light theme: cream `#EEE8E3`, blue text `#183861`, deep emerald `#0B3D2E` for
the bar and label, red `#B71C2C` for the single takeaway line. Font: Almarai
from `fonts/`. Cards are 1080×1920 PNG.

**Before swapping the font**, render a card and look at it. Cards are shaped by
libraqm on the runner and by `arabic-reshaper` everywhere else, and the two
paths ask the font for different glyphs. `_shaping_gaps()` in `news_bot.py`
checks this and falls back to bundled `NotoNaskhArabic` rather than publish
boxes — if you see that fallback in the log, the font you chose is the problem.

Card header: short bar top-right, label beneath it (`ملخص تنفيذي - خبر` for
news, `- معلومة` for topics, `- قصة` for stories), then centred headline,
photo, body, red takeaway, thin rule, sources.

## Image sources, in order

local `images/` folder → article's own photo → SPA (cc.spa.gov.sa) →
Wikimedia Commons → Library of Congress → Openverse → Pexels → generated
(topic cards only). Each is filtered for safety, relevance and Saudi context
where appropriate.

Commons and LoC need no key. Commons does two lookups per keyword — a direct
file search, and the lead image of any matching Wikipedia article (`ar` then
`en`), which is where portraits of people live. Its credit line comes from the
file's own licence metadata and is not optional. LoC is public-domain
photography, useful for historical subjects; only items whose rights advisory
says "no known restrictions" are used, because `access_restricted` is
unreliable. **Both reject the project's browser-style `USER_AGENT`** — they
need `PUBLIC_API_UA`, which names the project and a contact.

Each source tries its queries narrowest first and stops at the first result
scoring `MIN_PHOTO_SCORE` or better. **That stop threshold and the publish
threshold must stay the same number** — stopping below the publish bar means
giving up while holding something you're about to reject.

## Posting

`POST_PROVIDER=bundle` uses bundle.social (custom plan: 150 posts/month).
`POST_TO_SNAPCHAT=0` is hybrid mode — build and commit the card, don't post.
Telegram delivers every finished card to the phone either way.

What actually posts:

| Workflow | Posts to Snapchat |
|---|---|
| `news_bot.py` | the 07:00, 17:00 and 21:00 KSA runs |
| `news_bot.py` | **not** the 12:00 KSA run (`0 9 * * *`) — hybrid |
| `topic_bot.py` | yes, the 09:00 KSA run |
| `story_bot.py` | no — hybrid |
| any manual dispatch | no |

daily.yml picks that per-run with `github.event.schedule`. A manual dispatch
sets no schedule, so it falls through to hybrid — those are nearly always
tests, and a test that posts to the profile is expensive to undo.

`MONTHLY_POST_LIMIT` is a self-imposed cap counted in `state/quota.json`, one
file shared by all three bots. When it blocks a post the card still goes to
Telegram via `deliver_unposted()` — **a run that builds a card must never end
without saying so somewhere.** Two bots now post, so all three workflows must
name the **same** cap (145) — the file is shared but each passes its own
limit, and mismatched numbers mean whichever is lowest silently stops the
others. Expect roughly 120 posts a month against that 145.

## Conventions

- Comments explain **why**, not what. Especially where a value was tuned
  because of a real failure — say what the failure was.
- Prompts live in `SYSTEM_PROMPT` strings and are in Arabic. They carry worked
  ✗/✓ examples drawn from cards that actually went wrong. Keep that pattern.
- Every env var has a fallback for empty values — GitHub passes `""` for an
  unset repo variable, which would otherwise disable a filter silently.
- Before finishing: `python -m py_compile` each bot, and confirm
  `import news_bot, topic_bot, story_bot, ask_card` works. If you touched
  anything the renderer uses, also render a card and **look at it** — compiling
  and importing cannot see a card full of empty boxes.

## Things that have bitten us

- A shared function changed in `news_bot.py` without uploading it broke
  `topic_bot` with an ImportError. They move together.
- `<cite index="...">` markup from web search leaked into card text.
- Openverse blocklist matched `war` inside `warehouse`, rejecting everything.
- `find_all_photos` was capped at 4 frames while the renderer drew 6.
- Duplicate keys in a workflow `env:` block fail the whole workflow file.
- `git push` from three bots on one branch loses races. Push through
  `_git_push()`, which rebases and retries — a bare push raised
  `CalledProcessError` and killed the run after the card was already built.
- Openverse and Pexels stopped searching at a hardcoded score of 10 but
  published against `MIN_PHOTO_SCORE`. Raising that variable — the obvious
  move after a bad photo — made the search *worse*: it still stopped at the
  mediocre match, rejected it, and with `REQUIRE_PHOTO=1` posted nothing.
- Almarai and Cairo have no **isolated** forms for ا إ أ ء د ذ ر ز و ة ي, so
  off the runner every one of them drew as a box. The glyph warning couldn't
  see it: it checked the text *before* reshaping. Both are fixed — the reshaper
  is configured with `use_unshaped_instead_of_isolated`, and the warning now
  runs on the shaped string. Keep any new check on the shaped string.

# daily-news-snap

Three bots that build Arabic cards and post them to a Snapchat Public Profile,
run by GitHub Actions on a schedule. Everything is Python + Pillow, no framework.

## The bots

| File | What it does | Schedule (KSA) |
|---|---|---|
| `news_bot.py` | One business/tech news story per run, as a single card | 07:00, 12:00, 21:00 |
| `topic_bot.py` | One researched explainer per day, chosen by a scoring system | 09:00 |
| `story_bot.py` | One narrative told across 6 frames | 14:00 daily |
| `ask_card.py` | Asks followers what they want covered | manual only |
| `publish_cards.py` | Posts a story already built, unchanged | manual only |

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

## Stories

The prompt builds six beats: العالم والمشكلة (no protagonist, ≤1 proper noun),
البطل (the protagonist arrives, first portrait), المنعطف, الثمن, النتيجة,
الحكم. The closing frame passes a verdict — on the protagonist, resting on
what won't change back, no setbacks or footnotes, and never a restatement of
the title. Per frame: at most two new proper nouns, each with a descriptor;
one fact per sentence; neutral verbs (أتلفت لا سحقت). `punch` is an optional
red line under the body — one or two per story, the closing frame is its best
home. Each frame carries its own `image_keywords` (things, not concepts —
"Shekou industrial zone", never "Cultural Revolution"; for historical beats,
the thing plus its place or year — "Dammam No. 7 1938", never "Aramco",
whose archive photos are its modern jets) and `image_keywords_ar`
(the Arabic name is often the only one the archive knows).

Every story photo passes a **vision gate** before it ships: Haiku looks at
the downscaled candidate next to the frame's own text and answers whether it
really shows the subject — the automated version of the glance that kept
catching certificates, charts and perfume vials that metadata scoring
accepted. The verdict is three-way: نعم ships, لا moves the search on, and
محايدة (a real photograph that misleads no one but proves nothing) is banked
and used only if no نعم ever arrives — the first gated run returned لا for
every candidate of every frame and killed the whole story after the research
was paid for. Parse the verdict word loosely: Haiku dresses it in bold or
quotes, and a strict startswith once read every approval as a rejection.
Fail-open: no key or an API error lets the photo through with a loud log
line. `VISION_GATE=0` disables it.

Person-led stories are gated before the research call: no free portrait means
skip, recorded in `state/stories_skipped.json` for `STORY_SKIP_DAYS` (14) —
deliberately shorter than the 60-day publish cooldown, because a missing
portrait is not a verdict on the story. `choose_story()` hashes the date so a
daily cadence doesn't walk down one section of `stories.txt`. No photo repeats
within a story; repeats are a loud last resort.

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

**Curated logos** (stories only): `images/logos/<slug>-<era>.png`, where era
is a 4-digit year or `current`; `index.json` maps slugs to Arabic/Latin names
for matching. A logo is the fallback between the widened search and the loud
repeat — frame 1 takes the oldest era, the closing frame takes `current`, the
protagonist frame (2) never takes one. Curated files bypass the logo pixel
check and the vision gate **by provenance** (they never pass through either);
a logo arriving from archive search is still rejected exactly as before —
filler on a news card, but an era-matched curated logo on a story frame is a
deliberate editorial choice. The folder is self-filling for CURRENT logos
(`LOGO_AUTO_CURRENT`, default on): when the ladder reaches the logo rung and
the slug has no file, story_bot fetches the subject's current logo through
`logo_fetch.py`'s title-verified article-infobox path (never search; non-free
wiki-hosted files are accepted, but the file title must carry the subject's
name) and commits it — one fetch per company ever. The slug comes from the
first story-level keyword: lowercased, punctuation stripped, spaces to
hyphens; collisions are first-writer-wins. Historical/era logos stay manual —
no mechanism can verify a file labelled 1938 is the 1938 mark — via
`logo_fetch.py` candidates sent to Telegram; renaming one into the folder is
the approval.

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
| `news_bot.py` | the 07:00 and 21:00 KSA runs |
| `news_bot.py` | **not** the 12:00 KSA run (`0 9 * * *`) — hybrid |
| a manual news run | only when the **post** input is ticked |
| `topic_bot.py` | yes, the 09:00 KSA run |
| `story_bot.py` | no — hybrid, so six frames get read before they go out |
| any manual dispatch | no |

About 122 posts a month, under the 145 cap and the plan's 150. A story counts
as one post however many frames it has — it is hybrid today, so it costs
nothing against the quota.

News selection runs three tests in order: **الأهمية** (does the reader know
the company, does anything change), **القرب** (does the effect reach Riyadh in
one sentence), **التوقف** (would a thumb stop on it). The third rejects the
true-but-expected — routine results, incremental updates, meetings held — and
says plainly that the stopping comes from the news, not from the wording. A
teaser headline on an ordinary story loses the reader twice. Saudi economy,
Saudi/Gulf real estate and Saudi travel are named beats; labour news (أعداد
العمالة، التوطين، تصاريح العمل) is excluded — in news only, an explainer on
employment rights is still topic_bot territory.

A story is hybrid, so it is read before it goes out. To publish the frames you
reviewed, dispatch **Publish built cards** — `publish_cards.py` posts what is
already in `cards/`, with no research call and no re-rendering. Re-dispatching
`story.yml` would *not* do this: it researches again and produces different
frames. **Name the stamp** unless you are sure nothing newer landed: blank
picks the newest story, and a scheduled run may have built one since the one
you reviewed. `cards/{stamp}-story.json` is the sidecar: caption, title, and
the authoritative frame list the publisher posts. The six frames ship as one
MP4 (ffmpeg comes from the `imageio-ffmpeg` wheel — **runners have no ffmpeg
on PATH**), ten seconds a frame, last frame one second short — see the bitten
list for why every word of that sentence is load-bearing.

daily.yml picks that per-run with `github.event.schedule`. Breaking news goes out by dispatching that workflow with **post** ticked — that is what the retired 17:00 slot was traded for. Ticking **dry run** as well wins: the run returns before posting. A manual dispatch
sets no schedule, so it falls through to hybrid — those are nearly always
tests, and a test that posts to the profile is expensive to undo.

`MONTHLY_POST_LIMIT` is a self-imposed cap counted in `state/quota.json`, one
file shared by all three bots. When it blocks a post the card still goes to
Telegram via `deliver_unposted()` — **a run that builds a card must never end
without saying so somewhere.** Every workflow that can post — daily, topic,
story, publish — must name the **same** cap (145): the file is shared but each passes its own
limit, and mismatched numbers mean whichever is lowest silently stops the
others. Expect roughly 120 posts a month against that 145.

## Conventions

- Comments explain **why**, not what. Especially where a value was tuned
  because of a real failure — say what the failure was.
- Prompts live in `SYSTEM_PROMPT` strings and are in Arabic. They carry worked
  ✗/✓ examples drawn from cards that actually went wrong. Keep that pattern.
  Some rules span bots and must stay in sync when edited: comparing figures
  (components of one index aren't rivals) is in all three; Saudi regulation
  (name the rule that governs the advice) is in topic and story only.
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
- `choose_story()` picked with `ordinal % len(fresh)`. The ordinal advances by
  one a day, so consecutive days took consecutive lines — and `stories.txt` is
  grouped by section, so a daily story walked down one theme: seven
  businessmen, then seven cities. It hashes the date now. Invisible at two a
  week, dominant at one a day.
- A portrait found by Commons *search* must carry the name in the FILE TITLE,
  not just somewhere in the description. Anyone by that name in a caption was
  enough before, which offered a US embassy reception for "Robert Plath" and a
  football match for "Jack Bogle". A photograph of the wrong person is the one
  failure nothing downstream catches. Portraits from a title-verified article
  lead are reliable; the search fallback is not, and is now held to the title.
- Award documents are not named "certificate" on Commons. They are "Genius
  Nikola Tesla Award", "Diplôme de Participation", "Honorary Charter", "Order
  of the White Lion awarded to X". Three reached story frames after
  "certificate" was blocked. `_DOCUMENT_RE` blocks the noun "award" but spares
  "award-winning", which is an adjective for a real building.
- Commons categories classify the SUBJECT, not the picture. Judging safety by
  them rejected a headshot of someone who had once served, on 'Army' sitting
  in his biography. Safety now reads title and description; categories are
  checked only against words that describe a scene and never a career — and
  in the plural, because that is how Commons names them.
- Two story runs fired in one KSA hour (GitHub replays stale crons after an
  edit) and left two full frame sets under one stamp. A glob then stitched a
  story out of both runs — the first publish attempt shipped that mix to
  ffmpeg. The sidecar now records the run's own frame list and the publisher
  posts exactly that; with duplicates and no sidecar it refuses.
- Two stories in one KSA hour used to overwrite each other's cards: the
  filename digest was `md5(stem)` and `ksa_stamp()` only resolves to the hour.
  It hashes the file's bytes too now — keep it that way, and keep it
  idempotent so republishing reuses the name rather than adding a copy.
- bundle.social allows ONE upload per Snapchat post — "Max 1 upload(s)
  allowed". The six-upload story path had never run live (story was always
  hybrid), so it failed on the first real publish. Stories therefore post as
  one MP4, FRAME_SECONDS per frame, built by publish_cards.py. Snapchat then
  splits that video into 10-SECOND snaps: FRAME_SECONDS must stay 10 so each
  snap is exactly one frame — at 8s the segments straddled frames and viewers
  tapping through skipped one entirely. A video at exactly 60s gets its tail
  shaved by Snapchat, so the last frame gives up TAIL_MARGIN (1s) and the
  video runs 59s. And ffmpeg 7's concat demuxer is a minefield for stills:
  repeating the last file adds a full extra cycle, and the final entry is
  held for the PREVIOUS entry's duration, not its own — [10,10,9] plays 30s,
  measured. publish_cards emits every frame as repeated 1-second entries,
  which sidesteps all of it; keep durations whole seconds.
- news_bot's Claude call had a fixed 120s timeout and started at 8000 tokens.
  Eight candidates in Arabic overran that, so it retried at 16000 and the
  longer generation blew the timeout — and a socket timeout is not an
  HTTPError, so it escaped the handler and killed the run. Timeouts scale
  with the budget now and are retried. Keep the API timeout × 2 under the
  workflow's `timeout-minutes`.
- `git push` from three bots on one branch loses races. Push through
  `_git_push()`, which rebases and retries — a bare push raised
  `CalledProcessError` and killed the run after the card was already built.
- Openverse and Pexels were the only two photo sources that never ran
  `looks_like_a_graphic` on their downloads — article, SPA, Commons and LoC
  all did. The one unchecked path delivered the same green chart to two
  stories, sailing past a pixel check that had just been strengthened for
  paths that never call it. Every fetcher checks its bytes now; keep it that
  way when adding a source.
- Openverse and Pexels stopped searching at a hardcoded score of 10 but
  published against `MIN_PHOTO_SCORE`. Raising that variable — the obvious
  move after a bad photo — made the search *worse*: it still stopped at the
  mediocre match, rejected it, and with `REQUIRE_PHOTO=1` posted nothing.
- Almarai and Cairo have no **isolated** forms for ا إ أ ء د ذ ر ز و ة ي, so
  off the runner every one of them drew as a box. The glyph warning couldn't
  see it: it checked the text *before* reshaping. Both are fixed — the reshaper
  is configured with `use_unshaped_instead_of_isolated`, and the warning now
  runs on the shaped string. Keep any new check on the shaped string.

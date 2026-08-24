# daily-news-snap

Three bots that build Arabic cards and post them to a Snapchat Public Profile,
run by GitHub Actions on a schedule. Everything is Python + Pillow, no framework.

## The bots

| File | What it does | Schedule (KSA) |
|---|---|---|
| `news_bot.py` | One business/tech news story per run, as a single card | 07:00, 12:00 |
| `breaking_watch.py` | Breaking-news watcher (08:00–19:30, every 30 min) + 20:00 fallback news post | see breaking.yml |
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
- `stories.txt` — ~122 narrative subjects in pools: a `# @pool: saudi` /
  `# @pool: general` marker assigns every following line until the next
  marker; lines before any marker are general. A `logo:domain.com` token in
the tail declares the subject's logo identity — the ONLY thing the
auto-logo fetch accepts (title-derived slugs are dead; the article must
reference the domain). Optional `| alias, alias` per
  line: the archive's names for the subject (stage names, business names,
  transliterations) — the portrait pre-check and the research call try
  them, because archives catalogue people under names the story may not use
- `requests.txt` — topics followers asked for; these outrank everything
- `voice.txt` — sample lines the writing should imitate

## Rules that must not be broken

1. **Every news and topic card has a picture.** Story frames prefer one,
   and get a subject-kind fallback ladder — but a frame that exhausts its
   ladder runs **text-only as a deliberate floor** rather than carry a
   faked or misleading image. Text-only is honourable; a wrong image is not.
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
daily cadence doesn't walk down one section of `stories.txt`, and it
retires SUBJECTS, not titles: a used line retires every line sharing its
entity (domain or Latin aliases, matched by key-set intersection) — the
Zain story reselected itself through a sibling line once. 429/529/503
from the API back off exponentially with jitter (4 attempts); a research
failure benches only that candidate for the run — never marked used or
skipped — and the run moves on, exiting non-zero only when the whole run
produced nothing. Scheduled
runs draw 4 saudi + 3 general a week (`SAUDI_PER_WEEK`/`GENERAL_PER_WEEK`,
should sum to 7; counts in `state/story_mix.json`, ISO-week reset), picking
whichever pool is furthest behind its ratio; an exhausted pool borrows from
the other — loudly, crediting the pool the story actually came from —
because a skipped day is worse than an imperfect ratio. Manual STORY= runs
bypass the mix entirely. No photo repeats
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

`state/photos_used.json` is a cross-run cooldown shared by all three bots:
an accepted card photo's perceptual digest is registered (pushed at once, so
the 07:00 run's photos bind the 09:00 run) and re-fetching it within
`PHOTO_REUSE_DAYS` (7) is rejected mid-search like a within-story repeat.
Exempt: the local `images/` library and curated logos — so a recurring
subject (Tadawul milestones, budget days) is best served by dropping one
good photo into `images/`, which guarantees relevance and sidesteps the
cooldown by design. If every source exhausts and only a recent photo
remains, it ships with a loud ⚠️ prefix on the Telegram delivery — a
repeat is a flaw, a dead run is worse.

**Story frame ladder** (revised twice in 2026-08; this is current): a
WRONG photo is worse than a logo, but a bare beige frame is a
scroll-past. Per frame: the frame's OWN keywords, relevance-verified →
(country frames: the curated flag from `images/flags/<iso>.png`) → the
STORY SUBJECT'S logo as the PRIMARY fallback for every kind, person
frames included — curated, or auto-fetched only when the line declares
`logo:domain.com` (identity and cache key; the matched article must
reference the domain) — capped at `LOGO_MAX_FRAMES` (2): one mark
papering 4/6 frames is a fail, beyond the cap frames go designed
text-only —
→ a gate-verified on-topic general photo from the story-subject pool
(person-frame names stripped; never for person frames) → text-only as the
LAST resort, rendered with a
large low-contrast brand watermark in the photo zone so it reads
designed, not broken. Each frame logs its tier. The neutral bank, the
recent-photo rescue and the in-story repeat stay removed. If more than
`STORY_MAX_BLANK_FRAMES` (2) frames end with no visual, the story is
SKIPPED, recorded in `state/stories_skipped.json` with reason
`no_logo_insufficient_visuals` (same review queue as portrait skips),
Telegram is told, and the run advances to the next eligible story —
never a mostly-blank deck, never a lost slot. TYPOGRAPHIC frames count
as illustrated (owner decision): a photoless frame whose text carries a
strong figure — a number with unit, a year — sets it huge in the photo
zone over the faint watermark; such frames don't count toward the blank
budget. `preflight_stories.py` (manual) checks every line's illustration
coverage offline — portrait for person lines, logo identity (curated or
`logo:domain.com`-fetchable), or an archive probe — writes verdicts to
`state/story_coverage.json`, and `choose_story` skips recorded failures:
they are the curation worklist (add a logo domain, drop a curated file,
or retire the line). Unchecked lines are never blocked. Dropping a curated logo
into `images/logos/` un-skips a story; manual rescue is opt-in, not the
normal path. Story GENERATION is OFF (2026-08: every generated frame was
junk — the fake desert Mercedes closed the SAVOLA deck); the code stays
dormant behind `ALLOW_STORY_GENERATION`/`ALLOW_GENERATED`, both "0" in
code default and story.yml.

**Pinterest is declined as a source** (owner asked; recorded so it isn't
re-proposed): its content is overwhelmingly copyrighted re-pins with no
reuse licence — publishing them breaks the licence-clean rule the whole
pipeline enforces; its API manages your own pins, not third-party image
search, so it cannot slot into the ladder; and its mislabeled /
watermarked / AI-generated rate is the opposite of the title-verified,
licence-checked discipline used everywhere else. Wanting more real-photo
coverage means more CURATED `images/` seeds for recurring beats, not an
unlicensed source.

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
| `news_bot.py` | the 07:00 KSA run |
| `news_bot.py` | **not** the 12:00 KSA run (`0 9 * * *`) — hybrid |
| a manual news run | only when the **post** input is ticked |
| `topic_bot.py` | yes, the 09:00 KSA run |
| `breaking_watch.py` watcher | at most ONE confirmed breaking card a day, the moment it lands |
| `breaking_watch.py` 20:00 KSA | posts the day's strongest story — unless a breaking card posted today, then hybrid |
| `story_bot.py` | no — hybrid, so six frames get read before they go out |
| any manual dispatch | no (breaking.yml's manual dispatch defaults dry_run ON) |

The evening is two-tier, fully documented in breaking.yml: a watcher every
30 minutes 08:00–19:30 KSA — Haiku classifies with two budgeted searches,
default refusal — and a confirmed event is PINNED into news_bot
(`PINNED_EVENT`), which re-verifies with search through the normal prompt
and ABORTS without posting if it can't confirm. `state/breaking.json`
holds the one-per-day cap, the cycle lock, and the event fingerprint that
stops one event posting twice in different words; quiet cycles write
nothing. The script guards its own time window because stale crons replay.
Breaking OR the 20:00 fallback posts each evening, never both. Every
watcher cycle sends exactly one Telegram line — quiet (⚪️ with the
classifier's reason), error (🔴, never swallowed), or the breaking
card itself — because a working watcher and a dead one must never look
the same (both used to look like nothing). Dry-run news cards are sent
too (🟡 held, with how to approve): the artifact steps keep files 7
days in Actions, and a held card only on disk is a card never seen.

About 91 posts a month (07:00 news + 09:00 topic + one evening card),
under the 145 cap and the plan's 150. A story counts
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

daily.yml picks that per-run with `github.event.schedule`. Breaking news is
automated now (the watcher above); dispatching daily.yml with **post** ticked
remains the human override. Ticking **dry run** as well wins: the run returns
before posting. A manual dispatch
sets no schedule, so it falls through to hybrid — those are nearly always
tests, and a test that posts to the profile is expensive to undo.

`MONTHLY_POST_LIMIT` is a self-imposed cap counted in `state/quota.json`, one
file shared by all three bots. When it blocks a post the card still goes to
Telegram via `deliver_unposted()` — **a run that builds a card must never end
without saying so somewhere.** Every workflow that can post — daily, topic,
story, publish, breaking — must name the **same** cap (145): the file is shared but each passes its own
limit, and mismatched numbers mean whichever is lowest silently stops the
others. Expect roughly 91 posts a month against that 145.

## Conventions

- Comments explain **why**, not what. Especially where a value was tuned
  because of a real failure — say what the failure was.
- Prompts live in `SYSTEM_PROMPT` strings and are in Arabic. They carry worked
  ✗/✓ examples drawn from cards that actually went wrong. Keep that pattern.
  Some rules span bots and must stay in sync when edited: comparing figures
  (components of one index aren't rivals) is in all three; Saudi regulation
  (name the rule that governs the advice) is in topic and story only;
  government finance (report the number and its source, never a verdict on
  the state's performance or pace, no taxpayer framing, one quarter is not
  a trend) is in all three.
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
- The Mrsool story put a stranger's face on frame 2, captioned as the
  founder. The pre-check verified a real portrait EXISTED (title-verified),
  then the render fetched AGAIN through generic caption-matching search and
  took a different photo. Second wrong-person incident. The rule now:
  **identity is not subject to widening** — widening may relax relevance,
  never identity. Person frames fetch only through provenance that verifies
  who is in the picture (the cached pre-check portrait, images/, or
  fetch_commons_portrait's title-verified routes); the generic search,
  widened pass, neutral bank and recent-photo rescue are all forbidden on
  them, and the fallback is the company logo (allowed on the hero frame for
  exactly this case) then repeat/text-only. Never a caption-matched face.
- The same photo shipped on multiple cards (a corniche on three posts) and
  on two frames of ONE story (Mrsool 1/2): dedup lived only inside one
  story run. `state/photos_used.json` is the cross-run cooldown now —
  perceptual digests, all bots, pushed immediately; exempt: `images/`,
  curated logos, flags, generated images. Exact-digest dedupe cannot see a
  re-CROPPED variant of the same scene — confirmed live when one orange
  Riyadh skyline landed on frames 1, 5 AND 6 of the Mrsool deck as three
  crops with three digests. Near-dup detection is hamming distance on the
  same ahash now (`PHOTO_HAMMING_THRESHOLD`, 8 of 256 bits), applied to
  both the within-story seen set and the cross-run registry.
- Photoless frames used to fall to one blind rule. The subject-kind ladder
  keys the fallback on what the MODEL says the frame is about; an unsure
  model says "abstract", whose floor is text-only. Flags are for
  place_country ONLY (a city never borrows its country's flag), and
  abstract is the only kind that may reach generation — gated, labelled,
  never registered in the cooldown.
- Mrsool sponsored Al-Nassr, and the sponsor's dressing room and stadium
  landed on three frames of the delivery-app story — adjacent entities in
  the research context (sponsors, partners, venues) leak into image
  keywords, and archive files genuinely NAMED after the sponsor ("Mrsool
  Park") pass every name filter honestly. The prompt rule: a keyword names
  what THIS frame's text is about — the story's subject, never its
  sponsor/partner/investor/venue context.
- The SAVOLA logo shipped on the Jameel/Toyota story. The auto-logo rung
  had stored Savola's first Arabic SEARCH TERM («جدة») as an index alias,
  and the matcher checked aliases as substrings of the story's keyword
  soup — so every Jeddah story matched a food company. Logo matching is
  exact identity now: the file's slug or alias must EQUAL a declared
  subject name (story keywords or the line's aliases), a miss NEVER
  borrows another company's cached file, the slug→file pairing is logged
  on every use, and only names carried by the story's own title may be
  written to the index — search vocabulary is not a name.
- A Riyadh Air aircraft shipped in a Zain licensing story: the frame's own
  keywords carried a background entity, and the gate only checked "is this
  a real relevant image", not "is this an image of the SUBJECT". On company
  stories every image query is now bound to the declared subject entity —
  never built from an individual frame's text — the gate is told «القصة عن
  X» and answers لا to anything belonging to another brand, and one correct
  subject image plus logos (capped) plus typographic frames is the whole
  deck. The publisher verifies sidecar indices are exactly 1..N (explicit
  index, never listing order) and refuses gaps or duplicates.
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

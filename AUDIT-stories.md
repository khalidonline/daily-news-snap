# stories.txt portrait-fragility audit — 2026-08-24

Report only; the owner applies reframes. Classifier = the runtime's own
`person_name()`, portrait check = the runtime's own pre-check (library +
title-verified Commons), logo probe = `logo_fetch._article_logo_files`
(dry — does a title-verified infobox logo file EXIST; nothing downloaded).

122 stories · 35 gate as person-led at runtime · **4 fragile**

## Fragile lines (will SKIP at runtime today)

| line (head) | person-led? | portrait? | reframe company | logo obtainable? | recommendation |
|---|---|---|---|---|---|
| عبداللطيف جميل: كيف بدأ من محطة وقود في جدة؟ | yes (real person) | none free | Abdul Latif Jameel | **yes** — `File:Abdul Latif Jameel logo.png`, en article | **REFRAME → Abdul Latif Jameel** (owner already drafting) |
| قصة هنقرستيشن وحرب تطبيقات التوصيل | **false positive** — company reads as a person to the gate | n/a | HungerStation | **no** — article infobox file isn't NAMED "logo", auto-fetch can't see it | REWORD head so the gate skips it (e.g. «قصة تطبيق هنقرستيشن…») + CURATE `images/logos/hungerstation-current.png` |
| قصة التمر السعودي وتحوله لصناعة | **false positive** — a thing, not a person | n/a | — | — | REWORD head (add صناعة/قصة-breaking word the gate knows, e.g. «قصة صناعة التمر السعودي») or seed `images/` with a date-farm photo |
| قصة ربط الريال بالدولار وقصته | **false positive** — a concept | n/a | — | — | REWORD head (the older phrasing «لماذا ارتبط الريال…؟» passed the gate fine — question words defuse it) |

## Person-led lines with portraits (31 — OK, no action)

Steve Jobs · Warren Buffett · Radia Perlman · Shuji Nakamura ·
Jerry Lawson · Hedy Lamarr · Ajay Bhatt · Philo Farnsworth ·
Mary Allen Wilkes · Masaru Ibuka · Malcom McLean · Muriel Siebert ·
Benjamin Graham · Jack Bogle (library) · Amancio Ortega ·
Muhammad Yunus · مدام سي جيه ووكر (library) · Juan Trippe ·
Herb Kelleher · Fred Smith · علي النعيمي (library) · سليمان الراجحي ·
يوسف بن أحمد كانو · صالح الراجحي · محمد بن لادن · صالح كامل ·
plus five company lines the gate mis-reads as people but which PASS
anyway because their brand name resolves an image (مرسول، العثيم،
نادك، ستاربكس/الشايع، نون) — they run, no action needed today.

## Two findings beyond the ask

1. **The gate's false positives are the bigger fragility class.** Three
   of the four fragile lines aren't people at all — 2–4-word Arabic
   heads with no question word read as personal names to `person_name()`.
   At ~400 stories this class will grow faster than real portrait gaps.
   Cheapest durable fix (owner's call, not applied): heads for
   thing/concept stories should carry a question word or a
   `NOT_A_PERSON` noun (صناعة، تطبيق، سوق…) — or extend NOT_A_PERSON
   with تطبيق-like nouns already present (تطبيق IS in the list; the
   هنقرستيشن line lacks any such noun in its head).
2. **The auto-logo probe only sees files NAMED "logo"** — Toyota and
   HungerStation both have infobox logos on Wikipedia, but the files
   aren't named `*logo*`, so `_article_logo_files` returns nothing.
   Companies like NVIDIA/Savola/Jameel worked because their files carry
   the word. If auto-logo misses pile up, the fix is to also accept the
   article's DECLARED infobox image field rather than filename matching
   — noted for a future task, not changed here.

## The reframed Jameel line — confirmed

`قصة عبداللطيف جميل للسيارات ووكالة تويوتا | Abdul Latif Jameel, Toyota Saudi Arabia`
resolves: **Abdul Latif Jameel → `File:Abdul Latif Jameel logo.png`**
(title-verified, en article) — the auto-fetch will obtain it, so the
line won't skip. (Note: "Toyota" alone would NOT resolve — its logo
file isn't named "logo" — so keep "Abdul Latif Jameel" first in the
aliases, as the owner's draft already does.)

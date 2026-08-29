# Saudi Snapchat Editorial Model

Date: 2026-08-29
Status: Approved direction, revised for audience-fit review

## Goal

Make the daily news bot feel native to a primarily Saudi, Arabic-speaking Snapchat audience aged roughly 25–50. The bot should select the story this audience is most likely to stop for, understand immediately, and want to mention or share — while preserving factual accuracy, source discipline, and the account's premium business-aware tone.

The bot should not behave like a miniature business newswire, and it should not behave like a local municipal bulletin. It should behave like a sharp Saudi-interest editor who understands Snapchat and the interests of adults in the 25–50 age range.

## Audience profile

The intended follower is an adult Saudi or Saudi-resident Snapchat user, broadly 25–50 years old.

The editorial model should therefore favor stories with broad relevance to adult life, such as:
- money, financing, banking, prices, housing, major consumer changes
- work, business, careers, major regulation, and economic changes
- technology and AI that affect daily use or work
- travel, aviation, visas, destinations, and major hospitality developments
- major Saudi sports with broad conversation value
- major Saudi entertainment, culture, and national-scale events
- nationally relevant changes in services, transport, education, or daily life

It should not over-index toward youth-only trends, influencer chatter, minor gaming/internet culture, or hyperlocal announcements merely because they are Saudi.

## Core editorial principle

The editorial question is:

> Would a Saudi Snapchat follower aged 25–50 stop because this subject affects their life, involves a name they strongly recognize, surprises them, or gives them something worth talking about?

Conventional newsroom importance is secondary to Saudi audience relevance, provided the story is factual and genuinely newsworthy.

## National relevance, not merely local geography

`saudi_core` means **broad Saudi relevance**, not "anything that happened in Saudi Arabia."

A story should not receive priority merely because it concerns a Saudi city, municipality, district, or local project.

Usually reject or heavily down-rank:
- a new municipal project in one city with little relevance outside that city
- routine road, park, beautification, neighborhood, or local-service projects
- ribbon cuttings and ceremonial openings
- a small local development whose impact is limited to a narrow geographic audience
- routine municipality announcements
- local institutional PR with no national, economic, consumer, or conversation value

A city-specific story may still qualify when its significance is much broader than the city itself, for example:
- a major airport or airline development
- a nationally important mega-event or destination
- a large housing/transport policy with wider implications
- a major development involving a project or place already recognized across Saudi Arabia
- a change likely to affect a large share of residents, travelers, investors, consumers, or businesses

The test is **scale and audience interest**, not the location name.

## Eligible content lanes

The bot may select from six lanes. There is no final-output quota; the strongest qualified story wins.

### 1. Saudi life and major decisions

Eligible examples:
- major government decisions that change daily life
- large regulatory or consumer changes
- nationally meaningful housing, transport, education, or service changes
- meaningful labor-market changes when they materially affect Saudis or residents

Reject routine administrative or hyperlocal announcements.

### 2. Business, money, and consumer impact

Eligible examples:
- interest rates and financing
- oil when the move is material
- major Saudi companies
- prices, fees, subscriptions, mortgages, banking
- major acquisitions, IPOs, or results when the company is widely known

Existing public-finance and numerical-comparison safeguards remain in force.

### 3. Technology

Eligible examples:
- Apple, Google, OpenAI, Snap, TikTok, Samsung, Meta, Microsoft, Tesla, NVIDIA and similarly familiar brands
- major launches and product changes
- AI developments with obvious consumer or work impact
- price, privacy, subscription, policy, or access changes

Minor UI tweaks and obscure startups remain low priority.

### 4. Major sports

Sports is allowed only when the event has broad Saudi conversation value among adults, not because a sports feed produced it.

Eligible examples:
- major Al Hilal, Al Nassr, Al Ittihad, Al Ahli or national-team developments
- major transfers involving globally or locally famous players
- major Saudi-hosted tournaments and landmark sporting events
- exceptional results or decisions that dominate public conversation

Reject:
- routine match results
- minor transfers
- ordinary fixture news
- repetitive club PR
- speculative rumors

The bot is not becoming a sports feed.

### 5. Entertainment, culture, and major events

Eligible examples:
- major Riyadh Season / Jeddah Season developments
- major concerts, festivals, openings, or cultural events with broad Saudi interest
- major entertainment-market launches or changes
- globally significant entertainment news when the subject is highly familiar to Saudi adults

Reject:
- celebrity gossip
- relationship rumors
- low-value influencer news
- promotional PR with no meaningful development
- niche youth trends with weak relevance to the 25–50 audience

### 6. Travel and lifestyle

Eligible examples:
- new Saudi airline routes with meaningful demand or strategic relevance
- airport or visa changes
- major tourism openings
- travel rules or material pricing changes
- large hospitality or destination announcements
- consumer/lifestyle developments with broad adult relevance

## Dedicated Saudi source mix

Dedicated Saudi-interest sources are part of Phase 1. The source pool must contain enough sports, entertainment/culture, travel, and lifestyle coverage that strong stories from those lanes can reach the editor.

Initial RSS candidates:

### Saudi sports
- اليوم — الرياضة: `https://www.alyaum.com/rssFeed/1009`
- اليوم — الدوري السعودي: `https://www.alyaum.com/rssFeed/1009/112`
- الوطن — رياضة: `https://www.alwatan.com.sa/rssFeed/3`
- الشرق الأوسط — الرياضة: `https://aawsat.com/feed/sport`

### Entertainment and culture
- الوطن — حياة: `https://www.alwatan.com.sa/rssFeed/10`
- الشرق الأوسط — الثقافة: `https://aawsat.com/feed/culture`
- الشرق الأوسط — أنغام وفنون: `https://aawsat.com/feed/arts`
- الشرق الأوسط — السينما: `https://aawsat.com/feed/cinema`

### Travel and tourism
- اليوم — سياحة وسفر: `https://www.alyaum.com/rssFeed/1007/105`
- الشرق الأوسط — السياحة: `https://aawsat.com/feed/travel`

### Lifestyle and consumer interest
- اليوم — الحياة: `https://www.alyaum.com/rssFeed/1007`
- الوطن — حياة: `https://www.alwatan.com.sa/rssFeed/10`

These supplement rather than replace strong business, technology, Saudi-general, and regional sources.

A feed may be dropped if it consistently returns zero usable items, malformed XML, or mostly low-value/hyperlocal content. Replacements should remain established Saudi or Saudi-relevant sources.

## Audience-fit gate before lane allocation

Lane allocation happens **after** basic audience-fit filtering.

A fresh item is not automatically entitled to a shortlist slot. Before a lane uses its capacity, the item should plausibly meet at least one strong adult-Snapchat signal:
- broad national relevance
- strong name/brand/club/event familiarity
- material impact on money, travel, work, housing, technology, family life, sport, or daily routine
- high conversation value
- a genuinely surprising or consequential new development

Hyperlocal or routine stories fail this gate even if their feed belongs to `saudi_core`.

If a lane has no sufficiently strong stories, **do not fill its allocation with weak material**. Reallocate those slots to stronger qualified stories from other lanes.

## Balanced candidate sampling

The bot currently uses a capped model shortlist, so high-volume feeds must not crowd other qualified lanes out.

Phase 1 should:
- tag each feed with an internal lane such as `saudi_core`, `business_tech`, `sports`, `entertainment_culture`, or `travel_lifestyle`
- preserve existing article fields and public output schema
- apply basic audience-fit/locality filtering before or during shortlist construction
- interleave qualified items by lane instead of raw feed-list order
- cap how many headlines one individual feed can contribute before other feeds receive a turn
- reallocate unused capacity rather than padding with weak stories

Starting ceilings for the 60-headline model window:
- `business_tech`: up to 20
- `saudi_core`: up to 16
- `sports`: up to 8
- `entertainment_culture`: up to 8
- `travel_lifestyle`: up to 8

These are **maximum opportunities, not minimum quotas**. A lane can contribute zero if nothing is good enough. `saudi_core: up to 16` must never mean "find 16 Saudi local stories."

The model still chooses the single strongest story overall.

## Saudi Snapchat score

For qualified candidates, the prompt should ask the model to evaluate internally:

1. **Audience fit (25–50)** — Is this naturally interesting/useful to adult Saudi Snapchat users?
2. **Saudi relevance** — Does it affect or strongly interest a meaningful share of people in Saudi Arabia?
3. **Familiarity** — Does the audience recognize the person, club, brand, place, product, or event?
4. **Personal impact** — Does it touch money, travel, phone use, work, housing, family life, entertainment, sport, or routine?
5. **Conversation value** — Would someone mention it to a friend or send the Snap?
6. **Surprise/newness** — Is there a real development, number, consequence, or change rather than routine noise?
7. **Scale** — Is the importance broad enough, or is it hyperlocal/niche?
8. **Visual potential** — Can it be represented clearly with a relevant photograph?

Ranking principle:

> High audience fit + Saudi relevance + familiarity + conversation value beats a more globally important but remote story.

A hyperlocal story should lose even if it is technically "more Saudi" than a major Apple, financing, airline, football, or national event story.

Visual potential is a tiebreaker/quality factor, not permission to select a weak story.

## Stop-scroll test

A story should usually contain at least one of:
- a familiar Saudi or global name with a meaningful new development
- a surprising or useful number
- a direct effect on daily life, money, travel, technology, work, housing, family, entertainment, or sport
- a major event people across Saudi Arabia are likely to discuss
- a strong "I didn't know that" factor that can be explained immediately

Prompt test:

> If this appeared between Stories from the follower's friends, would a Saudi adult aged 25–50 stop because the subject matters to them or because they immediately want to know what happened?

The bot must never manufacture stop-scroll value with clickbait.

## Arabic voice

Use clean, conversational Arabic natural to a Saudi adult reader without heavy dialect.

Target voice:
- short
- direct
- mature
- modern
- warm but not chatty
- easy to process quickly
- natural vocabulary rather than bureaucratic/newswire wording

Avoid:
- formal press-release language
- legalistic vocabulary when a normal word exists
- long subordinate clauses
- forced Saudi slang
- teenager-coded slang
- clickbait such as "لن تصدق" or "مفاجأة صادمة"

Useful test:

> If you would not say the sentence naturally to an adult friend or colleague, simplify it.

Foreign company/product names remain in their common English forms. Saudi/Arabic entities remain in Arabic according to existing rules.

## Card-copy roles

Keep the public JSON schema and renderer unchanged.

### `headline`
Purpose: stop the scroll by stating the strongest real development.
- concise and specific
- no vague teasers
- lead with the familiar name, number, or consequence where possible
- do not exaggerate beyond the source

### `summary`
Purpose: answer "what happened?" immediately.
- two short sentences at most
- plain Arabic
- decisive fact + necessary context
- avoid duplicating the headline

### `takeaway`
Purpose: answer "why should I care?" or give the one implication worth remembering.
- useful alone
- polished and natural rather than gimmicky
- no hidden-information promises
- predictions qualified with `قد` or `ربما` unless directly sourced

## What remains excluded

- partisan political horse-race coverage
- wars, violent conflict, crime, gore, accidents and disaster content under existing account policy
- rumors and unverified leaks
- celebrity gossip
- trivial influencer news
- routine sports scores/fixtures
- obscure startup PR
- ceremonial meetings and cooperation announcements with no tangible outcome
- minor product/UI updates
- routine earnings/results that change nothing meaningful
- opinion pieces and pure analysis presented as news
- hyperlocal municipal/city announcements with narrow geographic relevance
- minor local projects and openings without broad Saudi, economic, consumer, or conversation value

## Source and accuracy rules

Keep existing factual restrictions:
- use only information supported by supplied title/summary for normal feed runs
- pinned breaking events require verification through the existing search flow
- preserve numerical comparison safeguards
- preserve public-finance neutrality rules
- preserve Latin digits
- preserve company/entity naming conventions
- preserve existing photo-safety and vision-gate rules

## Architecture and implementation scope

Primary changes:
1. Update `SYSTEM_PROMPT` in `news_bot.py` for the Saudi adult Snapchat editorial model.
2. Expand `FEEDS` with dedicated sports, entertainment/culture, travel, and lifestyle feeds.
3. Add internal feed-lane metadata.
4. Add lane-aware shortlist construction with an audience-fit/locality quality gate so weak hyperlocal items do not consume lane capacity.

Preserve:
- public output JSON schema
- `headline`, `summary`, `takeaway`, `source`, `item`, `scope`, `image_queries`, `image_queries_ar`
- renderer contracts
- publishing code
- photo-selection pipeline
- breaking-news pipeline interfaces

## Tests

At minimum cover:
1. A major Al Hilal/Al Nassr development outranks obscure US corporate earnings.
2. A major Riyadh Season announcement outranks a minor Google UI update.
3. A meaningful Saudi mortgage/financing rule outranks remote foreign political-economic news.
4. A major Apple/OpenAI consumer development may outrank routine Saudi institutional PR.
5. Routine match results do not outrank strong business/tech/consumer stories.
6. Celebrity gossip remains rejected.
7. Major Saudi travel/aviation developments rank strongly.
8. An obscure sports transfer or ordinary concert promotion does not win merely because it is local.
9. A small city municipal project is rejected/down-ranked despite being Saudi.
10. A city-specific story with national-scale impact can still qualify.
11. High-volume global feeds do not prevent qualified sports, entertainment/culture, and travel/lifestyle candidates from reaching the shortlist.
12. A single feed cannot dominate when other lanes have qualified fresh items.
13. If a lane has fewer qualified items than its ceiling, unused capacity flows elsewhere.
14. Existing cross-feed title deduplication still works when the same story appears in general and section feeds.

Where model-output tests would be nondeterministic, use deterministic prompt/fixture checks and representative evaluation cases rather than brittle exact-output assertions.

## Breaking-news behavior

The broader audience concept applies only after an event clears existing confirmation gates. Broadening editorial interest must not lower the definition of "breaking." A sports or entertainment event qualifies for breaking treatment only if genuinely major and confirmed.

Dedicated feeds may be added to the watcher later if its source architecture is separate. Phase 1 must not destabilize the breaking watcher.

## Rollout

Phase 1:
- expand source mix
- add lane metadata and audience-fit/locality filtering
- add lane-aware balanced shortlist sampling
- update editorial prompt
- preserve schema/rendering/publishing
- run dry-run comparisons and log lane representation plus rejected hyperlocal examples

Phase 2, only if justified:
- refine/replace weak feeds based on yield
- introduce explicit audience-scoring telemetry
- use Snapchat engagement data to tune ranking weights
- consider dedicated source expansion for the breaking watcher

## Success criteria

- selected stories feel relevant to Saudi Snapchat users aged 25–50
- the feed is broader than business/tech without becoming generic or gossip-driven
- dedicated Saudi-interest feeds contribute qualified candidates when strong material exists
- no lane is filled merely to hit a number
- hyperlocal city/municipal stories do not win merely because they are Saudi
- nationally important city-specific stories can still qualify
- no single high-volume global source crowds qualified Saudi-interest lanes out
- headlines are easy to understand at a glance
- cards answer "what happened?" and "why should I care?"
- accuracy, sourcing, visual-safety, and publishing safeguards remain intact

## Non-goals

This change does not:
- turn the account into a sports page
- turn the account into an entertainment/gossip page
- turn it into a municipal/local-news feed
- add Snapchat analytics or engagement scraping
- redesign card visuals
- add another model call
- change publishing frequency
- change the breaking-news confirmation threshold

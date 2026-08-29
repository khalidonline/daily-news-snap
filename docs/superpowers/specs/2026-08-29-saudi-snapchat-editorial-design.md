# Saudi Snapchat Editorial Model

Date: 2026-08-29
Status: Approved design, pending implementation review

## Goal

Make the daily news bot feel native to a primarily Saudi, Arabic-speaking Snapchat audience. The bot should select the story a Saudi follower is most likely to stop for, understand immediately, and want to mention or share — while preserving factual accuracy, source discipline, and the account's premium business-aware tone.

The bot should no longer behave like a miniature business newswire. It should behave like a sharp Saudi-interest editor who understands Snapchat.

## Current problem

The current `SYSTEM_PROMPT` is strong at rejecting low-value corporate news, but it is too narrow for the target audience:

- It explicitly excludes sports, entertainment, celebrity/culture, and most labor-market stories.
- It gives highest priority to global technology companies and business/economic news.
- Its primary relevance test is economic or product impact rather than broader Saudi audience interest.

This can cause a globally important but locally remote tech/business story to outrank a major Saudi event, sports development, travel announcement, cultural moment, or consumer change that would be much more compelling on Snapchat.

## Editorial identity

The system prompt should position the model as:

> A Snapchat news-content editor who understands Saudi audiences, Saudi daily life, and what makes a follower stop scrolling.

The model still writes in Arabic even when the source is English.

The editorial objective becomes:

> Would this story make a Saudi follower stop because the subject means something to them, affects their life, surprises them, or gives them something worth talking about?

Conventional newsroom importance is secondary to Saudi audience relevance, provided the story is factual and genuinely newsworthy.

## Eligible content lanes

The bot may select from six lanes. No fixed quota is required; the strongest story wins.

### 1. Saudi life and major decisions

Examples:
- major government decisions that change daily life
- large regulatory or consumer changes
- housing, transport, education, major services
- meaningful labor-market changes when they materially affect Saudis or residents

Routine administrative announcements remain low priority.

### 2. Business, money, and consumer impact

Examples:
- interest rates and financing
- oil when the move is material
- major Saudi companies
- prices, fees, subscriptions, mortgages, banking
- major acquisitions, IPOs, or results when the company is widely known

The existing accuracy rules for public finance and numerical comparisons remain in force.

### 3. Technology

Examples:
- Apple, Google, OpenAI, Snap, TikTok, Samsung, Meta, Microsoft, Tesla, NVIDIA and similarly familiar brands
- major launches and product changes
- AI developments with obvious consumer or work impact
- price, privacy, subscription, policy, or access changes

Minor UI tweaks and obscure startups remain low priority.

### 4. Major sports

Sports is allowed only when the event has broad Saudi conversation value.

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
- large concerts, festivals, openings, or cultural events with broad Saudi interest
- major entertainment-market launches or changes
- globally significant entertainment news when the subject is highly familiar to Saudi audiences

Reject:
- celebrity gossip
- relationship rumors
- low-value influencer news
- promotional PR with no meaningful development

### 6. Travel and lifestyle

Eligible examples:
- new Saudi airline routes
- airport or visa changes
- major tourism openings
- travel rules or pricing changes
- large hospitality or destination announcements
- consumer/lifestyle developments with broad Saudi relevance

## Saudi Snapchat score

The prompt should require the model to evaluate each candidate internally across six dimensions. These scores are for reasoning/ranking only and do not need to appear in the JSON output.

1. **Saudi relevance** — Does it affect or strongly interest someone living in Saudi Arabia?
2. **Familiarity** — Does the audience recognize the person, club, brand, place, product, or event?
3. **Personal impact** — Does it touch money, travel, phone use, work, housing, entertainment, sport, or daily routine?
4. **Conversation value** — Would someone mention it to a friend or send the Snap?
5. **Surprise/newness** — Is there a real development, number, consequence, or change rather than routine noise?
6. **Visual potential** — Can the story be represented with a clear, relevant photograph that makes sense instantly on a Snapchat card?

Ranking principle:

> A story with high Saudi relevance + familiarity + conversation value should beat a more globally important but remote story.

Visual potential is a tiebreaker/quality factor, not permission to select a weak story merely because it has a good photo.

## Stop-scroll test

The existing stop test should be expanded beyond business impact.

A story should usually contain at least one of:

- a familiar Saudi or global name with a meaningful new development
- a surprising or useful number
- a direct effect on daily life, money, travel, technology, work, housing, entertainment, or sport
- a major event people in Saudi Arabia are already likely to discuss
- a strong "I didn't know that" factor that can be explained immediately

The prompt should explicitly ask:

> If this appeared between Stories from the follower's friends, would they stop because the subject matters to them or because they immediately want to know what happened?

The bot must never manufacture stop-scroll value with clickbait. The underlying story must deserve attention.

## Arabic voice

Use clean, conversational Arabic that feels natural to a Saudi reader without becoming heavy dialect.

Target voice:
- short
- direct
- warm but not chatty
- modern
- easy to process in two seconds
- natural vocabulary rather than bureaucratic/newswire wording

Avoid:
- formal press-release language
- legalistic vocabulary when a normal word exists
- long subordinate clauses
- exaggerated colloquial spellings
- forced Saudi slang
- clickbait phrases such as "لن تصدق" or "مفاجأة صادمة"

A useful test:

> If you would not say the sentence naturally to a friend, simplify it.

Foreign company/product names remain in their common English forms. Saudi/Arabic entities remain in Arabic according to the existing rules.

## Card-copy roles

Keep the current JSON schema and renderer unchanged.

### `headline`

Purpose: stop the scroll by stating the strongest real development.

Rules:
- concise and specific
- no vague teasers
- lead with the familiar name, number, or consequence where possible
- do not exaggerate beyond the source

### `summary`

Purpose: answer "what happened?" immediately.

Rules:
- two short sentences at most
- plain Arabic
- include the decisive fact and context
- no duplicated headline wording unless necessary

### `takeaway`

Purpose: answer "why should I care?" or give the one implication worth remembering.

Rules:
- useful even when read alone
- may use a light conversational framing such as "وش يعني لك؟" in the editorial reasoning, but the actual line should remain polished and natural
- must not promise hidden information
- predictions must remain qualified (`قد`, `ربما`) unless directly sourced

## What remains excluded

The broadened model still rejects:

- partisan political horse-race coverage
- wars, violent conflict, crime, gore, accidents and disaster content under the existing account policy
- rumors and unverified leaks
- celebrity gossip
- trivial influencer news
- routine sports scores/fixtures
- obscure startup PR
- ceremonial meetings and cooperation announcements with no tangible outcome
- minor product/UI updates
- routine earnings/results that change nothing meaningful
- opinion pieces and pure analysis presented as news

## Source and accuracy rules

Keep the existing factual restrictions:

- use only information supported by the supplied title/summary for normal feed runs
- pinned breaking events require verification through the existing search flow
- preserve numerical comparison safeguards
- preserve public-finance neutrality rules
- preserve Latin digits
- preserve company/entity naming conventions
- preserve the existing photo-safety and vision-gate rules

This editorial change should not weaken factual or visual safeguards.

## Architecture and implementation scope

### Primary change

Update `SYSTEM_PROMPT` in `news_bot.py` so the selection and writing logic follows this Saudi Snapchat editorial model.

### Preserve existing interfaces

Do not change:
- `summarize()` call shape
- output JSON schema
- `headline`, `summary`, `takeaway`, `source`, `item`, `scope`, `image_queries`, `image_queries_ar`
- renderer contracts
- publishing code
- photo-selection pipeline
- breaking-news pipeline interfaces

This keeps the first rollout low risk.

### Tests

Add focused editorial regression tests/examples that verify ranking behavior conceptually. At minimum cover:

1. A major Al Hilal/Al Nassr development should outrank obscure US corporate earnings.
2. A major Riyadh Season announcement should outrank a minor Google UI update.
3. A meaningful Saudi mortgage/financing rule should outrank remote foreign political-economic news.
4. A major Apple/OpenAI consumer development may outrank routine Saudi institutional PR.
5. Routine match results should not outrank strong business/tech/consumer stories.
6. Celebrity gossip should remain rejected.
7. Major Saudi travel/aviation developments should rank strongly.
8. An obscure sports transfer or ordinary concert promotion should not win merely because it is local.

Where automated model-output tests would be nondeterministic, implement deterministic prompt/fixture checks and representative evaluation cases rather than brittle exact-output assertions.

## Breaking-news behavior

The breaking watcher may use the same broader audience concept only after the event clears its existing confirmation gates.

Broadening editorial interest must not lower the definition of "breaking." A sports or entertainment event should qualify for breaking treatment only if it is genuinely major and confirmed, not merely trending.

## Rollout

Phase 1:
- change the editorial prompt only
- preserve schema/rendering/publishing
- run dry-run comparisons against current candidate sets

Phase 2, only if later justified by observed results:
- tune feed mix to add stronger Saudi sports/culture/travel sources
- introduce explicit audience-scoring telemetry
- use engagement data to tune ranking weights

These are intentionally outside the first implementation unless needed to make the approved editorial model work.

## Success criteria

The change is successful when:

- selected stories feel recognizably relevant to Saudi Snapchat users
- the feed is broader than business/tech without becoming generic or gossip-driven
- headlines are easier to understand at a glance
- cards more consistently answer "what happened?" and "why should I care?"
- major Saudi sports, events, travel, consumer and cultural stories can beat remote global business stories when appropriate
- existing accuracy, sourcing, visual-safety and publishing safeguards remain intact

## Non-goals

This change does not:
- turn the account into a sports page
- turn the account into an entertainment/gossip page
- add engagement scraping or Snapchat analytics
- redesign the card visuals
- add another model call
- change publishing frequency
- change the breaking-news confirmation threshold

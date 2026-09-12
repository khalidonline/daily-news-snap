# Managed publishing pilot

This branch builds the first measurable migration stage. It does **not** operate the new daily publishing service. The owner approved increased investment to achieve reliable daily Info, Topic and true Story posts, each linked to an event active for today and tomorrow in Saudi time.

## What is implemented

- Isolated OpenAI and Anthropic generation adapters, model-access checks, and Getty editorial metadata search. Reuters and Google Cloud return `setup_required` because no end-to-end integration is established here.
- Three historical evidence packages: iPhone 16 launch, Riyadh Metro inauguration, and NASA's 2013 confirmation of Voyager's interstellar crossing. Dates, official sources and claim references are stored in `evaluation/event_packages.json`. These are **replays**, not current posts. Contractor/product announcements are attributed first-party evidence, not independent corroboration.
- A comparison runner that checkpoints model responses and usage, validates structure/references, and never picks a winner without editorial review. A valid source ID does not prove that a generated sentence follows from that source.
- A SQLite delivery reference with per-frame receipts, immutable artifact hashes, Saudi calendar expiry, and safe handling of uncertain sends. This is Linux/local-filesystem test code, **not Cloud Run storage or a live Telegram sender**. Production requires transactional Firestore state and distributed ownership. Local file locks do not span cloud instances; files must be immutable in object storage before delivery.
- Free automated tests and a separate manual supplier evaluation. No Telegram or Snapchat credentials are supplied to these workflows.

## Run the evidence checks

```bash
python -m unittest discover -s tests -p 'test_v2_*.py' -v
python -m publishing_v2.evaluate --mode offline --output /tmp/v2-offline
python -m publishing_v2.evaluate --mode readiness --output /tmp/v2-readiness
python -m publishing_v2.evaluate --mode models --allow-paid --output /tmp/v2-models
python -m publishing_v2.evaluate --mode images --allow-paid --output /tmp/v2-images
```

Offline mode never calls a provider. Readiness performs API GETs only when the corresponding environment key exists. Models/images require the explicit flag. In GitHub, use **Publishing v2 manual evaluation** once the workflow is available on the default branch. Configure `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GETTY_API_KEY` as repository/environment secrets; never put values into issues, commits or chat. An existing production Anthropic key may already be configured: readiness must establish actual model access.

The model experiment reserves worst-case costs in SQLite before each call, using an input UTF-8 byte bound plus 4,096 protocol tokens and up to 6,000 output tokens. No search tools, prompt caching or automatic API retries are requested. Standard rates recorded on September 12, 2026: GPT-6 Astra $10/$50 and Sonnet 5 $2/$10 per million input/output tokens. Verify rates before a later campaign: [OpenAI pricing](https://developers.openai.com/api/docs/pricing), [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing).

The $10 ceiling is cumulative within an output directory. Reusing it cannot reset reservations; unknown attempts retain their full reservation and completed checkpoints are not regenerated. Each separate GitHub invocation uses a fresh directory and a separate $10 ceiling; rerunning a workflow is a new paid experiment. Download the entire artifact, including `spend.sqlite`, to resume an old experiment locally. A hard runner termination can occur before artifact upload: never infer that an absent report means no paid request occurred. This is an experiment safeguard, not an organization-wide billing limit.

## Review model and photo evidence

Review the two providers blind where possible against the same cases. Record factual accuracy, distinct angles, Saudi Arabic quality, opening hook, six-frame narrative, shareability, and proposed image feasibility. Reject fabricated facts/dialogue. Record provider/version, response ID, latency, cost and failures. Three cases screen suppliers; they do not establish broad reliability or justify an automatic winner.

Getty search returns **metadata candidates only**. It does not download an image, inspect pixels, establish contracted rights, or demonstrate a usable portrait crop. Download availability is deliberately unknown (`null`): the adapter does not request account-entitled download metadata. Before approving the photo supply chain:

1. Obtain licensed editorial search/download access and confirm intended social use with the supplier.
2. For every Info/Topic and every Story frame, retrieve an authorized original; verify subject, model/version, date, place, authenticity, resolution, watermark absence and crop.
3. Reject generic filler, false documentary illustrations, and mismatched historical images. Inspect the final Arabic render, not only the source photo.
4. Prove an alternative supplier can complete a package when the first supplier fails. Reuters and official press media still need integration, rights checks and coverage tests.
5. Keep a ready alternative event package within its valid two-day window. If no relevant verified package exists, escalate to the operations owner; do not silently publish stale or invented content.

Supplier references: [Getty API](https://developer.gettyimages.com/docs/), [Reuters delivery](https://reutersagency.com/content-delivery-platforms/content-delivery).

## Delivery contract

Only a confirmed provider receipt establishes a delivered frame. A successful or skipped GitHub job is not proof of publishing. `TemporaryDeliveryError` is reserved for proof that the provider did not accept a frame. Timeouts and unexpected errors become `unknown`; they are not automatically resent. `resolve_unknown` requires an operator to supply an existing receipt or evidence that acceptance did not occur. It cannot independently prove that evidence. A retry resumes undelivered frames and never calls an LLM.

Theme expiry is midnight at the beginning of the third Saudi calendar day, regardless of retries. Expiry is checked before every frame. A clock callable can supply current time; when given a datetime, the store advances it using elapsed monotonic time during delivery. Expiry may leave a partial deck; the system must surface it. A sender must upload the same immutable bytes that were validated. This reference's path-based sender cannot prevent an external actor mutating a file between the hash check and upload.

`evaluation/failure_cases.json` maps observed production runs to these controls. Synthetic tests exercise the contracts; they do not reproduce or claim to fix the original external 401/403/404 outages, image quality rejection, or source coverage.

## Gates before replacing daily production

| Gate | Evidence required | Current state |
|---|---|---|
| Supplier access | Actual model access; contracted photo originals and alternate source | Live verification pending |
| Editorial package | Distinct Info/Topic and six-frame factual Story; approved final visuals | Historical corpus ready; live comparison pending |
| Durable production service | Cloud Run workers, Workflows recovery, Firestore transactions, Storage artifacts, Scheduler and monitoring | Not provisioned |
| Managed operations | Named person/service owns incidents, supplier renewals, credentials and missed deadlines | Owner not appointed |
| Telegram acceptance trial | 3 consecutive days, every planned package delivered with receipts, zero duplicate frames, no owner troubleshooting; outage drills | Not started |
| Rollout | Acceptance evidence reviewed; reversible schedule cutover | Not started |

Cloud architecture reference: [Google Cloud Workflows](https://docs.cloud.google.com/workflows/docs/overview). The review dashboard should show event expiry, content preview, factual sources, photo rights, delivery receipts and exceptions. Khalid reviews editorial decisions; the designated operations service handles technical exceptions. No operations service or background monitoring is activated by this branch.

Do not remove the current schedules or budget guard until the new service meets these gates. Snapchat direct publishing remains disabled pending its own reviewed integration and account access.

## Approved three-day acceptance window

The owner approved three days instead of fourteen. Day 1 begins when the live Telegram pilot delivers its first complete scheduled event package; preparation and offline tests do not count.

- Day 1: verify a complete Info, Topic and six-frame Story package, factual sources, relevant licensed visuals and delivery receipts.
- Day 2: verify event-window continuity or replacement and exercise supplier failure, interrupted delivery and uncertain-send recovery in an isolated test destination.
- Day 3: verify another complete scheduled day and review delivery, duplicates, content quality and outstanding incidents before gradual rollout.

Keep Telegram review throughout. Move to gradual rollout after the three-day evidence is acceptable; unresolved delivery or visual-quality failures must be fixed before expansion. Three days is an initial acceptance sample, not a guarantee of flawless operation. Technical exceptions belong to the operations owner, with continued monitoring after rollout.

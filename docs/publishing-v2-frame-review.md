# Frame-specific image screening

The strategy determines the visual requirements. Providers remain replaceable; Getty can join the same acquisition flow when access is available.

`public_images.acquire` accepts optional `frame_brief` and `reviewer` arguments. The trusted reviewer receives the downloaded file, its provenance, and the complete frame brief. It must return strict boolean decisions for relevance, crop suitability, and historical appropriateness, plus a reason. Rejected candidates and reviewer failures continue to the next candidate/provider. Existing download-only probes keep their previous behavior.

Each successful review invocation writes a content-addressed receipt containing the exact frame context, image SHA-256, source manifest, decisions, and explanation. An image changed during review fails screening. Changing the frame produces a different receipt. Callers should include event date, expiry, complete frame text, intended crop, and illustration labeling in the brief.

This is an integration contract, not an installed visual model. No automatic reviewer is configured yet. Passing screening does not approve rights, establish factual accuracy, or authorize publication. Source credits and licensing metadata remain intact and licensing/publication flags stay false. The ordered source list is caller-configurable; this implementation finds the first passing candidate and does not rank all providers.

Before live rollout, connect an evaluated pixel-aware reviewer, verify rights for the intended use and rendered credits, render and inspect the complete Info/Topic/six-frame Story package, and exercise delivery recovery. The three-day live trial has not started.

Validation: rejection fallback, malformed decisions, changed frame context, and reviewer outage fallback have regression coverage. Existing image download and delivery tests remain included.

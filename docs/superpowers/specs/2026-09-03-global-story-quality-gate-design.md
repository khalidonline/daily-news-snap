# Global Story Quality Gate Design

## Goal
Ensure every Story shown to the human reviewer is already publication-ready, so review is an approval decision rather than repeated editorial coaching.

## Scope
This applies globally to all six-card Story decks. It must not contain story-specific rules for Jeddah, SAMA, Riyadh, or any other title.

The quality gate runs after editorial generation and visual selection, before the frozen human-review artifact is released for approval.

## Existing invariants preserved
- Six-card Story format remains unchanged.
- Existing frame-level visual relevance remains authoritative for semantic image fit.
- Opening and closing visual requirements remain in force.
- At most one middle frame may be text-only where the current publishability policy allows it.
- `POST_TO_SNAPCHAT=0` remains the default for scheduled review runs.
- Telegram remains blocked until human approval of the frozen exact deck.
- Approved delivery must reuse the exact frozen PNGs and must not rerender or regenerate.
- Existing model-cost guard/cache behavior remains unchanged.

## Quality dimensions

### 1. Subject focus
Every frame must materially advance the named subject of the Story.

A supporting fact may appear only when it explains the subject. The deck fails if a supporting topic becomes the dominant narrative.

Examples of failure patterns:
- A Story titled about an airport becomes mainly about pilgrimage travel.
- A company Story becomes mainly about the founder's unrelated biography.
- A city-infrastructure Story becomes mainly about the destination served by that infrastructure.

Required behavior:
- infer a compact `story_subject` from the Story title and editorial brief;
- classify each frame as `DIRECT`, `SUPPORTING`, or `DRIFT`;
- frame 1 and frame 6 must be `DIRECT`;
- no frame may be `DRIFT` in a release-ready deck;
- no more than two consecutive `SUPPORTING` frames.

### 2. Claim precision
The pre-review gate must reject misleading or over-broad wording even when individual facts are technically related.

High-risk claim forms include:
- exclusivity: only / exclusively / the sole way;
- universality: always / everyone / never;
- unsupported firsts or superlatives;
- causal language stronger than the evidence;
- geographic substitutions that materially change meaning.

For Saudi-context Stories, when the intended referent is the modern Kingdom, prefer `السعودية` or `المملكة` rather than loose wording such as `الجزيرة` unless the historical/geographic distinction is deliberate and supported.

The checker returns frame-level findings with severity `BLOCK` or `WARN`. Any `BLOCK` prevents human-review release.

### 3. Narrative chronology
Historical Stories should move through time coherently.

Each frame receives a temporal label:
- explicit year/range when present;
- otherwise one of `HISTORICAL`, `TRANSITION`, `CURRENT`, `TIMELESS`, or `UNKNOWN`.

Rules:
- explicit dates must not regress unless the copy clearly signals a flashback;
- a `CURRENT` frame followed by an unexplained historical regression is a block;
- frame 6 marked current/today/now must represent the latest narrative point;
- timeless explanatory frames may appear between dated frames if they do not imply time reversal.

### 4. Visual chronology
Visuals must follow the narrative's temporal direction.

Each selected image receives visual-era evidence using existing metadata first:
- curated asset metadata / provenance;
- source title, caption, query, filename and known year;
- frame-specific curated mapping;
- deterministic lexical signals such as `historic`, `archive`, `old`, `terminal 1`, current year, etc.

Use semantic/model judgment only when deterministic evidence cannot resolve the era and the decision affects release.

Rules:
- visual era should not move backward relative to the frame narrative without an explicit flashback;
- a current/today frame may not use a clearly archival visual;
- frame 6 must not be older in context than frame 5 when frame 6 is present-day;
- `UNKNOWN` visual era is allowed only when the image is semantically relevant and the frame copy is not explicitly time-bound;
- for explicitly current frame 6, `UNKNOWN` is not release-ready.

### 5. Final-frame currency
Frame 6 is the payoff and must visually match the ending tense.

If the frame contains signals equivalent to today/now/currently/after decades/the modern form, its image must be positively identified as current or modern enough for the claim.

An archival-looking, historical, or ambiguous image blocks release for a current frame 6.

## Evaluation architecture
Create a dedicated global policy module with no renderer side effects.

Suggested module: `story_quality_gate.py`.

Public interfaces:

```python
def evaluate_story_quality(story: str, frames: list[dict], visual_state: dict) -> dict:
    """Return deterministic release findings for focus, claims, narrative time and visual time."""


def release_ready(report: dict) -> bool:
    """True only when there are no BLOCK findings."""
```

Expected report shape:

```python
{
  "status": "PASS" | "BLOCKED",
  "story": "...",
  "dimensions": {
    "subject_focus": "PASS" | "BLOCKED",
    "claim_precision": "PASS" | "BLOCKED",
    "narrative_chronology": "PASS" | "BLOCKED",
    "visual_chronology": "PASS" | "BLOCKED",
    "final_frame_currency": "PASS" | "BLOCKED"
  },
  "findings": [
    {
      "frame": 6,
      "dimension": "final_frame_currency",
      "severity": "BLOCK",
      "code": "CURRENT_COPY_ARCHIVAL_VISUAL",
      "message": "..."
    }
  ]
}
```

## Data boundaries
The quality checker consumes the final editorial deck and final selected visual evidence. It must not:
- rewrite copy;
- choose a new Story;
- publish anything;
- call Telegram or Snapchat;
- perform full-deck regeneration.

It may return structured repair targets.

## Pre-review repair behavior
When quality fails, the system should repair only the affected frames where practical.

Repair target format:

```python
{
  "frames": [1, 6],
  "dimensions": ["subject_focus", "final_frame_currency"],
  "instructions": {
    "1": ["keep copy centered on named subject"],
    "6": ["replace archival visual with clearly current visual"]
  }
}
```

Rules:
- visual-only findings trigger visual-only repair first;
- copy-only findings trigger frame-scoped editorial repair where supported;
- mixed findings may repair both dimensions on the affected frames;
- do not regenerate all six cards unless frame-scoped repair cannot produce a passing deck;
- all repairs remain subject to the existing cost guard.

## Human-review boundary
A Story is eligible to be shown to the human reviewer only when:
1. existing frame relevance/publishability passes;
2. the new global quality report has no `BLOCK` findings;
3. the final six-card deck is frozen with the existing SHA-256 manifest.

A failed quality report remains internal and must not be presented as a ready Story.

After the human approves, the existing approved-artifact path sends the exact frozen files to Telegram without regeneration.

## Cost policy
Use the lowest-cost reliable mechanism in this order:
1. deterministic parsing and metadata;
2. existing cached editorial/visual evidence;
3. lightweight semantic judgment only for unresolved release-critical cases;
4. expensive model use only when a cheaper method cannot safely resolve the quality decision.

Do not introduce a second model-generation call merely because the deck enters human review or is approved.

## Testing strategy
Tests must prove generalization across multiple Story types, not Jeddah alone.

Required regression cases:
- airport/infrastructure Story with side-topic drift -> blocked;
- company Story with unrelated founder tangent -> blocked;
- valid supporting context that returns to subject -> passes;
- exclusivity claim without evidence -> blocked;
- Saudi terminology normalization risk (`الجزيرة` used when `السعودية` is intended) -> blocked or repair-targeted;
- chronological historical deck 1945 -> 1981 -> current -> passes;
- explicit date regression without flashback -> blocked;
- current frame 6 with archival visual -> blocked;
- current frame 6 with modern visual -> passes;
- timeless frame with unknown image era but strong semantic relevance -> allowed;
- visual-only failure generates targeted repair for that frame only;
- quality gate never calls Telegram/Snapchat;
- approval still sends frozen hashes only;
- existing Story publishability, relevance and cost-control suites remain green.

## Acceptance criteria
The feature is complete when:
- no Story-specific exception is required to encode the Jeddah lessons;
- every candidate shown for human approval has passed all five global quality dimensions;
- current-ending Stories cannot end on a clearly old image;
- obvious subject drift and misleading exclusivity are blocked before review;
- failed frames are targeted for repair instead of defaulting to full-deck regeneration;
- approval remains zero-regeneration and uses the exact frozen deck;
- existing cost-control guarantees remain intact.

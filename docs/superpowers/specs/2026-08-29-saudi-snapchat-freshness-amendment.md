# Saudi Snapchat Editorial Model — Freshness Amendment

Date: 2026-08-29
Status: User requirement; supplements `2026-08-29-saudi-snapchat-editorial-design.md`

## Requirement

The daily news bot must be timely without becoming so narrow that it misses an important story simply because it is more than a few hours old.

Normal daily-news eligibility uses a **48-hour maximum lookback**.

Freshness bands:

- **0–12 hours:** strongest freshness preference.
- **12–24 hours:** fully eligible.
- **24–48 hours:** still eligible when the story remains important, useful, surprising, broadly relevant, or actively discussed.
- **Older than 48 hours:** excluded from the normal daily-news candidate pool.

Freshness is a ranking factor, not the only ranking factor. When two stories have similar Saudi Snapchat audience value, choose the newer story. But a major 36–48-hour-old story may outrank a weak or routine story published in the last few hours.

The bot must not repeat a story merely because the lookback window is wider. Existing recently-posted-story memory/deduplication remains in force.

## Internal data requirement

Each fetched feed item should retain its parsed publication timestamp as internal metadata, for example `published_at` in UTC ISO-8601 form. This field is internal only and must not be added to the public card JSON schema.

The model input should expose publication age clearly (for example, `age=7h`, `age=31h`) so the editor can apply the freshness rule explicitly rather than infer age from feed order.

## Shortlist behavior

Lane balancing remains in force. Within otherwise comparable candidates, fresher items should appear earlier. The shortlist logic must not hard-delete 24–48-hour-old qualified stories merely to fill the list with newer low-value material.

## Workflow configuration

The daily workflow lookback should be changed from the current 10-hour override to **48 hours**. The source fetch default should also resolve to 48 hours unless a deliberate workflow override is supplied.

## Breaking-news exception

This 48-hour policy applies to the normal daily-news bot. It does not loosen the separate breaking-news standard. Breaking news must continue to be genuinely current and pass the existing confirmation gates.

## Tests

Add regression coverage proving that:

1. an item older than 48 hours is excluded;
2. a 47-hour-old qualified item remains eligible;
3. when audience value is otherwise equal, a 4-hour-old item ranks ahead of a 30-hour-old item;
4. an important 30-hour-old item is not discarded merely because a weak 2-hour-old item exists;
5. publication age is included in model-input text;
6. the public output schema remains unchanged;
7. recently posted stories remain excluded independently of the wider lookback window.

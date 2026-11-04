# Read-only operational status report

Use the existing report entry point without invoking its Telegram sender:

```sh
python -m publishing_v2.autopilot.report --read-only snapshot.json
python -m publishing_v2.autopilot.report --read-only snapshot.json --format json
```

`--now 2026-11-04T08:49:21Z` fixes the report clock for reproducible replay.
This mode only reads a local snapshot and prints to stdout. It makes no network
requests, paid API calls, writes, dispatches or schedule changes. The existing
no-argument workflow sender is unchanged and is not the read-only command.
No automation is enabled. Existing budget controls are untouched.

## Snapshot contract

The input wraps existing journal bytes, rather than introducing another
publication state store. Fetch evidence read-only before constructing it:

```json
{
  "packages": [{
    "package_id": "original delivery identity",
    "title": "Package title",
    "status": "published",
    "expected_story_cards": 1,
    "story": {
      "source": "verified Story journal URL",
      "observed_at": "2026-11-04T08:49:21Z",
      "data": {"1": {"status": "POSTED", "placement": "STORY", "post_id": "story-id"}}
    },
    "saved_story": {
      "source": "verified Saved Story journal URL",
      "observed_at": "2026-11-04T08:48:05Z",
      "data": {"identity": "original delivery identity", "status": "POSTED", "post_id": "saved-id", "confirmed_at": "2026-11-04T07:08:55Z"}
    }
  }]
}
```

This example illustrates the schema, not live evidence. `status` and `reason`
are source package-state claims, independent of destination confirmation. Use
`unknown` when no package-state evidence is available. Expected Story card count
comes from the original package, not from how many receipts happened to arrive.

The adapter trusts the collector to bind raw journal bytes to the original
package identity and to record the real retrieval time and source. It cannot
verify provenance or current provider visibility offline. Do not label file
mtime, report-generation time, or old cached Git bytes as fresh retrieval.
Do not include tokens, raw HTTP headers or unrelated account metadata.

## Evidence semantics

- Story and Saved Story are separate. A successful workflow/package state is
  not a destination receipt. All expected Story rows must be POSTED with IDs;
  partial, inconsistent or pending journals remain unresolved. Missing is unknown.
- Confirmation means recorded delivery, not that a Story has not since expired
  or been deleted. Reconciliation is a separate authorized operation.
- `observed_at` means when the collector read the evidence; `confirmed_at` comes
  only from a valid timestamp in the source. Missing confirmation times remain
  unknown, even if delivery is confirmed. Generation time is separate.
- Report dates use Asia/Riyadh (UTC+3). An observation over one hour old is labeled
  stale. Missing/future/naive/malformed observation times do not establish freshness.
- This report includes no cost collection, estimation, balance or ledger adapter.
  Unrelated input fields are not forwarded to its output.

## Verified replay, 4 November 2026

The local read-only command was exercised using repository reads:

- [Story journal](https://github.com/khalidonline/daily-news-snap/blob/snapchat-api-state/api-receipts/b06d1d6da96fdd06a51754cd0215713d8e46c33e5bc39f4ff88fd4d9b932c005.json), observed by 08:49:21 UTC: one POSTED card; no confirmation timestamp in journal.
- [Saved Story journal](https://github.com/khalidonline/daily-news-snap/blob/snapchat-api-state/saved-story-receipts/b06d1d6da96fdd06a51754cd0215713d8e46c33e5bc39f4ff88fd4d9b932c005.json), read by 08:48:05 UTC: POSTED, confirmed at 07:08:55.773230 UTC.

This is historical replay evidence, not a promise those sources remain current.
The report demonstration did not create new content or send anything.

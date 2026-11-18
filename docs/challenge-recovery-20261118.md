# Challenge recovery audit, 18 November 2026

Scope: offline transport hardening only; no publication, package edits or request
changes. Retain exact approved media and original per-destination identities.

## Findings

- A route changed after the earlier package validation. Stopping was correct;
  the earlier validation did not certify the new code. Review changed executable
  files, refresh only their inventory entries, then run exact-package validation
  on the resulting commit. Never pin an old publisher or treat a historical
  successful run as proof of current readiness.
- The current live workflow already checks for ffmpeg AND ffprobe before apt,
  uses ubuntu-24.04 and bounds update/install to 90/300 seconds inside an
  eight-minute tooling step. This reduces unnecessary installation and bounds
  stalls; it cannot guarantee package-mirror availability. No change needed.
- Run 44286098509 failed with HTTP 503 during live delivery after validation.
  A create 503 is not evidence the provider rejected the request. Preserve the
  durable SENDING intent. The current gate correctly blocks further sends.
- Run 44294228198 later confirms both destinations. Its reconciliation and
  owner-absence evidence are specific to Pokut; never reuse them for another
  package or silently clear another unresolved intent.

## Limited transport change

GET without a request body retries only HTTP 502/503/504 or OSError, with at
most three attempts and delays of one then two seconds. Every attempt retains
45-second socket timeout. That timeout is NOT an overall wall-clock deadline.
Malformed JSON, authorization/not-found failures and every mutation stop
immediately. No response bodies or credentials are logged.

A missing create response still requires read-only provider reconciliation.
Known post IDs are polled, never recreated. Unknown IDs remain blocked even
when a referenceKey exists: a reference key is not proof of provider-supported
idempotency or comprehensive lookup. Absence from a partial list alone is not
proof of no publication. Existing Story/Spotlight journals remain independent.

## Integration order

Merge the reviewed transport code/tests and the two matching inventory hashes
without changing either live publish request. Then rerun offline exact-package
validation for the current next challenge on the FINAL main commit. If a
concurrent worker is validating it, coordinate that worker's final validation
rather than modifying its files or treating its previous result as current.
Do not execute a publish action as a test.

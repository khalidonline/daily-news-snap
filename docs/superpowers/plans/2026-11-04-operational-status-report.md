# Operational status report implementation plan

Goal: Extend the existing report entry point with a local, read-only JSON/text status report. No sender, runtime, budget or workflow changes.

Architecture: A pure snapshot adapter beside the existing autopilot report consumes existing Story/Saved Story journals. The existing Telegram entry point retains its behavior; an explicit `--read-only SNAPSHOT` mode prints only.

Constraints: No paid calls, dispatch, live writes, schedules, merge or deploy. Receipt observation time is distinct from provider confirmation time. No receipt implies unknown, not failure. Confirmation is destination-specific and requires all expected Story cards. Cost reporting was cancelled by the owner; omit it without altering existing budget controls.

Review focus: Partial and grouped Story journals; Saved Story identity mismatch; duplicate media/post IDs; stale/future observations; accidental send on read-only CLI.

1. Add regression tests for receipt normalization and unknown evidence, then observe failure.
2. Add pure snapshot reporting and Arabic concise rendering, extending the existing report CLI without altering legacy sends.
3. Run targeted and aggregate offline tests. Document snapshot contract and realistic evidence example without credentials.
4. Review diff and upload the status-only change to a draft review branch under the owner’s explicit approval. Verify exact-head CI. No merge or deployment.

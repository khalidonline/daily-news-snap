# Content-safe cleanup

Owner authorized cleaning obsolete operation paths while preserving everything
that may be useful as content: publication logs, sources, rights, originals,
approved exports, drafts, ideas, owner decisions, design masters and receipts.

No live posting, generation, scheduler changes or deletion of remote history.
Prefer recoverable archival to deletion. Do not infer that old code is unused:
publishing_v2.preview still imports news_bot for a supported renderer.

First bounded batch: create a content-preservation index and archive the retired
Story-to-Telegram approval route and its exclusively static tests. This is not
completion of whole-repository cleanup. Follow-up batches require dependency
and receipt evidence; dated per-card workflows may still be needed for recovery.

Preserve approved/, cards/, images/, drafts/, state/, review/, reviews/,
editorial/, assets/, fonts/, evaluation/ and all tracked non-executable content
outside these roots byte-for-byte. Protect the whole roots, including mixed
scripts, until individually assessed. Never move files referenced by approved
hash-bound manifests. Do not modify Library files or snapchat-api-state branch.

Archive copies must match source SHA256 before originals leave active paths.
Keep explicit from/to mapping and restore instructions. Archive as .txt so
historical code cannot be mistaken for an active workflow or collected test.
All current v2 tests, current template tests and publication safeguards remain.
Do not suppress full-suite failures: report remaining failures by name.

# Uploaded preview prerequisite

Owner authorization: «خله شرط», after approving the sequence upload → verify →
preview → approve → publish. Scope: information-card preview entry point only.

Root cause: the Jubbah export was staged locally, then large base64 command output
was truncated during remote transfer after approval. Existing delivery integrity
correctly stopped before posting; publication was delayed by recovery.

Implementation: preserve offline staging as prepare-local-preview. Make the
existing public prepare-preview CLI require a fresh main fetch and byte matching
before returning display paths. Preserve both false approvals and both design
destination reviews. No template, publisher, quota, schedule or receipt changes.

Tests first: local-only CLI readiness and five corrupted/missing remote cases
failed before implementation (7 failures). Use real temporary Git commits for
comparison tests, not invented upload receipts. Network mocks only test failure.

Limits: this gates the approved CLI/agent workflow, not arbitrary Markdown or
attachments sent outside it. Remote/provider processing time is not eliminated.

Verification: 27 focused tests passed. Full isolated suite with the repository's
approved `THEME=light FONT_FAMILY=Almarai` configuration: **1242 passed, 256
subtests passed, 1 existing Pillow getdata deprecation warning**, 98.59 seconds.
The initial unconfigured run was interrupted, not counted as a passing run.
The reviewed executable inventory hash was updated for prepared_information.py.
Push impact: only offline checks; no trigger files or publishing workflows changed.
No live publishing, paid generation, settings/template or content changes.

# Approval-triggered information delivery

## Intent and owner decision
Khalid selected option one on 1 November 2026: recording explicit publication approval should start delivery of the exact prepared information package without a browser. This is approval of the approach, not authority to republish Hyatt or any earlier package.

## Approaches
Selected: an explicit, versioned request file updated with the authorization commit, consumed by the existing publish-approved-package workflow on main. The existing guarded deliver_information publisher remains the only delivery implementation.
Alternative: retain browser dispatch and only streamline metadata. Rejected because it retains the slow UI step. Connector dispatch is not currently exposed; do not extract credentials or invent an API route.

## Proposed implementation
- Add one dedicated .github/information-publish-request.json trigger path, initially absent. Installing the workflow must not create a live request.
- An offline approval helper validates an uploaded-preview receipt and unchanged package hashes, records the owner's reference and time, and stages both authorizations plus a request in one commit. It never generates media or sends a network request.
- Request binds schema version, package name, manifest/archive/prepared hashes, media identity, approved destinations, owner reference, time and expiry. It is not independent permission: both package approvals and existing publisher checks remain required.
- On push, existing workflow reads the request from the exact event commit, confirms the trigger changed in that push, validates all bindings, and calls deliver_information once. Never scan for approved packages or select the latest folder. Ordinary asset/config pushes do not publish.
- Keep workflow_dispatch as explicit recovery. Share the existing account-wide concurrency group, cancel-in-progress false, durable journals and reconciliation. Do not replace receipts, create a new identity on retry, or claim success before both destination confirmations.
- Any content/source/template change invalidates readiness. Missing provenance or rights decision blocks preparation rather than being silently repaired during publication. Editorial acceptance is not a copyright-license claim.

## Constraints and acceptance
Information cards only: Story plus Saved Story, ONE_WEEK. Challenges, schedules, design master and budget unchanged. No live posting, paid generation, secrets extraction or old-package replay during implementation. Preserve concurrent edits and use expected-SHA updates without force. Test with synthetic fixtures and mocked network. Demonstrate invalid/missing/expired/changed approvals cause zero publisher calls; repeated requests reconcile without duplicate creates. Measure actual time improvement only on a future independently approved post.

## Status
Approach selected; detailed plan ready for owner review. No executable changes or live request installed.

# Editorial-first production and targeted correction

Implemented priorities authorized by the owner:
1. Validate timing/research, then independent text review of the useful Info fact and chronological documented story before image preflight and design. A source-bound approval digest is required by Renderer and invalidates on textual changes.
2. One working draft per candidate. Bounded reviewer-specified zero-based card patches cannot modify other cards, title or count. Each revised text passes the gate again. Reuse unchanged selected images and rendered bytes; retain attribution receipts. The internal sources card may be refreshed and is still excluded from Snapchat delivery.
3. Keep delivery separate from production. Existing shared delivery never invokes renderer when files are missing. Saved approved manifests remain deliverable without new model calls; failures stay pending under the original duplicate guards.
4. Existing shared API capacity preflight requires enough slots for the entire unsent remainder before upload. No publishing triggered by this change.

The text review uses the configured reviewer model; card repair uses the configured writer model, both charged to the existing shared $3 ledger. Additional text review is not free; its purpose is preventing wasted downstream production. Actual net savings remain unmeasured.

Owner prepare scripts retrieve supplied source articles and pass the same text gate before image work. Old fixed/expired packages are not automatically regenerated or published. Missing facts/current timing means rejection, not assumed approval.

Checks: 102 local tests available, 101 passing. Known unchanged failure: WorkflowBudgetTests.test_paid_workflows_cannot_override_guard_python_path expects an old injected budget-guard step name in publishing-v2-autopilot.yml. Existing integration fixture expectations were brought in line with the already-configured bounds of four draft attempts / three editor rounds; production bounds unchanged. Fixed a pre-existing KeyError for general editorial feedback lacking a rejected candidate ID, with a regression test.

Tests cover rejection before render, exact card patch scope, changed text invalidating approval, byte-verified render reuse, real renderer downloading/redrawing only the changed card, delivery retries and quota behavior. No paid API calls or publication used in validation. This is a partial checkout, not an assertion about every repository test.

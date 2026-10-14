# Verification — dates recovery

- Publisher/recovery gate: 21 tests passed locally; same gate required in the publishing Action before API operations.
- Approved manifest validated: identity d2ec1f199c92e70c4d5652675d5b39c6daac2f74f0412fd03d0d57024be0b355, two unchanged JPGs.
- Full repository pytest was attempted and is not green. Confirmed first failure: tests/test_breaking_manual_reproduction.py::ManualBreakingReproductionTests::test_breaking_workflow_is_review_only expects .github/workflows/breaking.yml, which is absent in the checked-out baseline. The -x run reported 78 passed and 1 failed. The broader run showed additional legacy failures and did not produce a final summary. No old workflow was restored or enabled to satisfy these tests.
- This verification does not claim general repository CI is healthy. Delivery is additionally checked live against POSTED, PUBLISHED, original upload IDs, distinct media IDs, and ONE_WEEK.

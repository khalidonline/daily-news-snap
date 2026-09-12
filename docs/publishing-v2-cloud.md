# Publishing v2 isolated Cloud evaluation

This foundation runs one historical, offline evaluation in Cloud Run. It does not call model, image, Telegram, or Snapchat providers. A successful run proves only that the digest-pinned container can execute; it does not approve editorial quality, Arabic rendering, photos, licensing, delivery, or production deployment.

## Fixed resources

| Resource | Value |
| --- | --- |
| Project | `daily-news-snap-508412` |
| Region | `me-central1` (Doha) |
| Artifact Registry repository | `publishing-v2` |
| Cloud Run job | `publishing-v2-offline` |
| Runtime identity | `snap-evaluation@daily-news-snap-508412.iam.gserviceaccount.com` |
| GitHub deployer | `snap-github@daily-news-snap-508412.iam.gserviceaccount.com` |

The deploy workflow is manual only. It tests the isolated package, audits the deployer's actual project permissions through [`projects.testIamPermissions`](https://docs.cloud.google.com/resource-manager/reference/rest/v1/projects/testIamPermissions), builds an allowlisted `linux/amd64` context, pushes a commit-specific image, validates its `sha256` digest, replaces the job from a complete specification, and waits for one execution. The script changes no IAM policy or binding.

Run the permission audit from **Actions → Publishing v2 cloud permission audit → Run workflow**. Run deployment from **Actions → Deploy publishing v2 offline evaluation → Run workflow** only after the audit passes. Locally, the safe entry point is:

```bash
python -m publishing_v2.cloud_smoke
```

It accepts no arguments, supplies an empty environment to evaluation, uses a temporary output directory, and always selects `offline` mode. Paid evaluation state must remain on durable storage; this Cloud Run job never hosts the paid SQLite ledger.

## One-time deployer roles

Grant `snap-github` these project roles for initial bootstrap:

- Service Usage Admin — `roles/serviceusage.serviceUsageAdmin`
- Artifact Registry Administrator — `roles/artifactregistry.admin`
- Cloud Run Developer — `roles/run.developer`
- Create Service Accounts — `roles/iam.serviceAccountCreator`
- Service Account User — `roles/iam.serviceAccountUser`

Do not grant Owner, Editor, or IAM Admin. The runtime account receives no project roles. Project-level Service Account User allows `actAs` across service accounts, so after the runtime account exists, replace that broad grant with Service Account User on `snap-evaluation` itself. After bootstrap, remove Create Service Accounts and Service Usage Admin, and reduce Artifact Registry Administrator to the narrower ongoing repository access required by deployments. This workflow is for initial bootstrap only; after narrowing these roles, subsequent deployments require a separate scoped permission audit and deployment path before use. Do not restore the broad bootstrap roles merely to pass the original audit. Google documents the Cloud Run job model in [Create jobs](https://docs.cloud.google.com/run/docs/create-jobs) and the service-account roles in [IAM roles and permissions](https://docs.cloud.google.com/iam/docs/roles-permissions/iam).

The separate permission workflow also reports whether `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `GETTY_API_KEY` secrets are configured or missing. It never prints their values and makes no provider request. Credential presence is informational and does not make this offline job a live evaluation.

Remaining acceptance work includes durable shared state, licensed original images, Arabic visual review, Telegram receipts, supplier comparison, operational escalation, and three live trial days.

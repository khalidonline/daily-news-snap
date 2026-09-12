# Cloud evaluation deployment implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare an isolated, manually executed Cloud Run offline evaluation job and verify the deployer's actual permissions before resource creation.

**Architecture:** GitHub federation authenticates snap-github in daily-news-snap-508412. A read-only permission audit runs on changes to its own workflow on main. A separate manual-only workflow builds an allowlisted container, creates a dedicated Artifact Registry repository and unprivileged runtime service account, deploys a digest-pinned one-task Cloud Run job, and waits for one offline execution.

**Tech Stack:** Python 3.12 standard library, Docker, GitHub Actions, gcloud, Cloud Run jobs, Artifact Registry, region me-central1 (Doha).

**Spec:** docs/superpowers/specs/2026-09-12-event-led-editorial-strategy.md

## Global constraints

- News is the trigger for selection, not a post format. The three published formats are Info, Topic, and Story.
- Preserve Telegram review and existing delivery validation. Snapchat publishing remains disabled.
- No scheduler, production workflow changes, supplier calls, Telegram secrets, or live trial in this bootstrap.
- No project IAM policy changes, service-account keys, or permission grants in deployment scripts.
- Offline evaluation only: never move paid SQLite accounting onto ephemeral Cloud Run storage.
- Deployment success establishes container execution only, not editorial/photo/delivery reliability.
- Dedicated resources: registry publishing-v2, job publishing-v2-offline, runtime snap-evaluation@daily-news-snap-508412.iam.gserviceaccount.com.

### Task 1: Permission-gated deployable offline job

**Files:**
- Create: publishing_v2/cloud_permissions.py (read-only audit and safe CLI)
- Create: publishing_v2/cloud_smoke.py (fixed offline entry point and report to stdout)
- Create: tests/test_v2_cloud.py (audit behavior and entry-point isolation)
- Create: deploy/publishing-v2/Dockerfile and .dockerignore (allowlisted context)
- Create: deploy/publishing-v2/deploy.sh (bounded bootstrap and execution)
- Create: .github/workflows/publishing-v2-cloud-permissions.yml (push main restricted to itself plus manual)
- Create: .github/workflows/publishing-v2-cloud-deploy.yml (manual only)
- Modify: .github/workflows/publishing-v2-tests.yml (include deploy paths and container build/run verification)
- Create: docs/publishing-v2-cloud.md (resources, commands, roles, limitations)

**Interfaces:**
- Permission audit uses fixed project testIamPermissions endpoint, CLOUD_ACCESS_TOKEN environment variable, 20-second timeout, and explicit permission list. Returns JSON status, granted, missing. Errors expose only fixed status and HTTP numeric code, never response body or token. Reject malformed responses. Missing permissions must exit nonzero; a check is not deployment readiness proof.
- Test these project-scoped permissions: serviceusage.services.enable/get/list/use; artifactregistry.repositories.create/get/list/uploadArtifacts/downloadArtifacts; iam.serviceAccounts.create/get/list/actAs; run.jobs.create/get/update/run; run.executions.get; run.operations.get; resourcemanager.projects.get.
- cloud_smoke.main() calls existing evaluate.run('offline', temporary path, env={}) and emits the full safe report. It accepts no CLI arguments and cannot enable paid/provider modes.
- Deploy workflow must run tests and permission audit first, then use auth@v3 with credentials file for setup-gcloud. Build context must exclude generated credential files and all production files; copy only publishing_v2 and evaluation JSON files into a dedicated temporary context.
- deploy.sh is invoked from repo root, uses fixed resource names, enables run/artifactregistry/iam APIs, lists resources before conditional creation (listing failure stops), builds linux/amd64 image, pushes commit-specific tag, resolves and validates sha256 digest, deploys job with runtime SA, tasks=1, max-retries=0, task-timeout=300s, cpu=1, memory=512Mi, then executes with --wait. No IAM binding changes.
- Workflow concurrency prevents overlapping bootstrap; timeout 20 minutes. Cloud success summary must say offline execution only.

- [ ] Write tests proving empty permissions are missing, full response passes, malformed response fails, request uses only the fixed endpoint and authentication header, and exceptions containing a sentinel token never expose it. Use unittest.mock around urllib transport. Prove smoke entrypoint calls only offline and emits no approval flags as true.
- [ ] Run `python -m unittest discover -s tests -p 'test_v2_cloud.py' -v`; record expected initial import failure.
- [ ] Implement the interfaces above. Container base python:3.12-slim, nonroot uid 10001, working dir /app, entrypoint `["python", "-m", "publishing_v2.cloud_smoke"]`.
- [ ] Run `python -m unittest discover -s tests -p 'test_v2_*.py' -v`, `bash -n deploy/publishing-v2/deploy.sh`, parse workflows with yaml.BaseLoader, and execute `python -m publishing_v2.cloud_smoke`.
- [ ] Document exact one-time project bootstrap roles for snap-github: Service Usage Admin (roles/serviceusage.serviceUsageAdmin), Artifact Registry Administrator (roles/artifactregistry.admin), Cloud Run Developer (roles/run.developer), Create Service Accounts (roles/iam.serviceAccountCreator), Service Account User (roles/iam.serviceAccountUser). Explain project-wide actAs and reduce to runtime account after bootstrap; no Owner/Editor/IAM Admin. Runtime account receives no project roles. Reduce bootstrap creator/API admin and registry admin after initial setup.
- [ ] Commit owned files. Review task and branch before publishing. Publish PR using authoritative remote base tree, merge after offline CI passes, inspect live permission audit logs. If permissions missing, give user one consolidated IAM screen instruction. Do not claim Cloud deployment until live execution succeeds.

## Acceptance / remaining work

This stage implements the deployment foundation portion of the managed pilot plan. It deliberately cannot satisfy production acceptance: durable shared state, licensed original images, Arabic rendering review, Telegram receipts, supplier comparison, operational escalation, and three live trial days still need implementation/evidence. Audit API errors are distinct from missing roles and must not be described as proof of missing permissions.

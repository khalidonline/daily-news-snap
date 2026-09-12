"""Read-only audit of the fixed Cloud evaluation deployer permissions."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT = "daily-news-snap-508412"
ENDPOINT = f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT}:testIamPermissions"
REQUIRED_PERMISSIONS = (
    "serviceusage.services.enable",
    "serviceusage.services.get",
    "serviceusage.services.list",
    "serviceusage.services.use",
    "artifactregistry.repositories.create",
    "artifactregistry.repositories.get",
    "artifactregistry.repositories.list",
    "artifactregistry.repositories.uploadArtifacts",
    "artifactregistry.repositories.downloadArtifacts",
    "iam.serviceAccounts.create",
    "iam.serviceAccounts.get",
    "iam.serviceAccounts.list",
    "iam.serviceAccounts.actAs",
    "run.jobs.create",
    "run.jobs.get",
    "run.jobs.update",
    "run.jobs.run",
    "run.executions.get",
    "run.operations.get",
    "resourcemanager.projects.get",
)


def audit(access_token: str) -> dict:
    """Return granted and missing permissions without exposing response errors."""
    if not isinstance(access_token, str) or not access_token.strip():
        return {"status": "missing_access_token", "granted": [], "missing": []}
    request = Request(
        ENDPOINT,
        data=json.dumps({"permissions": list(REQUIRED_PERMISSIONS)}).encode("utf-8"),
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read()
    except HTTPError as error:
        return {"status": "http_error", "http_code": error.code, "granted": [], "missing": []}
    except Exception:
        return {"status": "request_failed", "granted": [], "missing": []}
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError):
        return {"status": "malformed_response", "granted": [], "missing": []}
    if (
        not isinstance(payload, dict)
        or not set(payload).issubset({"permissions"})
        or not isinstance(payload.get("permissions", []), list)
        or any(not isinstance(item, str) for item in payload.get("permissions", []))
        or len(payload.get("permissions", [])) != len(set(payload.get("permissions", [])))
        or any(item not in REQUIRED_PERMISSIONS for item in payload.get("permissions", []))
    ):
        return {"status": "malformed_response", "granted": [], "missing": []}
    returned = payload.get("permissions", [])
    granted = [item for item in REQUIRED_PERMISSIONS if item in returned]
    missing = [item for item in REQUIRED_PERMISSIONS if item not in returned]
    return {
        "status": "missing_permissions" if missing else "permissions_granted",
        "granted": granted,
        "missing": missing,
    }


def main() -> int:
    report = audit(os.environ.get("CLOUD_ACCESS_TOKEN", ""))
    print(json.dumps(report, separators=(",", ":")))
    return 0 if report["status"] == "permissions_granted" else 1


if __name__ == "__main__":
    raise SystemExit(main())

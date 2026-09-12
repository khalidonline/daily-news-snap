#!/usr/bin/env bash
set -euo pipefail

PROJECT="daily-news-snap-508412"
REGION="me-central1"
REPOSITORY="publishing-v2"
JOB="publishing-v2-offline"
RUNTIME_SA="snap-evaluation@${PROJECT}.iam.gserviceaccount.com"
BUILD_CONTEXT="${BUILD_CONTEXT:?BUILD_CONTEXT must name the allowlisted temporary build context}"
COMMIT_SHA="${GITHUB_SHA:?GITHUB_SHA is required for an immutable image tag}"

[[ "$COMMIT_SHA" =~ ^[0-9a-fA-F]{40}$ ]] || { echo "GITHUB_SHA must be a 40-character commit SHA" >&2; exit 2; }
test -f "$BUILD_CONTEXT/Dockerfile"

gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com \
  --project "$PROJECT" --quiet

repositories="$(gcloud artifacts repositories list --project "$PROJECT" --location "$REGION" --format='value(name)')"
service_accounts="$(gcloud iam service-accounts list --project "$PROJECT" --format='value(email)')"
jobs="$(gcloud run jobs list --project "$PROJECT" --region "$REGION" --format='value(name)')"

if ! grep -Eq "(^|/)$REPOSITORY$" <<<"$repositories"; then
  gcloud artifacts repositories create "$REPOSITORY" --project "$PROJECT" --location "$REGION" \
    --repository-format docker --description "Publishing v2 isolated offline evaluation" --quiet
fi
if ! grep -Fxq "$RUNTIME_SA" <<<"$service_accounts"; then
  gcloud iam service-accounts create snap-evaluation --project "$PROJECT" \
    --display-name "Publishing v2 offline evaluation" --quiet
fi

registry="$REGION-docker.pkg.dev"
image="$registry/$PROJECT/$REPOSITORY/publishing-v2:$COMMIT_SHA"
gcloud auth configure-docker "$registry" --quiet
docker build --platform linux/amd64 --tag "$image" --file "$BUILD_CONTEXT/Dockerfile" "$BUILD_CONTEXT"
docker push "$image"
digest_ref="$(docker image inspect "$image" --format '{{range .RepoDigests}}{{println .}}{{end}}' \
  | awk -v prefix="$registry/$PROJECT/$REPOSITORY/publishing-v2@" 'index($0,prefix)==1 {print; exit}')"
[[ "$digest_ref" =~ ^${registry}/${PROJECT}/${REPOSITORY}/publishing-v2@sha256:[0-9a-f]{64}$ ]] \
  || { echo "Pushed image did not resolve to the expected sha256 digest" >&2; exit 1; }

job_spec="$(mktemp)"
trap 'rm -f "$job_spec"' EXIT
cat >"$job_spec" <<EOF
apiVersion: run.googleapis.com/v1
kind: Job
metadata:
  name: $JOB
  namespace: '$PROJECT'
spec:
  template:
    spec:
      taskCount: 1
      template:
        spec:
          serviceAccountName: $RUNTIME_SA
          maxRetries: 0
          timeoutSeconds: '300'
          containers:
            - image: $digest_ref
              resources:
                limits:
                  cpu: '1'
                  memory: 512Mi
EOF

# Replace from a complete spec so old commands, args, environment, and secrets cannot survive.
if grep -Eq "(^|/)$JOB$" <<<"$jobs"; then
  echo "Replacing existing $JOB job with the authoritative offline specification."
else
  echo "Creating $JOB from the authoritative offline specification."
fi
gcloud run jobs replace "$job_spec" --project "$PROJECT" --region "$REGION" --quiet
gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" --wait --quiet

#!/usr/bin/env bash
# Deploy the daily crossword to GCP: builds images, pushes to Artifact Registry,
# deploys the Cloud Run web service + generation job, and schedules daily runs.
#
# Prereqs: gcloud (authed, with a project), Docker.
# Usage:   ./infra/deploy.sh
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
: "${REGION:=us-central1}"
: "${AR_REPO:=daily-crossword}"
: "${BUCKET:?set BUCKET (gs:// bucket name, no gs:// prefix)}"
: "${WEB_SERVICE:=daily-crossword-web}"
: "${GEN_JOB:=daily-crossword-gen}"
: "${SCHEDULER_JOB:=daily-crossword-gen-trigger}"
: "${SA:=daily-crossword-gen@${PROJECT_ID}.iam.gserviceaccount.com}"  # gen job SA

AR="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
TAG="latest"

echo "==> Building & pushing images to ${AR}"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet || true
docker build -t "${AR}/${WEB_SERVICE}:${TAG}" -f Dockerfile.web .
docker push "${AR}/${WEB_SERVICE}:${TAG}"
docker build -t "${AR}/${GEN_JOB}:${TAG}" -f Dockerfile.gen .
docker push "${AR}/${GEN_JOB}:${TAG}"

echo "==> Deploying Cloud Run web service: ${WEB_SERVICE}"
gcloud run deploy "${WEB_SERVICE}" \
  --image "${AR}/${WEB_SERVICE}:${TAG}" \
  --region "${REGION}" --no-allow-unauthenticated \
  --set-env-vars "APP_ENV=production,PUZZLE_STORE=gcs,PUZZLE_BUCKET=${BUCKET}" \
  --min-instances 0 --max-instances 3 --cpu-throttling

echo "==> Deploying Cloud Run job: ${GEN_JOB}"
gcloud run jobs create "${GEN_JOB}" \
  --image "${AR}/${GEN_JOB}:${TAG}" \
  --region "${REGION}" \
  --set-env-vars "PUZZLE_STORE=gcs,PUZZLE_BUCKET=${BUCKET}" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" \
  --service-account "${SA}" \
  --task-timeout 10m || \
gcloud run jobs update "${GEN_JOB}" \
  --image "${AR}/${GEN_JOB}:${TAG}" --region "${REGION}" \
  --set-env-vars "PUZZLE_STORE=gcs,PUZZLE_BUCKET=${BUCKET}" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" \
  --service-account "${SA}"

echo "==> Scheduling daily generation (02:00 UTC) via Cloud Scheduler"
SCHED_URL="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${GEN_JOB}:run"
gcloud scheduler jobs create http "${SCHEDULER_JOB}" \
  --schedule "0 2 * * *" --time-zone UTC \
  --uri "${SCHED_URL}" --http-method POST \
  --oauth-service-account-email "${SA}" \
  --attempt-deadline 600s \
  --location "${REGION}" \
  --description "Trigger daily crossword generation" || \
gcloud scheduler jobs update http "${SCHEDULER_JOB}" \
  --schedule "0 2 * * *" --time-zone UTC \
  --uri "${SCHED_URL}" --http-method POST \
  --oauth-service-account-email "${SA}" \
  --location "${REGION}"

echo "==> Done."
echo "Web URL:   https://${WEB_SERVICE}-$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)').run.app"
echo "Trigger a run now:  gcloud run jobs execute ${GEN_JOB} --region ${REGION}"

#!/usr/bin/env bash
# Deploy Afterlife to Google Cloud Run. Safe to re-run: every step checks before creating.
#
#   gcloud auth login && gcloud config set project YOUR_PROJECT_ID
#   GEMINI_API_KEY=... ./scripts/deploy.sh          # first deploy (stores the key in Secret Manager)
#   ./scripts/deploy.sh                             # later deploys (reuses the stored key)
#
# Optional overrides: PROJECT_ID REGION SERVICE BUCKET EXTRACTION_MODEL REASONING_MODEL GEMINI_RPM
#                     MIN_INSTANCES MAX_INSTANCES
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-asia-south1}"                      # Mumbai
SERVICE="${SERVICE:-afterlife}"
BUCKET="${BUCKET:-${PROJECT_ID}-afterlife-uploads}"
FIRESTORE_DATABASE="(default)"
SECRET_NAME="GEMINI_API_KEY"
RUNTIME_SA="afterlife-run"
EXTRACTION_MODEL="${EXTRACTION_MODEL:-gemini-3.8-flash}"
# Free-tier defaults (same as .env.example). Once billing is on: REASONING_MODEL=gemini-4-argon GEMINI_RPM=0
REASONING_MODEL="${REASONING_MODEL:-gemini-3.6-flash}"  # gemini-4-argon has a free-tier quota of 0
GEMINI_RPM="${GEMINI_RPM:-5}"                           # free tier allows ~5/min; 0 = no client-side throttle
MIN_INSTANCES="${MIN_INSTANCES:-1}"                    # 1 avoids a cold start during the live demo
MAX_INSTANCES="${MAX_INSTANCES:-3}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "No project set. Run: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi
cd "$(dirname "$0")/.."
SA_EMAIL="${RUNTIME_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
step() { printf '\n==> %s\n' "$*"; }

step "Project ${PROJECT_ID}, region ${REGION}, service ${SERVICE}"

step "Enabling APIs"
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com storage.googleapis.com secretmanager.googleapis.com iam.googleapis.com \
  --project "${PROJECT_ID}"

step "Firestore database ${FIRESTORE_DATABASE}"
if gcloud firestore databases describe --database="${FIRESTORE_DATABASE}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  echo "exists"
else
  gcloud firestore databases create --database="${FIRESTORE_DATABASE}" --location="${REGION}" \
    --type=firestore-native --project "${PROJECT_ID}"
fi

step "Upload bucket gs://${BUCKET} (private, files auto-deleted 24h after upload)"
if gcloud storage buckets describe "gs://${BUCKET}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  echo "exists"
else
  gcloud storage buckets create "gs://${BUCKET}" --location="${REGION}" --project "${PROJECT_ID}" \
    --uniform-bucket-level-access --public-access-prevention
fi
# age=1 day: objects become eligible for deletion 24h after upload (GCS applies lifecycle rules asynchronously).
gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file=scripts/gcs-lifecycle.json

step "Secret ${SECRET_NAME} in Secret Manager"
if gcloud secrets describe "${SECRET_NAME}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    printf '%s' "${GEMINI_API_KEY}" | gcloud secrets versions add "${SECRET_NAME}" --data-file=- --project "${PROJECT_ID}"
    echo "added a new version"
  else
    echo "exists (set GEMINI_API_KEY to rotate it)"
  fi
else
  if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "First deploy needs the key: GEMINI_API_KEY=... ./scripts/deploy.sh" >&2
    exit 1
  fi
  printf '%s' "${GEMINI_API_KEY}" | gcloud secrets create "${SECRET_NAME}" --replication-policy=automatic \
    --data-file=- --project "${PROJECT_ID}"
fi

step "Runtime service account ${SA_EMAIL} (least privilege)"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${RUNTIME_SA}" --display-name="Afterlife Cloud Run" --project "${PROJECT_ID}"
fi
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="serviceAccount:${SA_EMAIL}" \
  --role=roles/datastore.user --condition=None >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --member="serviceAccount:${SA_EMAIL}" \
  --role=roles/storage.objectAdmin >/dev/null
gcloud secrets add-iam-policy-binding "${SECRET_NAME}" --member="serviceAccount:${SA_EMAIL}" \
  --role=roles/secretmanager.secretAccessor --project "${PROJECT_ID}" >/dev/null
echo "roles granted: datastore.user (project), storage.objectAdmin (bucket), secretAccessor (secret)"

step "Building and deploying to Cloud Run (Cloud Build uses the Dockerfile)"
gcloud run deploy "${SERVICE}" \
  --source . \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --service-account "${SA_EMAIL}" \
  --allow-unauthenticated \
  --set-secrets "GEMINI_API_KEY=${SECRET_NAME}:latest" \
  --set-env-vars "^|^STORAGE_BACKEND=gcp|GCP_PROJECT=${PROJECT_ID}|GCS_BUCKET=${BUCKET}|FIRESTORE_DATABASE=${FIRESTORE_DATABASE}|EXTRACTION_MODEL=${EXTRACTION_MODEL}|REASONING_MODEL=${REASONING_MODEL}|GEMINI_RPM=${GEMINI_RPM}" \
  --memory 1Gi --cpu 1 --timeout 300 --concurrency 20 \
  --min-instances "${MIN_INSTANCES}" --max-instances "${MAX_INSTANCES}" \
  --quiet

URL="$(gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)')"
step "Deployed: ${URL}"
curl -fsS "${URL}/api/health" && echo

#!/usr/bin/env bash
# Deploy fo-intel-api + fo-intel-web to Cloud Run.
# Prerequisites: gcloud auth, project set, OPENAI_API_KEY in env or fo-intel/.env
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-us-central1}"
if [[ -z "$PROJECT" || "$PROJECT" == "(unset)" ]]; then
  echo "Set GCP project: gcloud config set project YOUR_PROJECT"
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  if [[ -f .env ]]; then
    # shellcheck disable=SC1091
    set -a; source .env; set +a
  fi
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY required"
  exit 1
fi

if [[ ! -f data/index/index.faiss ]]; then
  echo "Building FAISS index..."
  python -m pipeline.build_index
fi

API_IMAGE="gcr.io/${PROJECT}/fo-intel-api"
WEB_IMAGE="gcr.io/${PROJECT}/fo-intel-web"

echo "Building API image..."
gcloud builds submit --tag "$API_IMAGE" -f api/Dockerfile .

echo "Deploying API..."
gcloud run deploy fo-intel-api \
  --image "$API_IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi \
  --set-env-vars "OPENAI_API_KEY=${OPENAI_API_KEY},FO_INDEX_DIR=/app/data/index"

API_URL="$(gcloud run services describe fo-intel-api --region "$REGION" --format='value(status.url)')"
echo "API_URL=$API_URL"

echo "Building Web image..."
gcloud builds submit --tag "$WEB_IMAGE" \
  --config=- <<EOF
steps:
- name: gcr.io/cloud-builders/docker
  args: ['build','-f','web/Dockerfile','--build-arg','NEXT_PUBLIC_API_URL=${API_URL}','-t','${WEB_IMAGE}','web']
images: ['${WEB_IMAGE}']
EOF

echo "Deploying Web..."
gcloud run deploy fo-intel-web \
  --image "$WEB_IMAGE" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 512Mi

WEB_URL="$(gcloud run services describe fo-intel-web --region "$REGION" --format='value(status.url)')"
echo "CUSTOMER_URL=$WEB_URL"
echo "$WEB_URL" > data/export/live_url.txt
echo "Done. Customer URL: $WEB_URL"

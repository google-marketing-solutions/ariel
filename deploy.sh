#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

SERVICE_NAME="ariel-v2"
REGION=$(grep "GCP_PROJECT_LOCATION" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')
GCS_BUCKET=$(grep "GCS_BUCKET_NAME" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')

if [[ -z "$REGION" || -z "$GCS_BUCKET" ]]; then
  echo "❌ Error: Could not read REGION or GCS_BUCKET from configuration.yaml."
  echo "Please run setup.sh first."
  exit 1
fi

# Build requirements.txt needed for cloud run but skipping the local file output from uv
uv pip compile pyproject.toml -o requirements.txt > /dev/null

# Deploy and capture the exit code
gcloud beta run deploy "$SERVICE_NAME" \
  --source . \
  --region="$REGION" \
  --memory 8192Mi \
  --cpu 2 \
  --timeout 3600 \
  --env-vars-file=configuration.yaml  \
  --quiet \
  --iap \
  --add-volume name=ariel,type=cloud-storage,bucket="$GCS_BUCKET" \
  --add-volume-mount volume=ariel,mount-path="/mnt/ariel" \


# Stream logs
#gcloud beta run services logs tail "$SERVICE_NAME" --region="$REGION"


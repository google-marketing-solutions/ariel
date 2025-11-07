#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

SERVICE_NAME="ariel-v2"
REGION="us-central1"
TEMP_BUCKET="ariel-v2-test-persistant-bucket"

# Build requirements.txt needed for cloud run but skipping the local file output from uv
uv pip compile pyproject.toml -o requirements.txt > /dev/null

# Deploy and capture the exit code
gcloud beta run deploy "$SERVICE_NAME" \
  --source . \
  --region="$REGION" \
  --memory 3072Mi \
  --env-vars-file=configuration.yaml  \
  --quiet \
  --iap \
  --add-volume name=ariel,type=cloud-storage,bucket="$TEMP_BUCKET" \
  --add-volume-mount volume=ariel,mount-path="/mnt/ariel" \


# Stream logs
#gcloud beta run services logs tail "$SERVICE_NAME" --region="$REGION"

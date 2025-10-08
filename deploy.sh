#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

SERVICE_NAME="ariel-v2"
REGION="us-central1"

# Build requirements.txt needed for cloud run but skipping the local file output from uv
pipx run uv pip compile pyproject.toml -o requirements.txt > /dev/null

# Deploy and capture the exit code
gcloud beta run deploy "$SERVICE_NAME" --source . --region="$REGION" --quiet --iap

# Stream logs
gcloud beta run services logs tail "$SERVICE_NAME" --region="$REGION"

#!/bin/bash

SERVICE_NAME="ariel-v2"
REGION=$(grep "GCP_PROJECT_LOCATION" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')
GCS_BUCKET=$(grep "GCS_BUCKET_NAME" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')
PROJECT_ID=$(grep "GCP_PROJECT_ID" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')

if [[ -z "$REGION" || -z "$GCS_BUCKET" || -z "$PROJECT_ID" ]]; then
  echo "❌ Error: Could not read configuration from configuration.yaml."
  echo "Please run setup.sh first."
  exit 1
fi

# Build requirements.txt needed for cloud run but skipping the local file output from uv
uv pip compile pyproject.toml -o requirements.txt > /dev/null

SERVICE_ACCOUNT_NAME="$SERVICE_NAME"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant the service account storage.objects.create access to the bucket
echo "🔑 Granting 'Storage Object Creator' role to the Cloud Run service account on bucket gs://$GCS_BUCKET..."
gsutil iam ch serviceAccount:${SERVICE_ACCOUNT_EMAIL}:roles/storage.objectCreator gs://$GCS_BUCKET

deploy_service() {
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
    --service-account="$SERVICE_ACCOUNT_EMAIL"
}

# First deployment attempt
echo "🚀 Deploying service..."
if deploy_service; then
  echo "✅ Deployment successful!"
else
  echo "⚠️ Deployment failed. Retrying in 5 seconds..."
  sleep 5

  # Get Project Number
  PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

  if [[ -n "$PROJECT_NUMBER" ]]; then
    IAP_SERVICE_ACCOUNT="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
    echo "🔑 Granting 'Cloud Run Invoker' role to the IAP service account ($IAP_SERVICE_ACCOUNT)..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:$IAP_SERVICE_ACCOUNT" \
      --role="roles/run.invoker" \
      --quiet
  else
    echo "❌ Error: Could not retrieve project number. Skipping role grant."
  fi

  echo "🔄 Retrying deployment..."
  if deploy_service; then
    echo "✅ Deployment successful on retry!"
  else
    echo "❌ Deployment failed again."
    exit 1
  fi
fi

# Stream logs
#gcloud beta run services logs tail "$SERVICE_NAME" --region="$REGION"



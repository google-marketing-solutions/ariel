#!/bin/bash

# A script to find a Cloud Run service account and grant it the Vertex AI User role.

# --- Configuration ---
# Set the name of your Cloud Run service and its region.
SERVICE_NAME="ariel"
REGION="us-central1"

echo "▶️ Starting permission script for service '$SERVICE_NAME' in region '$REGION'..."

# 2. Get the current Project ID from gcloud config
PROJECT_ID=$(gcloud config get-value project)
if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ Error: gcloud project ID not set. Please run 'gcloud config set project YOUR_PROJECT_ID'."
  exit 1
fi
echo "✅ Found Project ID: $PROJECT_ID"

# 3. Retrieve the Service Account email for the Cloud Run service
echo "🔎 Retrieving service account..."
SERVICE_ACCOUNT_EMAIL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format='value(spec.template.spec.serviceAccountName)' --project="$PROJECT_ID")

if [[ -z "$SERVICE_ACCOUNT_EMAIL" ]]; then
  echo "❌ Error: Could not find service account for '$SERVICE_NAME'. Please double-check the service name and region."
  exit 1
fi
echo "✅ Found Service Account: $SERVICE_ACCOUNT_EMAIL"

# 4. Grant the 'Vertex AI User' role to the Service Account
echo "🔑 Granting 'Vertex AI User' role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/aiplatform.user"

echo "🎉 Success! Permission granted."
echo "--------------------------------------------------------"
echo "Next Step: Re-deploy your Cloud Run service for the new permissions to take effect."
echo "gcloud run deploy $SERVICE_NAME --region=$REGION --source ."
echo "--------------------------------------------------------"

#!/bin/bash

# A script to find a Cloud Run service account and grant it the Vertex AI User role.

# --- Configuration ---
# Set the name of your Cloud Run service and its region.
SERVICE_NAME="ariel-v2"
REGION="us-central1"

echo "▶️ Starting permission script for service '$SERVICE_NAME' in region '$REGION'..."

# 2. Get the current Project ID from gcloud config
PROJECT_ID=$(gcloud config get-value project)
if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ Error: gcloud project ID not set. Please run 'gcloud config set project YOUR_PROJECT_ID'."
  exit 1
fi
echo "✅ Found Project ID: $PROJECT_ID"

# 3. Grant the current user permissions to manage IAM
CURRENT_USER=$(gcloud config get-value account)
if [[ -z "$CURRENT_USER" ]]; then
    echo "❌ Error: Could not get current user from gcloud config."
    exit 1
fi
echo "🔑 Granting 'IAP-secured Web App User' role to $CURRENT_USER..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="user:$CURRENT_USER" \
    --role="roles/iap.httpsResourceAccessor" \
    --quiet
echo "✅ IAM permissions granted to user."

# 3. Enable the Cloud Build API and grant necessary permissions
echo "🔑 Enabling Cloud Build API and granting permissions..."
gcloud services enable serviceusage.googleapis.com cloudbuild.googleapis.com iap.googleapis.com generativelanguage.googleapis.com aiplatform.googleapis.com translate.googleapis.com --project="$PROJECT_ID"

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
if [[ -z "$PROJECT_NUMBER" ]]; then
  echo "❌ Error: Could not retrieve project number for project '$PROJECT_ID'."
  exit 1
fi

# Grant the official Cloud Build service account the necessary roles
BUILD_SERVICE_ACCOUNT="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
echo "🔑 Granting 'Storage Object Viewer' and 'Logs Writer' roles to the Cloud Build service account..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BUILD_SERVICE_ACCOUNT" \
    --role="roles/storage.objectViewer" \
    --quiet
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BUILD_SERVICE_ACCOUNT" \
    --role="roles/logging.logWriter" \
    --quiet
echo "✅ Cloud Build permissions granted."

# 4. Create the service account for the service to run as
SERVICE_ACCOUNT_NAME="$SERVICE_NAME"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "🔎 Checking for service account: $SERVICE_ACCOUNT_EMAIL..."
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" --quiet &> /dev/null; then
  echo "🤔 Service account not found. Creating..."
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="Ariel Service Account" \
    --project="$PROJECT_ID"
  echo "✅ Service account created."
else
  echo "✅ Service account already exists."
fi

# 5. Grant necessary roles to the Service Account
echo "🔑 Granting 'Vertex AI User', 'Storage Object Viewer', and 'Logs Writer' roles to $SERVICE_ACCOUNT_EMAIL..."

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/aiplatform.user" \
    --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.objectViewer" \
    --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/logging.logWriter" \
    --quiet

echo "🎉 Success! Permission granted."
echo "--------------------------------------------------------"
echo "Next Step: Deploy your Cloud Run service with IAP enabled."
echo "gcloud run deploy $SERVICE_NAME --region=$REGION --source . --service-account=$SERVICE_ACCOUNT_EMAIL --iap=enabled"
echo "--------------------------------------------------------"

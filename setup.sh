#!/bin/bash

# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# A script to find a Cloud Run service account and grant it the Vertex AI User role.

# --- Configuration ---
# Set the name of your Cloud Run service.
SERVICE_NAME="ariel-v2"

echo "🛠️ Validating build and deploy requirements..."
ffmpeg -version >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "❌ Error: ffmpeg is not installed. Try installing it (e.g. apt-get install ffmpeg) and run the script again."
  exit 1
fi
echo "✅ ffmpeg is installed."

uv --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "❌ Error: uv is not installed. Try installing it (e.g. pip install uv) and run the script again."
  exit 1
fi
echo "✅ uv is installed."

gcloud --version >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "❌ Error: gcloud is not installed. Try installing it (e.g. apt-get install google-cloud-sdk) and run the script again."
  exit 1
fi
echo "✅ gcloud is installed."

echo "🛠️ Installing Python dependencies..."
uv sync

# 1. Get and confirm the current Project ID from gcloud config
PROJECT_ID=$(gcloud config get-value project)

if [[ -n "$PROJECT_ID" ]]; then
  read -p "Is this the correct Project ID: '$PROJECT_ID'? (y/n) " confirm
  if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    PROJECT_ID="" # Clear it so we prompt for a new one
  fi
fi

if [[ -z "$PROJECT_ID" ]]; then
  read -p "Enter the Google Cloud Project ID: " NEW_PROJECT_ID
  if [[ -z "$NEW_PROJECT_ID" ]]; then
    echo "❌ Error: A Project ID is required."
    exit 1
  fi
  gcloud config set project "$NEW_PROJECT_ID"
  PROJECT_ID=$NEW_PROJECT_ID
fi

echo "✅ Using Project ID: $PROJECT_ID"

# Get region from gcloud config, or prompt if not set
REGION=$(gcloud config get-value compute/region)
if [[ -z "$REGION" ]]; then
  read -p "Enter the GCP region for the service (e.g., us-central1): " REGION
  if [[ -z "$REGION" ]]; then
    echo "❌ Error: A region is required."
    exit 1
  fi
  # Set the region in gcloud config for future use
  gcloud config set compute/region "$REGION"
fi

echo "▶️ Starting permission script for service '$SERVICE_NAME' in region '$REGION'..."

# 3. Prompt for and create the Cloud Storage bucket
while true; do
  read -p "Enter the name for the Cloud Storage bucket to be used for analysis: " BUCKET_NAME
  BUCKET_URI="gs://$BUCKET_NAME"

  echo "🔎 Checking for Cloud Storage bucket: $BUCKET_URI..."
  # Check if bucket exists and we have access
  DESCRIBE_OUTPUT=$(gcloud storage buckets describe "$BUCKET_URI" 2>&1)
  DESCRIBE_EXIT_CODE=$?

  if [[ $DESCRIBE_EXIT_CODE -eq 0 ]]; then
    echo "✅ Bucket already exists and is readable."
    break
  elif echo "$DESCRIBE_OUTPUT" | grep -q "Permission 'storage.buckets.get' denied on resource"; then
    echo "❌ Error: The bucket '$BUCKET_NAME' exists but is not readable."
    echo "Please enter a globally unique name for a new bucket."
  elif echo "$DESCRIBE_OUTPUT" | grep -q "not found: 404"; then
    echo "🤔 Bucket not found. Creating..."
    if gcloud storage buckets create "$BUCKET_URI" --location="$REGION"; then
      echo "✅ Bucket created."

      echo "⏳ Setting 5-day TTL lifecycle policy..."
      cat <<EOF > lifecycle.json
{
  "rule":
  [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 5}
    }
  ]
}
EOF
      gcloud storage buckets update "$BUCKET_URI" --lifecycle-file=lifecycle.json
      rm lifecycle.json
      echo "✅ Lifecycle policy set."
      break
    else
      echo "❌ Failed to create bucket. Please try a different name."
    fi
  else
    echo "❌ Error checking bucket: $LS_OUTPUT"
    echo "Please try a different name."
  fi
done

# Create configuration.yaml from template
echo "📝 Creating configuration.yaml..."
cp configuration.template.yaml configuration.yaml

if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS (BSD sed) requires an empty string for the -i flag
  sed -i "" "s/enter project id here/$PROJECT_ID/g" configuration.yaml
  sed -i "" "s/enter project location here/$REGION/g" configuration.yaml
  sed -i "" "s/enter bucket name here/$BUCKET_NAME/g" configuration.yaml
else
  # Linux (GNU sed) does not
  sed -i "s/enter project id here/$PROJECT_ID/g" configuration.yaml
  sed -i "s/enter project location here/$REGION/g" configuration.yaml
  sed -i "s/enter bucket name here/$BUCKET_NAME/g" configuration.yaml
fi

echo "✅ configuration.yaml created."

# 4. Grant the current user permissions to manage IAM
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

# 5. Enable the Cloud Build API and grant necessary permissions
echo "🔑 Enabling Cloud Build API and granting permissions..."
gcloud services enable serviceusage.googleapis.com cloudbuild.googleapis.com iap.googleapis.com generativelanguage.googleapis.com aiplatform.googleapis.com translate.googleapis.com texttospeech.googleapis.com --project="$PROJECT_ID"

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



# 6. Create the service account for the service to run as
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

# Wait for service account to be fully propagated
echo "⏳ Waiting for service account to be available..."
while ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project="$PROJECT_ID" --quiet &> /dev/null; do
  echo "zzz..."
  sleep 5
done
echo "✅ Service account is ready."

# 7. Grant necessary roles to the Service Account
echo "🔑 Granting 'Vertex AI User', 'Cloud Run Developer', 'Storage Object Admin', and 'Logs Writer' roles to $SERVICE_ACCOUNT_EMAIL..."

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/aiplatform.user" \
    --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/run.builder" \
    --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/storage.objectAdmin" \
    --quiet

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/logging.logWriter" \
    --quiet

echo "🎉 Success! Permission granted."
echo "--------------------------------------------------------"
echo "Next Step: Deploy Ariel v2 by running deploy.sh."
echo "--------------------------------------------------------"

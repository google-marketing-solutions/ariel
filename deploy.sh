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

SERVICE_NAME="ariel-v2"
REGION=$(grep "GCP_PROJECT_LOCATION" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')
GCS_BUCKET=$(grep "GCS_BUCKET_NAME" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')
PROJECT_ID=$(grep "GCP_PROJECT_ID" configuration.yaml | awk -F': "' '{print $2}' | tr -d '"')
DOCKER_REPO_NAME=gps-docker-repo
ARTIFACT_POSITORY_NAME=$REGION-docker.pkg.dev/$PROJECT_ID/$DOCKER_REPO_NAME
DOCKER_IMAGE_TAG=$ARTIFACT_POSITORY_NAME/ariel-process:latest

if [[ -z "$REGION" || -z "$GCS_BUCKET" || -z "$PROJECT_ID" ]]; then
  echo "❌ Error: Could not read configuration from configuration.yaml."
  echo "Please run setup.sh first."
  exit 1
fi

DOCKER_AVAILABLE=$(docker --version >/dev/null 2>&1 && echo "true" || echo "false")

# Build requirements.txt needed for cloud run but skipping the local file output from uv
uv pip compile pyproject.toml -o requirements.txt > /dev/null

SERVICE_ACCOUNT_NAME="$SERVICE_NAME"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant the service account storage.objects.create access to the bucket
echo "🔑 Granting 'Storage Object Creator' role to the Cloud Run service account on bucket gs://$GCS_BUCKET..."
gcloud storage buckets add-iam-policy-binding gs://$GCS_BUCKET \
    --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
    --role="roles/storage.objectCreator"

if [ "$DOCKER_AVAILABLE" = "true" ]; then
  echo "ℹ️ Using local Docker build to speed up development and deployment"
  echo "🛠️ Setting up Docker registry in GCP..."

  REPO_EXISTS=$(gcloud artifacts repositories describe $DOCKER_REPO_NAME --location=$REGION >/dev/null 2>&1 && echo "true" || echo "false")
  if "${REPO_EXISTS}"; then
    echo "⚠️ Repository '$DOCKER_REPO_NAME' already exists in location '$REGION'. Skipping creation...\n"
  else
    echo "📦 Creating artifacts repository for docker images"
    gcloud artifacts repositories create $DOCKER_REPO_NAME --repository-format=docker \
      --location=$REGION --description="Google Professional Services images" \
      --project=$PROJECT_ID
    test $? -eq 0 || exit
    echo "✅ Repository '$DOCKER_REPO_NAME' created successfully in location '$REGION'!\n"
    gcloud auth configure-docker $REGION-docker.pkg.dev
  fi
fi

deploy_service() {
  if [ "$DOCKER_AVAILABLE" = "true" ]; then
    echo "  📦 Building Docker image $DOCKER_IMAGE_TAG\n"
    docker build -t $DOCKER_IMAGE_TAG .
    docker push $DOCKER_IMAGE_TAG

    echo "--🚀 Deploying $SERVICE_NAME Cloud Run container...\n"
    gcloud beta run deploy "$SERVICE_NAME" \
      --image=$DOCKER_IMAGE_TAG \
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
  else
    echo "--🏗️ Docker is not available. Using Cloud Build..."
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
  fi
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



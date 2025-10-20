#!/bin/bash
PROJECT_ID="my-project-id"
PROJECT_NUMBER="my-project-number"
SERVICE_NAME="dubble-gui"
REGION="us-central1"
SERVICE_ACCOUNT="dubble-sa"

# --- User Access ---
# Add the email of the user or group you want to grant access to.
# You can also use group:group@example.com or serviceAccount:sa@project.iam.gserviceaccount.com
MEMBER_TO_GRANT_ACCESS="my-user@my-domain.com"

echo "Setting region..."
gcloud config set run/region $REGION


echo "Enabling necessary services..."
gcloud services enable \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    iap.googleapis.com \
    run.googleapis.com \
    iam.googleapis.com

echo "Creating IAP SA..."
gcloud beta services identity create \
    --service=iap.googleapis.com \
    --project=$PROJECT_ID

# 2. Create a dedicated service account for the app
echo "Creating service account..."
gcloud iam service-accounts create $SERVICE_ACCOUNT \
  --display-name="Dubble Service Account" \
  --project=$PROJECT_ID


echo "Granting IAP access to the Service..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"  \
    --role="roles/run.invoker"

echo "Granting Vertex AI user access to compute service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"


echo "Replacing placeholder variables in templates/index.html..."
sed -i "s/\$PROJECT_ID/$PROJECT_ID/g" templates/index.html
sed -i "s/\$REGION/$REGION/g" templates/index.html

echo "Deploying Cloud Run service..."
gcloud beta run deploy $SERVICE_NAME \
  --source . \
  --cpu 8 \
  --memory 32Gi \
  --region $REGION \
  --service-account "${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --no-allow-unauthenticated \
  --project=$PROJECT_ID \
  --iap

#For every user to authorize to use the application, the following commands must be executed

echo "Adding user to IAP..."
gcloud beta iap web add-iam-policy-binding \
  --resource-type=cloud-run \
  --service=$SERVICE_NAME \
  --project=$PROJECT_ID \
  --region=$REGION \
  --member="user:$MEMBER_TO_GRANT_ACCESS" \
  --role=roles/iap.httpsResourceAccessor \
  --condition=None

echo "Granting user access to service..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
  --region=$REGION \
  --member="user:$MEMBER_TO_GRANT_ACCESS" \
  --role="roles/run.invoker" \
  --project=$PROJECT_ID

echo " "
echo "✅ Deployment complete."
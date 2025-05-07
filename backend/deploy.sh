#!/bin/bash
# Read config variables
CONFIG_FILE="$(dirname $0)/deploy-config.sh"
if [ ! -r $CONFIG_FILE ]; then
	echo "ERROR: Config file '$CONFIG_FILE' not found. This file is needed to configure the application's settings."
	echo "Please run 'npm run start' before attempting to run this script."
	exit 1
fi
. $CONFIG_FILE

gcloud config set project $GCP_PROJECT_ID
gcloud services enable cloudresourcemanager.googleapis.com
gcloud auth application-default set-quota-project $GCP_PROJECT_ID
printf "\nINFO - GCP project set to '$GCP_PROJECT_ID' successfully!\n"

BUCKET_EXISTS=$(gcloud storage ls gs://$GCS_BUCKET >/dev/null 2>&1 && echo "true" || echo "false")
if "${BUCKET_EXISTS}"; then
	printf "\nWARN - Bucket '$GCS_BUCKET' already exists. Skipping bucket creation...\n"
else
	gcloud storage buckets create gs://$GCS_BUCKET --project=$GCP_PROJECT_ID --location=$GCP_REGION --uniform-bucket-level-access
	test $? -eq 0 || exit
	printf "\nINFO - Bucket '$GCS_BUCKET' created successfully in location '$GCP_REGION'!\n"
fi
printf "\nINFO - Setting 7 days retention policy on the bucket"
gcloud storage buckets update gs://$GCS_BUCKET --lifecycle-file=bucket_retention_policy.json

if "${CONFIGURE_APIS_AND_ROLES}"; then
	printf "\nINFO - Enabling GCP APIs...\n"
	gcloud services enable \
		aiplatform.googleapis.com \
		artifactregistry.googleapis.com \
		cloudbuild.googleapis.com \
		compute.googleapis.com \
		eventarc.googleapis.com \
		logging.googleapis.com \
		pubsub.googleapis.com \
		run.googleapis.com \
		script.googleapis.com \
		serviceusage.googleapis.com \
		storage.googleapis.com

	PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")
	STORAGE_SERVICE_ACCOUNT="service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com"
	EVENTARC_SERVICE_ACCOUNT="service-${PROJECT_NUMBER}@gcp-sa-eventarc.iam.gserviceaccount.com"
	COMPUTE_SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
	printf "\nINFO - Creating Service Agents and granting roles...\n"
	for SA in "storage.googleapis.com" "eventarc.googleapis.com"; do
		gcloud --no-user-output-enabled beta services identity create --project=$GCP_PROJECT_ID \
			--service="${SA}"
	done
	COMPUTE_SA_ROLES=(
		"roles/eventarc.eventReceiver"
		"roles/run.invoker"
		"roles/cloudfunctions.invoker"
		"roles/storage.objectAdmin"
		"roles/storage.admin"
		"roles/aiplatform.user"
		"roles/logging.logWriter"
		"roles/artifactregistry.createOnPushWriter"
		"roles/cloudbuild.builds.builder"
		"roles/run.invoker"
	)
	for COMPUTE_SA_ROLE in "${COMPUTE_SA_ROLES[@]}"; do
		gcloud --no-user-output-enabled projects add-iam-policy-binding \
			$GCP_PROJECT_ID \
			--member="serviceAccount:${COMPUTE_SERVICE_ACCOUNT}" \
			--role="${COMPUTE_SA_ROLE}"
	done
	gcloud --no-user-output-enabled projects add-iam-policy-binding \
		$GCP_PROJECT_ID \
		--member="serviceAccount:${STORAGE_SERVICE_ACCOUNT}" \
		--role="roles/pubsub.publisher"
	gcloud --no-user-output-enabled projects add-iam-policy-binding \
		$GCP_PROJECT_ID \
		--member="serviceAccount:${EVENTARC_SERVICE_ACCOUNT}" \
		--role="roles/eventarc.serviceAgent"
	printf "Operation finished successfully!\n"
fi

if $USE_CLOUD_BUILD; then
	printf "\nINFO - Using Cloud Build to deploy from source"
	gcloud beta run deploy ariel-process \
		--region=$GCP_REGION \
		--no-allow-unauthenticated \
                --no-gpu-zonal-redundancy \
		--source=. \
		--memory=32Gi \
		--cpu=8 \
		--gpu=1 \
		--gpu-type=nvidia-l4 \
		--max-instances=1 \
		--min-instances=0 \
		--timeout=600s \
		--concurrency=7 \
		--set-env-vars PROJECT_ID=$GCP_PROJECT_ID \
		--set-env-vars REGION=$GCP_REGION \
		--add-volume name=ariel-bucket,type=cloud-storage,bucket=$GCS_BUCKET \
		--add-volume-mount volume=ariel-bucket,mount-path=/tmp/ariel
else
	printf "\nINFO - Using local Docker build to speed up development and deployment"
	printf "\nINFO - Setting up Docker registry and pushing image into it"
	DOCKER_REPO_NAME=gps-docker-repo
	REPO_EXISTS=$(gcloud artifacts repositories describe $DOCKER_REPO_NAME --location=$GCP_REGION >/dev/null 2>&1 && echo "true" || echo "false")
	if "${REPO_EXISTS}"; then
		printf "\nWARN - Repository '$DOCKER_REPO_NAME' already exists in location '$GCP_REGION'. Skipping creation...\n"
	else
		printf "\nINFO Creating artifacts repository for docker images"
		gcloud artifacts repositories create $DOCKER_REPO_NAME --repository-format=docker \
			--location=$GCP_REGION --description="Google Professional Services images" \
			--project=$GCP_PROJECT_ID
		test $? -eq 0 || exit
		printf "\nINFO - Repository '$DOCKER_REPO_NAME' created successfully in location '$GCP_REGION'!\n"
		gcloud auth configure-docker $GCP_REGION-docker.pkg.dev
	fi

	ARTIFACT_POSITORY_NAME=$GCP_REGION-docker.pkg.dev/$GCP_PROJECT_ID/$DOCKER_REPO_NAME
	DOCKER_IMAGE_TAG=$ARTIFACT_POSITORY_NAME/ariel-process:latest

	printf "\nINFO Building Docker image for ariel processor\n"
	docker build -t $DOCKER_IMAGE_TAG .
	docker push $DOCKER_IMAGE_TAG

	printf "\nINFO - Deploying the 'ariel-process' Cloud Run container...\n"
	gcloud beta run deploy ariel-process \
		--region=$GCP_REGION \
		--no-allow-unauthenticated \
                --no-gpu-zonal-redundancy \
		--image=$DOCKER_IMAGE_TAG \
		--memory=32Gi \
		--cpu=8 \
		--gpu=1 \
		--gpu-type=nvidia-l4 \
		--max-instances=1 \
		--min-instances=0 \
		--timeout=600s \
		--concurrency=7 \
		--set-env-vars PROJECT_ID=$GCP_PROJECT_ID \
		--set-env-vars REGION=$GCP_REGION \
		--add-volume name=ariel-bucket,type=cloud-storage,bucket=$GCS_BUCKET \
		--add-volume-mount volume=ariel-bucket,mount-path=/tmp/ariel
fi

printf "\nINFO Setting up triggers from GCS to Ariel processor topic in Cloud Run\n"

NOTIFICATION_ETAG=$(gcloud storage buckets notifications list gs://$GCS_BUCKET --format='value("Notification Configuration".etag)')
if [ -z "$NOTIFICATION_ETAG" ]; then
	gcloud storage buckets notifications create gs://$GCS_BUCKET --topic=$PUBSUB_TOPIC --event-types="OBJECT_FINALIZE"
fi

SUBSCRIPTION_NAME=$(gcloud pubsub subscriptions describe ariel-process-subscription --format='value(name)')
if [ -z "$SUBSCRIPTION_NAME" ]; then
	SERVICE_URL=$(gcloud run services describe ariel-process --region $GCP_REGION --format='value(status.url)')
	gcloud pubsub subscriptions create ariel-process-subscription --topic $PUBSUB_TOPIC \
		--ack-deadline=600 \
		--push-endpoint=$SERVICE_URL/ \
		--push-auth-service-account="$COMPUTE_SERVICE_ACCOUNT"
fi

test $? -eq 0 || exit

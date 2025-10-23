# 5 steps video localization process GUI (to be merged in Ariel v2)

This document provides instructions on how to deploy the GUI for the 5 steps video localization process GUI to Google Cloud Run.

**Disclaimer: This is not an official Google product.**

## Prerequisites

- You have a Google Cloud project with billing enabled.
- You have the Google Cloud SDK (`gcloud` version >=  542.0.0) installed and authenticated.
- You have [buildpack](https://buildpacks.io/docs/for-platform-operators/how-to/integrate-ci/pack/) installed.
- You have the necessary permissions to create and manage Cloud Run services, service accounts, and IAM policies. Ideally project owner or editor role.
- If you want to make use of the Google Cloud Storage functionality, make sure the service account (`SERVICE ACCOUNT` below) and all the user have read & write access.

## Deployment

1.  **Edit the `deploy.sh` script:**

    Open the `deploy.sh` file and modify the following variables with your own values:

    -   `PROJECT_ID`: Your Google Cloud project ID.
    -   `PROJECT_NUMBER`: Your Google Cloud project number.
    -   `SERVICE_NAME`: The name you want to give your Cloud Run service.
    -   `REGION`: The Google Cloud region where you want to deploy the service (e.g., `us-central1`).
    -   `SERVICE_ACCOUNT`: The name for the new service account that will be created.
    -   `MEMBER_TO_GRANT_ACCESS`: The email of the user you want to grant access to (e.g., `example@google.com`).

2.  **Run the deployment script:**

    ```bash
    bash deploy.sh
    ```

    This script will:
    -   Enable the required Google Cloud APIs.
    -   Create a service account for the application.
    -   Deploy the application to Cloud Run.
    -   Set up Identity-Aware Proxy (IAP) to secure your application.
    -   Grant access to the user specified in `MEMBER_TO_GRANT_ACCESS`.

3.  **Configure OAuth Redirect URI:**

    After the script finishes, it will print the URL of your deployed service. i.e:
    https://dubble-gui-xxxxxxxx-uc.a.run.app

4. **Grant access to other users:**

    Repeat the last 2 commands in the `deploy.sh` script for every user you'd want to grant access:

    ```echo "Adding user to IAP..."
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
    --project=$PROJECT_ID```


##  Note
    - You can also build and deploy using the Dockerfile. Just replace the variables for project and location in the Dockerfile before build.
    - When the image is built and transferred to your Artifact Registry, you will need to deploy with a command like:

    ```bash
    gcloud run deploy dubble-gui \
        --image <your-image> \
        --port <port> \
        --cpu <number-of-cpus> \
        --memory <memory> \
        --region <region> \
        --platform managed \
        --no-allow-unauthenticated \
        --iap
    ```
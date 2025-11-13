# gTech Ads Ariel for AI Video Ad Dubbing

Ariel is a tool for translating video voice tracks. It provides an easy to use
web interface for uploading videos, creating translations, and redubbing the
video with translated audio.

## Deployment

Deploying Ariel involves two main steps: running the setup script to configure
your Google Cloud environment and then running the deployment script to deploy
the service to Cloud Run.

### Prerequisites

Before you begin, ensure you have the following installed and configured:

*   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (which
    includes `gcloud` and `gsutil`)
*   Authenticated with Google Cloud: `gcloud auth login`
*   A Google Cloud project created and the billing enabled.

### 1. Initial Setup

The `setup.sh` script is designed to automate the configuration of your Google
Cloud project. It will:

*   Prompt you for the GCP region to deploy the service in.
*   Confirm your Google Cloud Project ID.
*   Prompt for a Cloud Storage bucket name and create it for you.
*   Enable all the necessary Google Cloud APIs.
*   Create a dedicated service account for the Cloud Run service.
*   Grant the required IAM permissions to the service account and your user
    account.
*   Generate a `configuration.yaml` file with your project settings.

To run the setup script, execute the following command in your terminal:

```bash
./setup.sh
```

Follow the on-screen prompts to complete the setup process.

### 2. Deploy to Cloud Run

Once your environment is set up, you can deploy the application to Cloud Run
using the `deploy.sh` script.

This script will:

*   Read the configuration from `configuration.yaml`.
*   Build the container image using Google Cloud Build.
*   Deploy the service to Cloud Run with IAP (Identity-Aware Proxy) enabled for
    security.

To deploy the application, run the following command:

```bash
./deploy.sh
```

The script will output the URL of the deployed service once it's finished.

### Granting Access to Other Users

By default, only your user account will have access to the deployed application
(via IAP). To grant access to other users, run the following command for each
user:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:USER_EMAIL" \
    --role="roles/iap.httpsResourceAccessor"
```

Replace `YOUR_PROJECT_ID` with your Google Cloud project ID and `USER_EMAIL`
with the email address of the user you want to grant access to.

## Usage

Ariel is accessed using the web front end. To access it, navigate to the URL
displayed at the end of the deployment process.

To dub a new video:

### Initial Translation

1.  Click the "Select Video from Computer" button, select the video you want to
    dub from the file chooser, and click "Open" in your file chooser.
1.  Add the speakers by clicking the "⊕ Add Speaker" button. You must add a
    speaker for each speaker in the video, in the order they start speaking.
    1.  In the *Select Speaker Voice* dialog, you can perform several actions:
        *   Add a label for the speaker in the first text box.
        *   Search for a specific voice using the second text box.
        *   Preview a voice by clicking the play button next to it.
        *   Filter voices by gender by clicking the "Male" and "Female" buttons.
    1.  To select a voice, click on it in the list and then click the "Add
        Voice" button.
    1.  The selected voice will appear in the list of speakers. Repeat this for
        every speaker in the video.
1.  Select the original language of the video.
1.  Select the language you wish to translate the video to.
1.  You can choose to use the pro or flash version of Gemini using the toggle
    labeled "Gemini Model".
1.  You can choose to automatically speed up or slow down the translated speech
    to match the original by using the "Adjust Speed" toggle. Please note that
    this does not normally lead to the best results.
1.  If you have any additional instructions for the initial translation or
    dubbing, enter them in the text box labeled "Gemini Instructions". This can
    include things like words that should not be translated or the general tone
    of voice to use.
1.  Click the *Start Processing* button to start the initial dubbing. This can
    take a few minutes, so please be patient. If an error occurs, a message will
    be shown. Please try processing the video again and, if it continues to not
    work, open a bug so that we can help you.

### Adjusting the translation

Once the video has been processed, the edit screen will be displayed to allow
you to edit the dubbing.

In the *Video Settings* section you can change the initial settings for the
transcription, including the languages and voices.

On the timeline, you can drag utterances to change the starting time.

In the list of utterances, you can:

*   remove an utterance from the final video using the trashcan icon.
*   use the original audio in the final video via the mute icon.
*   edit the utterance using the pencil icon

#### Editing Utterances

After clicking the pencil icon for a specific utterance, there are a number of
actions you can take.

*   Edit the original transcription by changing the text in the *Original Text*
    text area.
*   Listen to the translated audio by clicking the speaker icon.
*   Edit the translation by changing the text in the *Translated Text* text
    area.
*   Update the translation by providing additional instructions in the
    *Translation Instructions* text area and then clicking the *Regenerate
    Translation* button.
*   Update the dubbed audio by providing additional instructions in the *Voice
    Intonation Instructions* text area and clicking the *Regenerate Dubbing*
    button.
*   Change the start time of the translated utterance in the final video by
    editing the number in the *Translated Start Time* text box.
*   Change the end time of the translated utterance in the final video by
    editing the number in the *Translated End Time* text box.
*   Change the speaker by selecting a new speaker in the *Speaker* drop down.
    You will also need to click the *Regenerate Dubbing* button to update the
    audio with the new speaker.

Once you are happy with your edits, you must click the *Save* button to save the
changes and have them applied to the final video.

Regenerating the translation will also automatically regenerate the dubbing so
that you can hear the updated audio before deciding to save it.

Changing the start or end time will automatically update the other time to
ensure the overall duration of the clip is correct.

### Generating the final video

Once you are satisfied with the individual utterances, click the *Generate
Video* button to create the final dubbed translation. This can take some time,
to please be patient.

Once the video is complete, it will be shown on the screen. You can preview the
video by clicking the play button in the video player.

To download the video or the audio, click the appropriate button on the screen.

If you aren't satisfied with the final output, you can click the *Go back to
editing* button to make additional changes.

To start dubbing a new video, you can click the *Start Over* button to return to
the app's start page.

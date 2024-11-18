<!--
Copyright 2024 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

      https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Ariel UI

Here, we provide a User Interface (UI) for Ariel.
The UI is an alternative to the provided Colab notebook. It enables you to
easily run video ad dubbing including full customization and editing of the
audio chunks.

<img src="./public/assets/ariel_ui.png" alt="Ariel UI screenshot">

## Updates

- November 2024: Initial release.

## Requirements

The Ariel UI is an [Angular](https://angular.dev/) based application that is contained within an Apps
Script project. To get started, you need the following:

- Google (Workspace) account.
- Google Cloud Project for running the Cloud Run backend and storing files in
  Google Cloud Storage (GCS).
- Up to date version of [Node.js, npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)

## Installation

### Prepare your deployment environment

- Log in to [clasp](https://github.com/google/clasp) via `clasp login`.
- Navigate to the [Apps Script settings](https://script.google.com/home/usersettings) page and enable the Apps Script API.
- Make sure your system has an up-to-date installation of the [gcloud CLI](https://cloud.google.com/sdk/docs/install), then login via `gcloud auth login`.
- Clone this repository via `git clone https://github.com/google-marketing-solutions/ariel` and `cd ariel`

### Deploy the Ariel UI

- From the ariel directory, run `npm run deploy`

Our installation script handles everything else for you. It installs all the
required cloud and angular UI componenents, enables the required APIs and
outputs a link to the Ariel UI. Once you click on the link, you will be asked to
provide the relevant permissions.

That's it, you should have Ariel UI running in your browser now.

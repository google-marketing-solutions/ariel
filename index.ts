/**
 * Copyright 2024 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *       https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import prompts from 'prompts';

import {
	getCurrentConfig,
	GCS_BUCKET_NAME_SUFFIX,
	setUserConfig,
	checkGcloudAuth,
	deployGcpComponents,
	createScriptProject,
	deployUi,
	sanitizeUserConfig,
	saveUserConfig,
} from './common';

(async () => {
	const oldConfig = getCurrentConfig();
	const gcpRegions = ['europe-west4', 'us-central1', 'asia-southeast1'];

	const response = await prompts([
		{
			type: 'text',
			name: 'gcpProjectId',
			message: `Enter your GCP Project ID [${oldConfig.gcpProjectId || 'None'}]`,
			initial: oldConfig.gcpProjectId,
			validate: (value: string) => (!value ? 'Required' : true),
		},
		{
			type: 'text',
			name: 'gcsBucket',
			message: `Enter a GCS bucket name [${oldConfig.gcsBucket}]]:`,
			initial: (prev: string) =>
				oldConfig.gcsBucket || `${prev}${GCS_BUCKET_NAME_SUFFIX}`,
		},
		{
			type: 'select',
			name: 'gcpRegion',
			message: `Enter a GCP region for the Ariel to run in [${oldConfig.gcpRegion}]'):`,
			initial: gcpRegions.indexOf(oldConfig.gcpRegion ?? 'europe-west4'),
			choices: gcpRegions.map((name) => {
				return { title: name, value: name };
			}),
		},
		{
			type: 'text',
			name: 'gcsLocation',
			message: `Enter a GCS location to store files in (can be multi-region like 'us' or single region like 'us-central1') [${oldConfig.gcsLocation}]):`,
			initial: oldConfig.gcsLocation,
		},
		{
			type: 'text',
			name: 'pubsubTopic',
			message: `Enter a Pub/Sub Topic name [${oldConfig.pubsubTopic}]:`,
			initial: oldConfig.pubsubTopic,
		},
		{
			type: 'toggle',
			name: 'deployUi',
			message: 'Should Ariel deploy the UI?',
			initial: oldConfig.deployUi,
			active: 'yes',
			inactive: 'no',
		},
		{
			type: 'toggle',
			name: 'deployBackend',
			message: 'Should Ariel deploy the backend?',
			initial: oldConfig.deployBackend,
			active: 'yes',
			inactive: 'no',
		},
		{
			type: 'toggle',
			name: 'configureApisAndRoles',
			message: 'Should APIs and Roles be configured?',
			initial: oldConfig.configureApisAndRoles,
			active: 'yes',
			inactive: 'no',
		},
		{
			type: 'toggle',
			name: 'useCloudBuild',
			message: 'Should Ariel use Cloud Build?',
			initial: oldConfig.useCloudBuild,
			active: 'yes',
			inactive: 'no',
		},
	]);

	const config = sanitizeUserConfig(response);
	saveUserConfig(config);

	if (response.deployBackend || response.deployUi) {
		setUserConfig(response);
	}

	if (response.deployBackend) {
		await checkGcloudAuth();
		deployGcpComponents();
	}
	if (response.deployUi) {
		await createScriptProject();
		deployUi();
	}
})();

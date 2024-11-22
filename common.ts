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

const fs = require('fs-extra'); // tslint:disable-line
const os = require('os'); // tslint:disable-line
const path = require('path'); // tslint:disable-line
const replace = require('replace'); // tslint:disable-line
const spawn = require('cross-spawn'); // tslint:disable-line

/**
 * Default Google Cloud Platform region.
 */
export const DEFAULT_GCP_REGION = 'us-central1';

/**
 * Default Google Cloud Storage location.
 */
export const DEFAULT_GCS_LOCATION = 'us';

/**
 * Default Pub/Sub topic.
 */
export const DEFAULT_PUBSUB_TOPIC = 'ariel-topic';

/**
 * Google Cloud Storage bucket name suffix.
 */
export const GCS_BUCKET_NAME_SUFFIX = '-ariel';

/**
 * Default value for configuring APIs and roles.
 */
export const DEFAULT_CONFIGURE_APIS_AND_ROLES = true;

/**
 * Default value for using Cloud Build.
 */
export const DEFAULT_USE_CLOUD_BUILD = true;

interface ConfigReplace {
	regex: string;
	replacement: string;
	path: string;
}

/**
 * Interface for Prompts response.
 */
export interface PromptsResponse {
	gcpProjectId: string;
	gcpRegion?: string;
	gcsLocation?: string;
	pubsubTopic?: string;
	gcsBucket?: string;
	configureApisAndRoles?: boolean;
	useCloudBuild?: boolean;
	deployBackend?: boolean;
	deployUi?: boolean;
}

/**
 * Async function to check if the user is logged in via clasp.
 */
async function isClaspLoggedIn() {
	return await fs.exists(path.join(os.homedir(), '.clasprc.json'));
}

/**
 * Async function to login via clasp if the user is not logged in.
 */
async function loginClasp() {
	const loggedIn = await isClaspLoggedIn();

	if (!loggedIn) {
		console.log('Logging in via clasp...');
		spawn.sync('clasp', ['login'], { stdio: 'inherit' });
	}
}

/**
 * Async function to check if the clasp configuration exists.
 */
async function isClaspConfigured(rootDir: string) {
	return (
		(await fs.exists(path.join(rootDir, '.clasp-dev.json'))) ||
		(await fs.exists(path.join(rootDir, 'dist', '.clasp.json')))
	);
}

/**
 * Function to extract the Google Sheets link from the clasp output.
 */
function extractSheetsLink(output: string) {
	const sheetsLink = output.match(/Google Sheet: ([^\n]*)/);

	return sheetsLink?.length ? sheetsLink[1] : 'Not found';
}

/**
 * Function to extract the Google Sheets Add-on script link from the clasp output.
 */
function extractScriptLink(output: string) {
	const scriptLink = output.match(/Google Sheets Add-on script: ([^\n]*)/);

	return scriptLink?.length ? scriptLink[1] : 'Not found';
}

/**
 * Async function to create a new Clasp project.
 */
async function createClaspProject(
	title: string,
	scriptRootDir: string,
	filesRootDir: string
) {
	fs.ensureDirSync(path.join(filesRootDir, scriptRootDir));
	const res = spawn.sync(
		'clasp',
		[
			'create',
			'--type',
			'sheets',
			'--rootDir',
			scriptRootDir,
			'--title',
			title,
		],
		{ encoding: 'utf-8' }
	);

	await fs.move(
		path.join(scriptRootDir, '.clasp.json'),
		path.join(filesRootDir, '.clasp-dev.json')
	);
	await fs.copyFile(
		path.join(filesRootDir, '.clasp-dev.json'),
		path.join(filesRootDir, '.clasp-prod.json')
	);
	await fs.remove(path.join(scriptRootDir, 'appsscript.json'));
	const output = res.output.join();

	return {
		sheetLink: extractSheetsLink(output),
		scriptLink: extractScriptLink(output),
	};
}

/**
 * Async function to check if the user is authenticated via gcloud.
 */
export async function checkGcloudAuth() {
	const gcloudAuthExists = await fs.exists(
		path.join(os.homedir(), '.config', 'gcloud', 'credentials.db')
	);
	const gcloudAppDefaultCredsExists = await fs.exists(
		path.join(
			os.homedir(),
			'.config',
			'gcloud',
			'application_default_credentials.json'
		)
	);
	if (!gcloudAuthExists) {
		console.log('Logging in via gcloud...');
		spawn.sync('gcloud auth login', { stdio: 'inherit', shell: true });
		console.log();
	}
	if (!gcloudAppDefaultCredsExists) {
		console.log('Setting Application Default Credentials (ADC) via gcloud...');
		spawn.sync('gcloud auth application-default login', {
			stdio: 'inherit',
			shell: true,
		});
		console.log();
	}
}

/**
 * Function to deploy Google Cloud Platform components.
 */
export function deployGcpComponents() {
	console.log('Deploying Ariel Backend onto Google Cloud Platform...');
	const res = spawn.sync('npm run deploy-backend', {
		stdio: 'inherit',
		shell: true,
	});
	if (res.status !== 0) {
		throw new Error('Failed to deploy GCP components.');
	}
}

/**
 * Async function to create an Apps Script project for the UI.
 */
export async function createScriptProject() {
	console.log();
	await loginClasp();

	const claspConfigExists = await isClaspConfigured('./ui');
	if (claspConfigExists) {
		return;
	}
	console.log();
	console.log('Creating Apps Script Project...');
	const res = await createClaspProject('Ariel', './dist', './ui');
	console.log();
	console.log('IMPORTANT -> Google Sheets Link:', res.sheetLink);
	console.log('IMPORTANT -> Apps Script Link:', res.scriptLink);
	console.log();
}

/**
 * Function to deploy the UI Web App.
 */
export function deployUi() {
	console.log('Deploying the UI Web App...');
	spawn.sync('npm run deploy-ui', { stdio: 'inherit', shell: true });
	console.log();
}

/**
 * Function to get the current user configuration.
 */
export function getCurrentConfig(): Config {
	if (fs.existsSync('.config.json')) {
		return JSON.parse(fs.readFileSync('.config.json'));
	} else {
		console.log('No config found, using default values');
		return {
			gcpRegion: DEFAULT_GCP_REGION,
			gcsLocation: DEFAULT_GCS_LOCATION,
			pubsubTopic: DEFAULT_PUBSUB_TOPIC,
			configureApisAndRoles: DEFAULT_CONFIGURE_APIS_AND_ROLES,
			useCloudBuild: DEFAULT_USE_CLOUD_BUILD,
			deployBackend: true,
			deployUi: true,
		};
	}
}

/**
 * Interface for the deployment configuration.
 */
export interface Config {
	gcpProjectId?: string;
	gcpRegion: string;
	gcsBucket?: string;
	gcsLocation: string;
	pubsubTopic: string;
	configureApisAndRoles: boolean;
	useCloudBuild: boolean;
	deployBackend: boolean;
	deployUi: boolean;
}

/**
 * Function to save the user configuration.
 */
export function saveUserConfig(config: Config) {
	fs.writeFileSync('.config.json', JSON.stringify(config));
}

/**
 * Function to sanitize the user configuration.
 * @param response The user response from the prompts.
 * @return The sanitized user configuration.
 */
export function sanitizeUserConfig(response: PromptsResponse): Config {
	const gcpRegion = response.gcpRegion || DEFAULT_GCP_REGION;
	const gcsLocation = response.gcsLocation || DEFAULT_GCS_LOCATION;
	const sanitizedProjectId = `${response.gcpProjectId
		.replace('google.com:', '')
		.replace('.', '-')
		.replace(':', '-')}`;
	const gcsBucket =
		response.gcsBucket || `${sanitizedProjectId}${GCS_BUCKET_NAME_SUFFIX}`;
	const pubsubTopic = response.pubsubTopic || DEFAULT_PUBSUB_TOPIC;
	const configureApisAndRoles = response.configureApisAndRoles ?? true;
	const useCloudBuild = response.useCloudBuild ?? true;
	const deployUi = response.deployUi ?? true;
	const deployBackend = response.deployBackend ?? true;

	const config: Config = {
		gcpProjectId: sanitizedProjectId,
		gcpRegion,
		gcsLocation,
		pubsubTopic,
		gcsBucket,
		configureApisAndRoles,
		useCloudBuild,
		deployUi,
		deployBackend,
	};
	return config;
}
/**
 * Set of files that will need value replacements
 */
const TEMPLATE_FILES = [
	'./backend/deploy-config.sh.TEMPLATE',
	'./ui/src/config.ts.TEMPLATE',
];

function copyFreshTemplateFiles() {
	TEMPLATE_FILES.forEach((file) => {
		fs.copySync(file, file.replace('.TEMPLATE', ''));
	});
}

function configReplace(config: ConfigReplace) {
	replace({
		regex: config.regex,
		replacement: config.replacement,
		paths: [config.path],
		recursive: false,
		silent: true,
	});
}

/**
 * Injects config values into templated config files.
 */
export function setUserConfig(config: Config) {
	console.log();
	console.log('Setting user configuration...');
	copyFreshTemplateFiles();

	if (config.deployBackend) {
		configReplace({
			regex: '<gcp-project-id>',
			replacement: config.gcpProjectId!,
			path: './backend/deploy-config.sh',
		});

		configReplace({
			regex: '<gcp-region>',
			replacement: config.gcpRegion,
			path: './backend/deploy-config.sh',
		});

		configReplace({
			regex: '<gcs-location>',
			replacement: config.gcsLocation,
			path: './backend/deploy-config.sh',
		});

		configReplace({
			regex: '<gcs-bucket>',
			replacement: config.gcsBucket!,
			path: './backend/deploy-config.sh',
		});

		configReplace({
			regex: '<pubsub-topic>',
			replacement: config.pubsubTopic,
			path: './backend/deploy-config.sh',
		});

		configReplace({
			regex: '<configure-apis-and-roles>',
			replacement: config.configureApisAndRoles ? 'true' : 'false',
			path: './backend/deploy-config.sh',
		});

		configReplace({
			regex: '<use-cloud-build>',
			replacement: config.useCloudBuild ? 'true' : 'false',
			path: './backend/deploy-config.sh',
		});
	}

	if (config.deployUi) {
		configReplace({
			regex: '<gcs-bucket>',
			replacement: config.gcsBucket!,
			path: './ui/src/config.ts',
		});
	}

	console.log();
}

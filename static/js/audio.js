/*
* Copyright 2025 Google LLC
*
* Licensed under the Apache License, Version 2.0 (the "License"); you may not
* use this file except in compliance with the License. You may obtain a copy
* of the License at
*
*   http://www.apache.org/licenses/LICENSE-2.0
*
* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
* WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
* License for the specific language governing permissions and limitations
* under the License.
*/

import {
    showToast
} from './utils.js';

/**
 * @param {object} videoData
 * @returns {Promise<HTMLAudioElement|null>}
 */
export async function generateAudio(videoData) {
    try {
        const response = await fetch('/generate_audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(videoData)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        const audio = new Audio(data.audio_url);
        showToast('Audio generated successfully', 'success');
        return audio;
    } catch (error) {
        console.error('Error generating audio:', error);
        showToast(error.message, 'error');
        return null;
    }
}

/**
 * @param {HTMLAudioElement|null} audio
 */
export function playAudio(audio) {
    if (audio) {
        audio.play();
    } else {
        showToast('No audio to play', 'error');
    }
}
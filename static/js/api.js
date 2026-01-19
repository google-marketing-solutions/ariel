/*
* Copyright 2025 Google LLC
*
* Licensed under the Apache License, Version 2.0 (the "License"); you may not
* use this file except in compliance with the License. You may obtain a copy
* of the License at
*
*   http://www.apache.org/licenses/LICENSE-2.0

* Unless required by applicable law or agreed to in writing, software
* distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
* WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
* License for the specific language governing permissions and limitations
* under the License.
*/

export function fetchLanguages(originalLanguage, translationLanguage) {
  return fetch('static/languages.json')
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      const defaultOption = new Option('Please select...', '', true, true);
      defaultOption.disabled = true;
      originalLanguage.add(defaultOption.cloneNode(true));
      translationLanguage.add(defaultOption.cloneNode(true));

      const gaLanguages = data.filter(lang => lang.readiness === 'GA');
      const previewLanguages = data.filter(
        lang => lang.readiness === 'Preview',
      );

      const gaOptgroup = document.createElement('optgroup');
      gaOptgroup.label = 'GA';
      gaLanguages.forEach(lang => {
        gaOptgroup.appendChild(new Option(lang.name, lang.code));
      });

      const previewOptgroup = document.createElement('optgroup');
      previewOptgroup.label = 'Preview';
      previewLanguages.forEach(lang => {
        previewOptgroup.appendChild(new Option(lang.name, lang.code));
      });

      originalLanguage.appendChild(gaOptgroup);
      originalLanguage.appendChild(previewOptgroup);

      translationLanguage.appendChild(gaOptgroup.cloneNode(true));
      translationLanguage.appendChild(previewOptgroup.cloneNode(true));
    });
}

export function fetchVoices() {
  return fetch('static/voices.json').then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

export function processVideo(formData) {
  return fetch('/process', {
    method: 'POST',
    body: formData,
  }).then(response => {
    if (!response.ok) {
      console.log(response);
      if (response.status === 413) {
        throw new Error(
          'Video file is too large for the server to process. Please upload a smaller video (limit is typically 32MB).',
        );
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

export function regenerateTranslation(videoData, utteranceIndex, instructions) {
  return fetch('/regenerate_translation', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      video: videoData,
      utterance: utteranceIndex,
      instructions: instructions,
    }),
  }).then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

export function regenerateDubbing(videoData, utteranceIndex, instructions) {
  return fetch('/regenerate_dubbing', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      video: videoData,
      utterance: utteranceIndex,
      instructions: instructions,
    }),
  }).then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

export function generateVideo(videoData) {
  return fetch('/generate_video', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(videoData),
  }).then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

export function completeVideo(videoData) {
  return fetch('/complete_video', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(videoData),
  }).then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

export function updateVideoSettings(updatedVideoData) {
  return fetch('/process', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updatedVideoData),
  }).then(response => {
    if (!response.ok) {
      if (response.status === 413) {
        throw new Error(
          'Video file is too large for the server to process. Please upload a smaller video (limit is typically 32MB).',
        );
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  });
}

// --- Regeneration Wrappers ---

export function runRegenerateTranslation(
  currentVideoData,
  utterance,
  index,
  instructions,
) {
  console.log('Regenerating translation for utterance:', index);
  return regenerateTranslation(currentVideoData, index, instructions).then(
    result => {
      utterance.translated_text = result.translated_text;
      utterance.translated_end_time =
        utterance.translated_start_time + result.duration;
      utterance.audio_url = result.audio_url;
      return utterance; // Return the updated utterance
    },
  );
}

export function runRegenerateDubbing(
  currentVideoData,
  utterance,
  index,
  instructions,
) {
  console.log('Regenerating dubbing for utterance:', index);
  return regenerateDubbing(currentVideoData, index, instructions).then(
    result => {
      utterance.audio_url = result.audio_url;
      utterance.duration = result.duration;
      utterance.translated_end_time =
        utterance.translated_start_time + result.duration;
      return utterance; // Return the updated utterance
    },
  );
}

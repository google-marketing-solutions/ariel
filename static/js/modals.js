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

import {showToast} from './utils.js';
import {appState} from './state.js';

let currentlyPlayingButton = null;
const audioPlayer = new Audio();

audioPlayer.addEventListener('ended', () => {
  if (currentlyPlayingButton) {
    currentlyPlayingButton.innerHTML = '<i class="bi bi-play-fill"></i>';
    currentlyPlayingButton = null;
  }
});

export function renderVoiceList(
  targetListElement,
  searchInput,
  genderFilterName,
  voices,
  onVoiceSelect,
  selectedVoiceName,
) {
  const searchTerm = searchInput.value.toLowerCase();
  const genderFilter = document.querySelector(
    `input[name="${genderFilterName}"]:checked`,
  ).value;

  const filteredVoices = voices.filter(voice => {
    const nameMatch = voice.name.toLowerCase().includes(searchTerm);
    const genderMatch = genderFilter === 'all' || voice.gender === genderFilter;
    return nameMatch && genderMatch;
  });

  targetListElement.innerHTML = '';

  filteredVoices.forEach(voice => {
    const item = document.createElement('div');
    item.classList.add(
      'list-group-item',
      'd-flex',
      'justify-content-between',
      'align-items-center',
    );

    if (voice.name === selectedVoiceName) {
      item.classList.add('active');
    }

    const voiceNameSpan = document.createElement('span');
    voiceNameSpan.textContent = voice.name;
    item.appendChild(voiceNameSpan);

    const controls = document.createElement('div');
    controls.classList.add('d-flex', 'align-items-center');

    const genderSpan = document.createElement('span');
    genderSpan.classList.add('badge', 'bg-secondary', 'me-3');
    genderSpan.textContent = voice.gender;
    controls.appendChild(genderSpan);

    if (voice.url) {
      const playButton = document.createElement('button');
      playButton.classList.add(
        'btn',
        'btn-sm',
        'btn-outline-secondary',
        'me-2',
      );
      playButton.innerHTML = '<i class="bi bi-play-fill"></i>';

      playButton.addEventListener('click', e => {
        e.stopPropagation();

        if (currentlyPlayingButton === playButton) {
          audioPlayer.pause();
          playButton.innerHTML = '<i class="bi bi-play-fill"></i>';
          currentlyPlayingButton = null;
        } else {
          if (currentlyPlayingButton) {
            currentlyPlayingButton.innerHTML =
              '<i class="bi bi-play-fill"></i>';
          }
          audioPlayer.src = voice.url;
          audioPlayer.play();
          playButton.innerHTML = '<i class="bi bi-stop-fill"></i>';
          currentlyPlayingButton = playButton;
        }
      });
      controls.appendChild(playButton);
    }

    const selectButton = document.createElement('button');
    selectButton.classList.add('btn', 'btn-sm', 'btn-primary');
    selectButton.textContent = 'Select';
    selectButton.addEventListener('click', e => {
      e.stopPropagation();
      onVoiceSelect(voice);
    });
    controls.appendChild(selectButton);

    item.appendChild(controls);

    targetListElement.appendChild(item);
  });
}

export function addVoice(
  voiceData,
  speakers,
  renderSpeakers,
  validateStartProcessing,
) {
  const speakerNameInput = document.getElementById('speaker-name-input');
  const speakerModal = bootstrap.Modal.getInstance(
    document.getElementById('speaker-modal'),
  );

  if (!voiceData) {
    showToast(
      'Selected voice data could not be found. Please try again.',
      'error',
    );
    return;
  }

  if (appState.editingSpeakerId) {
    // Edit existing speaker
    const speakerToEdit = speakers.find(
      s => s.id === appState.editingSpeakerId,
    );
    if (speakerToEdit) {
      speakerToEdit.voice = voiceData.name; // Store voice name
      speakerToEdit.voiceName = voiceData.name; // Store voice name for display
      speakerToEdit.gender = voiceData.gender;
      const customName = speakerNameInput.value.trim();
      if (customName) {
        speakerToEdit.name = customName;
      }
    }
  } else {
    // Add new speaker
    const customName = speakerNameInput.value.trim();
    const speaker = {
      id: `speaker_${speakers.length + 1}`,
      name: customName || `Speaker ${speakers.length + 1}`,
      voice: voiceData.name, // Store voice name
      voiceName: voiceData.name, // Store voice name for display
      gender: voiceData.gender,
    };
    speakers.push(speaker);
  }

  // Reset state and UI
  appState.editingSpeakerId = null;
  speakerNameInput.value = '';
  speakerModal.hide();
  validateStartProcessing();
  if (appState.isEditingVideoSettings) {
    // Do nothing here, main.js's hidden.bs.modal listener will call renderVideoSettingsEditor()
  } else {
    renderSpeakers();
  }
}

export function handleSpeakerModalClose() {
  audioPlayer.pause();
  if (currentlyPlayingButton) {
    currentlyPlayingButton.innerHTML = '<i class="bi bi-play-fill"></i>';
    currentlyPlayingButton = null;
  }
}

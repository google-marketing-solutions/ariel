import { showToast } from './utils.js';
import { appState } from './state.js';

let currentlyPlayingButton = null;
const audioPlayer = new Audio();

audioPlayer.addEventListener('ended', () => {
    if (currentlyPlayingButton) {
        currentlyPlayingButton.innerHTML = '<i class="bi bi-play-fill"></i>';
        currentlyPlayingButton = null;
    }
});

export function renderVoiceList(targetListElement, searchInput, genderFilterName, voices) {
    const searchTerm = searchInput.value.toLowerCase();
    const genderFilter = document.querySelector(`input[name="${genderFilterName}"]:checked`).value;

    const filteredVoices = voices.filter(voice => {
        const nameMatch = voice.name.toLowerCase().includes(searchTerm);
        const genderMatch = genderFilter === 'all' || voice.gender === genderFilter;
        return nameMatch && genderMatch;
    });

    targetListElement.innerHTML = '';

    filteredVoices.forEach(voice => {
        const item = document.createElement('div');
        item.classList.add('list-group-item', 'list-group-item-action', 'd-flex', 'justify-content-between', 'align-items-center');
       
        const voiceNameSpan = document.createElement('span');
        voiceNameSpan.classList.add('me-auto'); // Align left
        voiceNameSpan.textContent = voice.name;
        item.appendChild(voiceNameSpan);

        const genderSpan = document.createElement('span');
        genderSpan.classList.add('badge', 'bg-secondary', 'mx-auto'); // Center the badge
        genderSpan.textContent = voice.gender;
        item.appendChild(genderSpan);

        if (voice.url) {
            const playButton = document.createElement('button');
            playButton.classList.add('btn', 'btn-sm', 'btn-outline-secondary', 'ms-auto'); // Align right
            playButton.innerHTML = '<i class="bi bi-play-fill"></i>';

            playButton.addEventListener('click', (e) => {
                e.stopPropagation();

                if (currentlyPlayingButton === playButton) {
                    // Clicked the same button that is currently playing
                    audioPlayer.pause();
                    playButton.innerHTML = '<i class="bi bi-play-fill"></i>';
                    currentlyPlayingButton = null;
                } else {
                    // Clicked a new button
                    if (currentlyPlayingButton) {
                        // Stop the previously playing audio and reset its button
                        currentlyPlayingButton.innerHTML = '<i class="bi bi-play-fill"></i>';
                    }
                    audioPlayer.src = voice.url;
                    audioPlayer.play();
                    playButton.innerHTML = '<i class="bi bi-stop-fill"></i>';
                    currentlyPlayingButton = playButton;
                }
            });
            item.appendChild(playButton);
        }

        item.dataset.voiceName = voice.name;
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const currentActive = targetListElement.querySelector('.active');
            if (currentActive) {
                currentActive.classList.remove('active');
            }
            item.classList.add('active');
        });
        targetListElement.appendChild(item);
    });
}

export function addVoice(voices, speakers, renderSpeakers, validateStartProcessing) {
    const voiceListModal = document.getElementById('voice-list');
    const speakerNameInput = document.getElementById('speaker-name-input');
    const speakerModal = bootstrap.Modal.getInstance(document.getElementById('speaker-modal'));

    const selectedVoiceEl = voiceListModal.querySelector('.active');
    if (!selectedVoiceEl) {
        showToast('Please select a voice.', 'error');
        return;
    }

    const voiceName = selectedVoiceEl.dataset.voiceName;
    const voiceData = voices.find(v => v.name === voiceName);

    if (!voiceData) {
        showToast('Selected voice data could not be found. Please try again.', 'error');
        return;
    }

    if (appState.editingSpeakerId) {
        // Edit existing speaker
        const speakerToEdit = speakers.find(s => s.id === appState.editingSpeakerId);
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
            gender: voiceData.gender
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
        // This prevents double rendering and ensures the editor is refreshed correctly.
    } else {
        renderSpeakers(); // Only re-render the initial speaker list if not in editor mode
    }
}

export function handleSpeakerModalClose() {
    audioPlayer.pause();
    if (currentlyPlayingButton) {
        currentlyPlayingButton.innerHTML = '<i class="bi bi-play-fill"></i>';
        currentlyPlayingButton = null;
    }
}

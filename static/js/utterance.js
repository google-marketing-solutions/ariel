import { showToast } from './utils.js';
import { regenerateTranslation } from './api.js';
import { renderTimeline } from './timeline.js';

const MAX_TEXT_SNIPPET_LENGTH = 100;

export function renderUtterances(currentVideoData, speakers, videoDuration) {
    const utterancesList = document.getElementById('utterances-list');
    utterancesList.innerHTML = '';
    const fragment = document.createDocumentFragment();
    const utterances = currentVideoData.utterances;

    const voiceToNameMap = new Map();
    speakers.forEach(s => {
        voiceToNameMap.set(s.voice, s.name);
    });

    utterances.forEach((utterance, index) => {
        const speakerName = voiceToNameMap.get(utterance.speaker.voice) || utterance.speaker.voice;
        const utteranceCard = document.createElement('div');
        utteranceCard.classList.add('utterance-card');
        utteranceCard.innerHTML = `
                <div>
                    <h6 class="mb-0">U: ${index + 1}</h6>
                    <div class="utterance-content-wrapper">
                        <div class="utterance-card-content mt-2">
                            <p><strong>Original:</strong> ${utterance.original_text.substring(0, MAX_TEXT_SNIPPET_LENGTH)}...</p>
                            <p><strong>Translated:</strong> ${utterance.translated_text.substring(0, MAX_TEXT_SNIPPET_LENGTH)}...</p>
                            <p><strong>Speaker:</strong> ${speakerName}</p>
                            <div class="utterance-overlay" style="display: none;"></div>
                        </div>
                    </div>
                </div>
                <div class="d-flex flex-column">
                    <button class="btn btn-sm btn-outline-secondary remove-utterance-btn mb-2"><i class="bi bi-trash"></i></button>
                    <button class="btn btn-sm btn-outline-secondary mute-utterance-btn mb-2"><i class="bi bi-mic-mute"></i></button>
                    <button class="btn btn-sm btn-outline-secondary edit-utterance-btn"><i class="bi bi-pencil"></i></button>
                </div>
        `;

        const content = utteranceCard.querySelector('.utterance-card-content');
        const overlay = utteranceCard.querySelector('.utterance-overlay');

        // Set initial visual state based on flags
        if (utterance.removed) {
            content.classList.add('removed');
            overlay.textContent = 'No audio will be generated';
            overlay.style.display = 'flex';
        }
        if (utterance.muted) {
            content.classList.add('muted');
            overlay.textContent = 'Original audio will be used';
            overlay.style.display = 'flex';
        }

        // --- BUTTON LISTENERS ---

        const removeBtn = utteranceCard.querySelector('.remove-utterance-btn');
        removeBtn.addEventListener('click', () => {
            utterance.removed = !utterance.removed;
            // Ensure mute is cancelled if remove is activated
            if (utterance.removed && utterance.muted) {
                utterance.muted = false;
            }
            renderUtterances(currentVideoData, speakers, videoDuration);
            renderTimeline(currentVideoData, videoDuration, speakers);
        });

        const muteBtn = utteranceCard.querySelector('.mute-utterance-btn');
        muteBtn.addEventListener('click', () => {
            utterance.muted = !utterance.muted;
            // Ensure remove is cancelled if mute is activated
            if (utterance.muted && utterance.removed) {
                utterance.removed = false;
            }

            if (utterance.muted) {
                utterance.translated_start_time = utterance.original_start_time;
                utterance.translated_end_time = utterance.original_end_time;
            } else {
                utterance.translated_start_time = utterance.initial_translated_start_time;
                utterance.translated_end_time = utterance.initial_translated_end_time;
            }
            renderUtterances(currentVideoData, speakers, videoDuration);
            renderTimeline(currentVideoData, videoDuration, speakers);
        });

        const editBtn = utteranceCard.querySelector('.edit-utterance-btn');
        editBtn.addEventListener('click', () => {
            // Cancel mute/remove state before editing
            if (utterance.muted || utterance.removed) {
                utterance.muted = false;
                utterance.removed = false;
                utterance.translated_start_time = utterance.initial_translated_start_time;
                utterance.translated_end_time = utterance.initial_translated_end_time;
                renderUtterances(currentVideoData, speakers, videoDuration);
                renderTimeline(currentVideoData, videoDuration, speakers);
            }
            editUtterance(utterance, index, currentVideoData, speakers, videoDuration);
        });

        fragment.appendChild(utteranceCard);
    });
    utterancesList.appendChild(fragment);
}

export function editUtterance(utterance, index, currentVideoData, speakers, videoDuration) {
    const utteranceEditor = document.getElementById('utterance-editor');
    const utteranceEditorContent = document.getElementById('utterance-editor-content');
    const confirmationModal = new bootstrap.Modal(document.getElementById('confirmation-modal'));

    console.log('Editing utterance:', JSON.stringify(utterance, null, 2)); // DEBUG

    const originalDuration = (utterance.original_end_time - utterance.original_start_time).toFixed(2);
    const translatedDuration = (utterance.translated_end_time - utterance.translated_start_time).toFixed(2);

    utteranceEditor.style.display = 'block';
    utteranceEditor.dataset.utteranceId = utterance.id;
    utteranceEditorContent.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-1">
            <label class="form-label mb-0">Original Text</label>
            <span class="badge bg-secondary">${originalDuration}s</span>
        </div>
        <textarea id="original-text-area" class="form-control" rows="3" readonly>${utterance.original_text}</textarea>

        <div class="d-flex justify-content-between align-items-center mt-3 mb-1">
            <label class="form-label mb-0">Translated Text</label>
            <span class="badge bg-secondary">${translatedDuration}s</span>
        </div>
        <div class="d-flex align-items-center">
            <textarea id="translated-text-area" class="form-control" rows="3">${utterance.translated_text}</textarea>
            <button class="btn btn-sm btn-outline-secondary ms-2 text-to-speech-icon" data-text-type="translated"><i class="bi bi-volume-up-fill"></i></button>
        </div>

        <div class="mb-3">
            <label class="form-label">Translation instructions</label>
            <textarea id="gemini-prompt-input" rows="2" class="form-control" placeholder="Translation instructions for Gemini..."></textarea>
        </div>

        <div class="mt-3">
            <label class="form-label">Voice Intonation Instructions</label>
            <textarea id="intonation-instructions-area" class="form-control" rows="2" placeholder="e.g., speak faster, with a happy tone">${utterance.instructions || ''}</textarea>
        </div>

        <div class="row mt-3">
            <div class="col-6">
                <label class="form-label">Original Start Time</label>
                <input type="text" class="form-control" value="${utterance.original_start_time}" readonly>
            </div>
            <div class="col-6">
                <label class="form-label">Original End Time</label>
                <input type="text" class="form-control" value="${utterance.original_end_time}" readonly>
            </div>
        </div>
        <div class="row mt-3">
            <div class="col-6">
                <label class="form-label">Translated Start Time</label>
                <input id="translated-start-time-input" type="text" class="form-control" value="${utterance.translated_start_time}">
            </div>
            <div class="col-6">
                <label class="form-label">Translated End Time</label>
                <input id="translated-end-time-input" type="text" class="form-control" value="${utterance.translated_end_time}">
            </div>
        </div>
        <div id="translated-overlap-warning" class="alert alert-warning mt-2" style="border-color: #ffc107; background-color: transparent; display: none;"></div>

        <div class="mb-3 mt-3">
            <label class="form-label">Speaker</label>
            <select id="speaker-select" class="form-select">
                ${speakers.map(s => `<option value="${s.voice}" ${s.voice === utterance.speaker.voice ? 'selected' : ''}>${s.name}</option>`).join('')}
            </select>
        </div>
        <button id="regenerate-translation-btn" class="btn btn-primary">Regenerate Translation</button>
        <button id="regenerate-dubbing-btn" class="btn btn-success">Regenerate Dubbing</button>
        <button id="save-utterance-btn" class="btn btn-info">Save</button>
    `;

    const regenerateTranslationBtn = utteranceEditorContent.querySelector('#regenerate-translation-btn');
    const regenerateDubbingBtn = utteranceEditorContent.querySelector('#regenerate-dubbing-btn');
    const saveUtteranceBtn = utteranceEditorContent.querySelector('#save-utterance-btn');

    const checkAndHandleChanges = () => {
        const currentTranslatedText = utteranceEditorContent.querySelector('#translated-text-area').value;
        const currentInstructions = utteranceEditorContent.querySelector('#intonation-instructions-area').value;
        const currentSpeaker = utteranceEditorContent.querySelector('#speaker-select').value;
        const currentGeminiPrompt = utteranceEditorContent.querySelector('#gemini-prompt-input').value;

        const hasChanges = currentTranslatedText !== initialTranslatedText ||
                         currentInstructions !== initialInstructions ||
                         currentSpeaker !== initialSpeaker ||
                         currentGeminiPrompt !== initialGeminiPrompt;

        if (hasChanges) {
            confirmationModal.show();
            return true; // Indicate that changes were detected
        }
        return false; // Indicate no changes
    };

    const saveUtteranceChanges = () => {
        utterance.translated_text = utteranceEditorContent.querySelector('#translated-text-area').value;
        utterance.instructions = utteranceEditorContent.querySelector('#intonation-instructions-area').value;
        utterance.speaker.voice = utteranceEditorContent.querySelector('#speaker-select').value;
        utterance.translated_start_time = parseFloat(utteranceEditorContent.querySelector('#translated-start-time-input').value);
        utterance.translated_end_time = parseFloat(utteranceEditorContent.querySelector('#translated-end-time-input').value);

        // Update initial values after saving
        initialTranslatedText = utterance.translated_text;
        initialInstructions = utterance.instructions;
        initialSpeaker = utterance.speaker.voice;
        // initialGeminiPrompt remains as it's not directly saved to utterance

        renderTimeline(currentVideoData, videoDuration, speakers);
        renderUtterances(currentVideoData, speakers, videoDuration);
        utteranceEditor.style.display = 'none';
        // Notify the app that the timeline has changed
        document.dispatchEvent(new CustomEvent('timeline-changed'));
    };

    regenerateTranslationBtn.addEventListener('click', () => {
        console.log('Regenerating translation...');
        regenerateTranslation(currentVideoData, index, document.querySelector('#gemini-prompt-input').value)
            .then(result => {
                utterance.translated_text = result.translated_text;
                utteranceEditorContent.querySelector('#translated-text-area').value = result.translated_text;
                utterance.translated_end_time = utterance.translated_start_time + result.duration;
                utteranceEditorContent.querySelector('#translated-end-time-input').value = utterance.translated_start_time + result.duration;
                utterance.audio_url = result.audio_url;
            });
    });

    regenerateDubbingBtn.addEventListener('click', () => {
        if (!checkAndHandleChanges()) {
            console.log('Regenerating dubbing...');
            // TODO: Implement actual regeneration logic
        }
    });

    saveUtteranceBtn.addEventListener('click', saveUtteranceChanges);

    // Store initial values
    let initialTranslatedText = utterance.translated_text;
    let initialInstructions = utterance.instructions || '';
    let initialSpeaker = utterance.speaker.voice;
    let initialGeminiPrompt = ''; // Assuming it's always empty initially

    const closeButton = document.getElementById('close-utterance-editor');
    closeButton.addEventListener('click', () => {
        if (!checkAndHandleChanges()) {
            utteranceEditor.style.display = 'none';
        }
    });

    // Add event listeners for the text-to-speech icons
    setupTextToSpeechListeners(utterance, utteranceEditorContent);

    function setupTextToSpeechListeners(utterance, containerElement) {
        const ttsIcons = containerElement.querySelectorAll('.text-to-speech-icon');
        ttsIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                const textType = e.target.dataset.textType;
                let textToSpeak = '';
                if (textType === 'original') {
                    textToSpeak = utterance.original_text;
                } else if (textType === 'translated') {
                    textToSpeak = containerElement.querySelector('#translated-text-area').value;
                }
                console.log(`Playing ${textType} text: ${textToSpeak}`);
                const audio = new Audio(utterance.audio_url);
                audio.play();
                audio.currentTime = 0;
            });
        });
    }

    // Initialize tooltips
    initializeTooltips(utteranceEditorContent);

    function initializeTooltips(containerElement) {
        const tooltipTriggerList = [].slice.call(containerElement.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Initial overlap check
    const overlapMessages = checkOverlap(utterance, utterances);
    const warningBox = utteranceEditorContent.querySelector('#translated-overlap-warning');
    if (overlapMessages.length > 0) {
        warningBox.innerHTML = overlapMessages.join('<br>');
        warningBox.style.display = 'block';
    } else {
        warningBox.style.display = 'none';
    }
}

import { showToast } from './utils.js';
import { regenerateDubbing, regenerateTranslation, runRegenerateDubbing, runRegenerateTranslation } from './api.js';
import { renderTimeline } from './timeline.js';

let activeEditorSession = null;

function hasUnsavedChanges() {
    if (!activeEditorSession) {
        return false;
    }

    // Check if the editor is even visible
    const utteranceEditor = document.getElementById('utterance-editor');
    if (!utteranceEditor || utteranceEditor.style.display === 'none') {
        activeEditorSession = null; // Reset if editor is not visible
        return false;
    }

    const initial = activeEditorSession.initialState;
    return (
        document.getElementById('original-text-area').value !== initial.original_text ||
        document.getElementById('translated-text-area').value !== initial.translated_text ||
        document.getElementById('intonation-instructions-area').value !== (initial.instructions || '') ||
        document.getElementById('speaker-select').value !== initial.speaker.voice ||
        parseFloat(document.getElementById('translated-start-time-input').value) !== initial.translated_start_time ||
        parseFloat(document.getElementById('translated-end-time-input').value) !== initial.translated_end_time
    );
}

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
                            <p><strong>Speaker:</strong> ${speakerName} <i class="ms-2 bi ${utterance.speaker.gender === 'Male' ? 'bi-gender-male' : 'bi-gender-female'}"></i></p>
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
    if (activeEditorSession && activeEditorSession.id !== utterance.id && hasUnsavedChanges()) {
        showToast('Please save or discard your changes before editing another utterance.', 'warning');
        return;
    }

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
        <textarea id="original-text-area" class="form-control" rows="3">${utterance.original_text}</textarea>

        <div class="d-flex justify-content-between align-items-center mt-3 mb-1">
            <label class="form-label mb-0">Translated Text</label>
            <span id="translated-duration" class="badge bg-secondary">${translatedDuration}s</span>
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

    // Set up the new editor session
    activeEditorSession = {
        id: utterance.id,
        initialState: { ...utterance, instructions: utterance.instructions || '' },
        utteranceObject: utterance
    };

    const saveUtteranceChanges = (closeEditor = true) => {
        utterance.original_text = document.getElementById('original-text-area').value;
        utterance.translated_text = document.getElementById('translated-text-area').value;
        utterance.instructions = document.getElementById('intonation-instructions-area').value;
        utterance.speaker.voice = document.getElementById('speaker-select').value;
        utterance.translated_start_time = parseFloat(document.getElementById('translated-start-time-input').value);
        utterance.translated_end_time = parseFloat(document.getElementById('translated-end-time-input').value);

        renderTimeline(currentVideoData, videoDuration, speakers);
        renderUtterances(currentVideoData, speakers, videoDuration);
        if (closeEditor) {
            utteranceEditor.style.display = 'none';
            activeEditorSession = null; // Clear session
        }
        document.dispatchEvent(new CustomEvent('timeline-changed'));
    };

    document.getElementById('save-utterance-btn').addEventListener('click', () => {
        saveUtteranceChanges();
    });

    document.getElementById('regenerate-translation-btn').addEventListener('click', () => {
        utterance.original_text = document.getElementById('original-text-area').value;
        const instructions = document.querySelector('#gemini-prompt-input').value;
        runRegenerateTranslation(currentVideoData, utterance, index, instructions)
            .then((updatedUtterance) => {
                currentVideoData.utterances[index] = updatedUtterance;
                document.getElementById('translated-text-area').value = updatedUtterance.translated_text;
                showToast('Translation regenerated successfully!', 'success');
            })
            .catch(error => {
                console.error('Error regenerating translation:', error);
                showToast('Failed to regenerate translation.', 'error');
            });
    });

    document.getElementById('regenerate-dubbing-btn').addEventListener('click', () => {
        const instructions = document.getElementById('intonation-instructions-area').value;
        utterance.speaker.voice = document.getElementById('speaker-select').value;
        runRegenerateDubbing(currentVideoData, utterance, index, instructions)
            .then((updatedUtterance) => {
                currentVideoData.utterances[index] = updatedUtterance;
                document.getElementById('translated-end-time-input').value = updatedUtterance.translated_end_time
                document.getElementById('translated-duration').innerText = (updatedUtterance.translated_end_time - updatedUtterance.translated_start_time).toFixed(2);
                renderTimeline(currentVideoData, videoDuration, speakers);
                showToast('Dubbing regenerated successfully!', 'success');
            })
            .catch(error => {
                console.error('Error regenerating dubbing:', error);
                showToast('Failed to regenerate dubbing.', 'error');
            });
    });

    function setupTextToSpeechListeners(utterance, containerElement) {
        const ttsIcons = containerElement.querySelectorAll('.text-to-speech-icon');
        ttsIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                const textType = e.currentTarget.dataset.textType;
                let textToSpeak = '';
                if (textType === 'original') {
                    textToSpeak = utterance.original_text;
                } else if (textType === 'translated') {
                    textToSpeak = containerElement.querySelector('#translated-text-area').value;
                }
                if (utterance.audio_url) {
                    const audio = new Audio(utterance.audio_url);
                    audio.play();
                    audio.currentTime = 0;
                }
            });
        });
    }

    setupTextToSpeechListeners(utterance, utteranceEditorContent);

    const closeEditorBtn = utteranceEditor.querySelector('.btn-close');
    closeEditorBtn.addEventListener('click', () => {
        if (hasUnsavedChanges()) {
            const modalEl = document.getElementById('confirmation-modal');
            const modalTitle = modalEl.querySelector('.modal-title');
            const modalBody = modalEl.querySelector('.modal-body');
            const confirmBtn = modalEl.querySelector('#confirm-close-btn');

            modalTitle.textContent = 'Discard Changes?';
            modalBody.innerHTML = '<p>You have unsaved changes. Are you sure you want to close without saving?</p>';
            confirmBtn.textContent = 'Yes, Discard';
            confirmBtn.className = 'btn btn-danger';

            const yesDiscardHandler = () => {
                utteranceEditor.style.display = 'none';
                activeEditorSession = null; // Clear session
                confirmationModal.hide();
                // Revert changes in the data model
                Object.assign(activeEditorSession.utteranceObject, activeEditorSession.initialState);
                renderTimeline(currentVideoData, videoDuration, speakers);
                renderUtterances(currentVideoData, speakers, videoDuration);
            };

            const noDiscardHandler = () => {
                confirmationModal.hide();
            };

            confirmBtn.addEventListener('click', yesDiscardHandler, { once: true });
            modalEl.addEventListener('hidden.bs.modal', noDiscardHandler, { once: true });

            confirmationModal.show();
        } else {
            utteranceEditor.style.display = 'none';
            activeEditorSession = null; // Clear session
        }
    });
}

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

import { completeVideo, fetchLanguages, fetchVoices, generateVideo, processVideo, runRegenerateDubbing, runRegenerateTranslation } from './api.js';
import { addVoice, handleSpeakerModalClose, renderVoiceList } from './modals.js';
import { appState } from './state.js';
import { renderTimeline } from './timeline.js';
import { showToast } from './utils.js';
import { checkZeroDurationUtterances, renderUtterances } from './utterance.js';

document.addEventListener('DOMContentLoaded', () => {
    // Instantiate templates
    const templates = [
        'results-view-template',
        'speaker-modal-template',
        'edit-speaker-voice-modal-template',
        'confirmation-modal-template',
        'thinking-popup-template',
        'generated-video-view-template',
        'completed-video-template'
    ];
    templates.forEach(id => {
        const template = document.getElementById(id);
        if (template) {
            document.body.appendChild(template.content.cloneNode(true));
        }
    });

    // Main elements
    const videoPlaceholder = document.getElementById('video-placeholder');
    const videoDropZone = document.getElementById('video-drop-zone');
    const videoInput = document.getElementById('video-input');
    const selectVideoComputerBtn = document.getElementById('select-video-computer');
    const videoPreview = document.getElementById('video-preview');
    const originalLanguage = document.getElementById('original-language');
    const translationLanguage = document.getElementById('target-language');
    const geminiInstructions = document.getElementById('gemini-instructions');
    const startProcessingBtn = document.getElementById('start-processing-btn');

    const geminiModelToggle = document.getElementById('gemini-model-toggle');
    const geminiModelLabel = document.getElementById('gemini-model-label');

    const adjustSpeedToggle = document.getElementById('adjust-speed-toggle');
    const adjustSpeedLabel = document.getElementById('adjust-speed-label');

    // Speakers
    const addSpeakerBtn = document.getElementById('add-speaker-btn');
    const speakerList = document.getElementById('speaker-list');
    const voiceSearch = document.getElementById('voice-search');
    const voiceListModal = document.getElementById('voice-list');

    // Results View
    const mainContent = document.querySelector('.main-content');
    const resultsView = document.getElementById('results-view');
    const videoSettingsContent = document.getElementById('video-settings-content');
    const resultsVideoPreview = document.getElementById('results-video-preview');
    const editVideoSettingsBtn = document.getElementById('edit-video-settings-btn');
    const generateVideoBtn = document.getElementById('generate-video-btn');
    const resetTimelineBtn = document.getElementById('reset-timeline-btn');

    // Modals
    const speakerModalEl = document.getElementById('speaker-modal');
    const speakerModal = new bootstrap.Modal(speakerModalEl);
    const confirmCloseBtn = document.getElementById('confirm-close-btn');
    const editSpeakerVoiceModal = new bootstrap.Modal(document.getElementById('edit-speaker-voice-modal'));
    const editVoiceSearch = document.getElementById('edit-voice-search');
    const editVoiceListModal = document.getElementById('edit-voice-list');
    const saveVoiceBtn = document.getElementById('save-voice-btn');

    // Generated Video View elements
    const generatedVideoView = document.getElementById('generated-video-view');
    const generatedVideoPreview = document.getElementById('generated-video-preview');
    const downloadVideoButton = document.getElementById('download-video-button');
    const downloadVocalsButton = document.getElementById('download-vocals-button');
    const downloadVocalsMusicButton = document.getElementById('download-vocals-music-button');
    const goBackToEditingButton = document.getElementById('go-back-to-editing-button');
    const startOverButton = document.getElementById('start-over-button');

    // Completed Video Modal
    const completedVideoModal = new bootstrap.Modal(document.getElementById('completed-video-modal'));
    const completedVideoVideo = document.getElementById('completed-video-video');

    // Thinking Popup
    const thinkingPopup = document.getElementById('thinking-popup');
    const thinkingPopupContent = document.querySelector('.thinking-popup-content');
    const arielLogo = document.createElement('img');
    const animatedDots = document.createElement('span');
    let dotAnimationInterval;
    let phraseChangeInterval;

    const thinkingPhrases = [
        "Spinning the gears",
        "Heating up CPUs",
        "Flexing Gemini",
        "Machine at work"
    ];

    function startThinkingAnimation() {
        thinkingPopup.style.display = 'flex';
        arielLogo.classList.add('ariel-logo-animated');
        thinkingWord.textContent = 'Thinking'; // Set initial text
        let dotCount = 0;
        dotAnimationInterval = setInterval(() => {
            dotCount = (dotCount + 1) % 4;
            animatedDots.textContent = '.'.repeat(dotCount);
        }, 500);

        phraseChangeInterval = setInterval(() => {
            let currentPhrase = thinkingWord.textContent;
            let nextPhrase = currentPhrase;
            while (nextPhrase === currentPhrase) {
                const randomIndex = Math.floor(Math.random() * thinkingPhrases.length);
                nextPhrase = thinkingPhrases[randomIndex];
            }
            thinkingWord.textContent = nextPhrase;
        }, 10000); // 10 seconds
    }

    function stopThinkingAnimation() {
        thinkingPopup.style.display = 'none';
        arielLogo.classList.remove('ariel-logo-animated');
        clearInterval(dotAnimationInterval);
        clearInterval(phraseChangeInterval);
        animatedDots.textContent = '';
    }

    let voices = [];
    let speakers = [];
    let currentVideoData = null;
    let videoDuration = 0;
    let currentEditingVoiceName = null;

    function validateStartProcessing() {
        const videoSelected = videoInput.files.length > 0;
        const speakersSelected = speakers.length > 0;
        const originalLangSelected = originalLanguage.value !== '';
        const translationLangSelected = translationLanguage.value !== '';

        startProcessingBtn.disabled = !(videoSelected && speakersSelected && originalLangSelected && translationLangSelected);
    }

    function displayVideo(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            videoPreview.src = e.target.result;
            videoPreview.style.display = 'block';
            videoDropZone.style.display = 'none';
            videoPlaceholder.classList.add('video-selected');
        };
        reader.readAsDataURL(file);
    }

    function renderSpeakers() {
        speakerList.innerHTML = '';
        speakers.forEach(speaker => {
            const speakerCard = document.createElement('div');
            speakerCard.className = 'speaker-card';
            speakerCard.dataset.speakerId = speaker.id;
            speakerCard.innerHTML = `
                <div class="speaker-info">
                    <div class="speaker-name">${speaker.name}</div>
                    <div class="speaker-details">
                        <span class="speaker-voice">${speaker.voiceName}</span>
                        <i class="ms-2 bi ${speaker.gender === 'Male' ? 'bi-gender-male' : 'bi-gender-female'}"></i>
                    </div>
                </div>
                <div class="speaker-actions">
                    <button class="btn btn-sm btn-outline-secondary edit-speaker-btn d-flex align-items-center justify-content-center" data-speaker-id="${speaker.id}"><i class="bi bi-pencil"></i></button>
                    <button class="btn-close" aria-label="Remove"></button>
                </div>
            `;
            speakerList.appendChild(speakerCard);
        });
    }

    const onVoiceSelect = (voice) => {
        addVoice(voice, speakers, renderSpeakers, validateStartProcessing);
    };

    // --- Initializations ---
    fetchLanguages(originalLanguage, translationLanguage).catch(error => {
        console.error('Error fetching languages:', error);
        showToast('Could not load language data. Please refresh the page.', 'error');
    });

    fetchVoices()
        .then(data => {
            voices = data.voices;
            renderVoiceList(voiceListModal, voiceSearch, 'gender-filter', voices, onVoiceSelect, currentEditingVoiceName);
            renderVoiceList(editVoiceListModal, editVoiceSearch, 'edit-gender-filter', voices, onVoiceSelect, null);
        })
        .catch(error => {
            console.error('Error fetching voices:', error);
            showToast('Could not load voice data. Please refresh the page.', 'error');
        });

    // Setup thinking popup
    thinkingPopupContent.innerHTML = '';
    arielLogo.src = 'static/Image/Ariel_Logo.png';
    arielLogo.id = 'ariel-logo-animation';
    arielLogo.style.width = '150px';
    arielLogo.style.height = 'auto';
    arielLogo.style.marginBottom = '20px';
    thinkingPopupContent.appendChild(arielLogo);
    const thinkingContainer = document.createElement('div');
    thinkingContainer.style.display = 'flex';
    thinkingContainer.style.justifyContent = 'center';
    thinkingContainer.style.alignItems = 'baseline';
    const thinkingWord = document.createElement('span');
    thinkingWord.textContent = 'Thinking';
    thinkingWord.style.marginRight = '5px';
    thinkingContainer.appendChild(thinkingWord);
    animatedDots.style.width = '20px';
    animatedDots.style.textAlign = 'left';
    thinkingContainer.appendChild(animatedDots);
    thinkingPopupContent.appendChild(thinkingContainer);

    // --- Event Listeners ---
    editVideoSettingsBtn.addEventListener('click', () => {
        appState.isEditingVideoSettings = true;
        renderVideoSettingsEditor();
    });
    geminiModelLabel.textContent = 'Flash';
    geminiModelToggle.addEventListener('change', () => {
        geminiModelLabel.textContent = geminiModelToggle.checked ? 'Pro' : 'Flash';
    });

    adjustSpeedToggle.addEventListener('change', () => {
        adjustSpeedLabel.textContent = adjustSpeedToggle.checked ? 'Yes' : 'No';
    });

    selectVideoComputerBtn.addEventListener('click', () => videoInput.click());
    videoInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            displayVideo(file);
        }
        validateStartProcessing();
    });

    videoDropZone.addEventListener('dragover', (e) => e.preventDefault());
    videoDropZone.addEventListener('drop', (event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file && file.type.startsWith('video/')) {
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            videoInput.files = dataTransfer.files;
            displayVideo(file);
        }
        validateStartProcessing();
    });

    originalLanguage.addEventListener('change', validateStartProcessing);
    translationLanguage.addEventListener('change', validateStartProcessing);

    addSpeakerBtn.addEventListener('click', () => {
        currentEditingVoiceName = null;
        speakerModal.show();
    });

    speakerModalEl.addEventListener('shown.bs.modal', () => {
        // Reset filters and search when modal opens
        document.getElementById('gender-all').checked = true;
        voiceSearch.value = '';
        renderVoiceList(voiceListModal, voiceSearch, 'gender-filter', voices, onVoiceSelect, currentEditingVoiceName);

        // Scroll to selected voice if editing
        const activeVoiceElement = voiceListModal.querySelector('.active');
        if (activeVoiceElement) {
            activeVoiceElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });

    speakerModalEl.addEventListener('hidden.bs.modal', () => {
        if (appState.isEditingVideoSettings) {
            renderVideoSettingsEditor(); // Re-render the editor to reflect changes
        }
        // Reset modal to its default "add" state when closed
        appState.editingSpeakerId = null;
        currentEditingVoiceName = null;
        speakerModalEl.querySelector('.modal-title').textContent = 'Select Speaker Voice';
        handleSpeakerModalClose();
    });

    voiceSearch.addEventListener('input', () => renderVoiceList(voiceListModal, voiceSearch, 'gender-filter', voices, onVoiceSelect, currentEditingVoiceName));
    document.querySelectorAll('input[name="gender-filter"]').forEach(radio => {
        radio.addEventListener('change', () => renderVoiceList(voiceListModal, voiceSearch, 'gender-filter', voices, onVoiceSelect, currentEditingVoiceName));
    });

    editVoiceSearch.addEventListener('input', () => renderVoiceList(editVoiceListModal, editVoiceSearch, 'edit-gender-filter', voices, onVoiceSelect, null));
    document.querySelectorAll('input[name="edit-gender-filter"]').forEach(radio => {
        radio.addEventListener('change', () => renderVoiceList(editVoiceListModal, editVoiceSearch, 'edit-gender-filter', voices, onVoiceSelect, null));
    });

    speakerList.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.edit-speaker-btn');
        if (editBtn) {
            appState.editingSpeakerId = editBtn.dataset.speakerId;
            const speakerToEdit = speakers.find(s => s.id === appState.editingSpeakerId);
            if (!speakerToEdit) return;
            
            currentEditingVoiceName = speakerToEdit.voiceName;
            speakerModalEl.querySelector('.modal-title').textContent = 'Edit Speaker Voice';
            speakerModalEl.querySelector('#speaker-name-input').value = speakerToEdit.name;

            speakerModal.show();
            return;
        }

        if (e.target.classList.contains('btn-close')) {
            const speakerCard = e.target.closest('.speaker-card');
            if (speakerCard) {
                const speakerIdToRemove = speakerCard.dataset.speakerId;

                // Filter out the removed speaker
                speakers = speakers.filter(s => s.id !== speakerIdToRemove);

                // Re-index and rename speakers with default names
                speakers.forEach((speaker, index) => {
                    // Check if the speaker has a default generated name
                    if (speaker.name.startsWith('Speaker ') && !isNaN(parseInt(speaker.name.split(' ')[1]))) {
                        speaker.id = `speaker_${index + 1}`; // Update ID
                        speaker.name = `Speaker ${index + 1}`; // Update name
                    }
                });

                renderSpeakers();
                validateStartProcessing();
            }
        }
    });

    startProcessingBtn.addEventListener('click', async () => {
        startThinkingAnimation();

        const formData = new FormData();
        if (videoInput.files[0]) {
            formData.append('video', videoInput.files[0]);
        }
        formData.append('original_language', originalLanguage.value);
        formData.append('translate_language', translationLanguage.value);
        formData.append('prompt_enhancements', geminiInstructions.value);
        formData.append('adjust_speed', adjustSpeedToggle.checked);
        formData.append('use_pro_model', geminiModelToggle.checked);
        const speakersToPost = speakers.map((s, index) => ({
            id: `speaker_${(index + 1).toString()}`,
            name: s.name,
            voice: s.voice,
            gender: s.gender
        }));
        formData.append('speakers', JSON.stringify(speakersToPost));

        try {
            const result = await processVideo(formData);
            console.log('Received result from backend:', JSON.stringify(result, null, 2)); // DEBUG
            currentVideoData = result;
            // Enrich utterance.speaker with gender information from the frontend speakers array
            currentVideoData.utterances.forEach(utterance => {
                const matchingSpeaker = speakers.find(s => s.voice === utterance.speaker.voice);
                if (matchingSpeaker) {
                    utterance.speaker.gender = matchingSpeaker.gender;
                }
                // Store the initial translated times for future reverts.
                utterance.initial_translated_start_time = utterance.translated_start_time;
                utterance.initial_translated_end_time = utterance.translated_end_time;
            });

            mainContent.style.display = 'none';
            resultsView.style.display = 'block';
            const videoPlayerContainer = document.getElementById('video-player-container');
            videoPlayerContainer.classList.add('floating-video-player');
            makeDraggable(videoPlayerContainer);

            const closeFloatingVideoBtn = document.getElementById('close-floating-video-btn');
            closeFloatingVideoBtn.addEventListener('click', () => {
                videoPlayerContainer.classList.remove('floating-video-player');
                videoPlayerContainer.style.cssText = ''; // Reset inline styles
            });
            // timelineControlsContainer.style.display = 'block';

            if (videoInput.files[0]) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    resultsVideoPreview.src = e.target.result;
                    resultsVideoPreview.addEventListener('loadedmetadata', () => {
                        videoDuration = resultsVideoPreview.duration;
                        renderTimeline(currentVideoData, videoDuration, speakers);
                        // Render utterances only AFTER video duration is known
                        renderUtterances(currentVideoData, speakers, videoDuration);
                        checkZeroDurationUtterances(currentVideoData.utterances);
                    });
                };
                reader.readAsDataURL(videoInput.files[0]);
            } else {
                const lastUtterance = result.utterances[result.utterances.length - 1];
                videoDuration = lastUtterance.original_end_time;
                renderTimeline(currentVideoData, videoDuration, speakers);
                renderUtterances(currentVideoData, speakers, videoDuration);
                checkZeroDurationUtterances(currentVideoData.utterances);
            }

            const originalLanguageName = originalLanguage.options[originalLanguage.selectedIndex].text;
            const translationLanguageName = translationLanguage.options[translationLanguage.selectedIndex].text;

            videoSettingsContent.innerHTML = `
                <p><strong>Original Language:</strong> ${originalLanguageName}</p>
                <p><strong>Translation Language:</strong> ${translationLanguageName}</p>
                <h6>Speakers:</h6>
                <ul>
                    ${speakers.map(s => `<li><strong>${s.name}:</strong> ${s.voice}</li>`).join('')}
                </ul>
            `;

        } catch (error) {
            console.error('Error during processing:', error);
            showToast('An error occurred during processing. Please try again.', 'error');
        } finally {
            stopThinkingAnimation();
        }
    });

    generateVideoBtn.addEventListener('click', async () => {
        startThinkingAnimation();

        try {
            const result = await generateVideo(currentVideoData);
            console.log("VIDEO URL: Got the following from the backend:", result.video_url);
            console.log("VOCALS URL: Got the following from the backend:", result.vocals_url);
            console.log("VOCALS + MUSIC URL: Got the following from the backend:", result.vocals_url);

            thinkingPopup.style.display = 'none';
            arielLogo.classList.remove('ariel-logo-animated');
            // Stop animations (dots, phrases) - similar to startProcessingBtn

            resultsView.style.display = 'none'; // Collapse Timeline and Utterances

            // Display generated video view
            generatedVideoView.style.display = 'block';
            generatedVideoPreview.src = result.video_url;

            // Set up download button
            downloadVideoButton.href = result.video_url;
            downloadVideoButton.download = `generated_video_${currentVideoData.video_id}`;

            // Set up audio download buttons
            downloadVocalsButton.href = result.vocals_url;
            downloadVocalsButton.download = `vocals_only_${currentVideoData.video_id}.wav`;
            downloadVocalsMusicButton.href = result.merged_audio_url;
            downloadVocalsMusicButton.download = `vocals_and_music_${currentVideoData.video_id}.wav`;

        } catch (error) {
            console.error('Error generating video:', error);
            showToast('An error occurred while generating the video. Please try again.', 'error');
        } finally {
            stopThinkingAnimation();
        }
    });

function makeDraggable(element) {
    let isDragging = false;
    let offsetX, offsetY;
    let currentX, currentY;
    let animationFrameId;

    function onMouseMove(e) {
        if (isDragging) {
            e.preventDefault();
            currentX = e.clientX;
            currentY = e.clientY;
            if (!animationFrameId) {
                animationFrameId = requestAnimationFrame(updatePosition);
            }
        }
    }

    function updatePosition() {
        animationFrameId = null;
        if (!isDragging) return;

        let newX = currentX - offsetX;
        let newY = currentY - offsetY;

        const viewportWidth = document.documentElement.clientWidth;
        const viewportHeight = document.documentElement.clientHeight;
        const elementWidth = element.offsetWidth;
        const elementHeight = element.offsetHeight;

        newX = Math.max(0, Math.min(newX, viewportWidth - elementWidth));
        newY = Math.max(0, Math.min(newY, viewportHeight - elementHeight));

        element.style.left = `${newX}px`;
        element.style.top = `${newY}px`;
    }

    function onMouseUp() {
        if (isDragging) {
            isDragging = false;
            element.style.cursor = 'move';
            document.body.style.userSelect = '';
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }
        }
    }

    element.addEventListener('mousedown', (e) => {
        if (e.target === element || e.target.classList.contains('results-video')) {
            isDragging = true;
            offsetX = e.clientX - element.getBoundingClientRect().left;
            offsetY = e.clientY - element.getBoundingClientRect().top;
            element.style.cursor = 'grabbing';
            document.body.style.userSelect = 'none';

            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        }
    });
}

    goBackToEditingButton.addEventListener('click', () => {
        generatedVideoView.style.display = 'none';
        resultsView.style.display = 'block'; // Show Timeline and Utterances again
    });

    startOverButton.addEventListener('click', () => {
        location.reload();
    });

    confirmCloseBtn.addEventListener('click', () => {
        document.getElementById('utterance-editor').style.display = 'none';
        bootstrap.Modal.getInstance(document.getElementById('confirmation-modal')).hide();
    });

    // --- Reset Button Logic ---
    function updateResetButtonVisibility() {
        if (!currentVideoData) return;

        const hasChanges = currentVideoData.utterances.some(u =>
            u.translated_start_time !== u.initial_translated_start_time ||
            u.translated_end_time !== u.initial_translated_end_time
        );

        resetTimelineBtn.style.display = hasChanges ? 'inline-block' : 'none';
    }

    document.addEventListener('timeline-changed', updateResetButtonVisibility);

    resetTimelineBtn.addEventListener('click', () => {
        if (!currentVideoData) return;

        currentVideoData.utterances.forEach(utterance => {
            utterance.translated_start_time = utterance.initial_translated_start_time;
            utterance.translated_end_time = utterance.initial_translated_end_time;
        });

        renderTimeline(currentVideoData, videoDuration, speakers);
        updateResetButtonVisibility(); // This will hide the button
    });

    function renderVideoSettingsEditor() {
        const originalContent = videoSettingsContent.innerHTML;

        fetch('static/languages.json')
            .then(response => response.json())
            .then(languages => {
                const gaLanguages = languages.filter(lang => lang.readiness === 'GA');
                const previewLanguages = languages.filter(lang => lang.readiness === 'Preview');

                const renderLanguageOptions = (selectedLanguage) => {
                    return `
                        <optgroup label="GA">
                            ${gaLanguages.map(lang => `<option value="${lang.code}" ${lang.code === selectedLanguage ? 'selected' : ''}>${lang.name}</option>`).join('')}
                        </optgroup>
                        <optgroup label="Preview">
                            ${previewLanguages.map(lang => `<option value="${lang.code}" ${lang.code === selectedLanguage ? 'selected' : ''}>${lang.name}</option>`).join('')}
                        </optgroup>
                    `;
                };

                videoSettingsContent.innerHTML = `
                    <div class="mb-3">
                        <label for="edit-original-language" class="form-label">Original Language</label>
                        <select id="edit-original-language" class="form-select">
                            ${renderLanguageOptions(currentVideoData.original_language)}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="edit-target-language" class="form-label">Translation Language</label>
                        <select id="edit-target-language" class="form-select">
                            ${renderLanguageOptions(currentVideoData.translate_language)}
                        </select>
                    </div>
                    <h6>Speakers:</h6>
                    <div id="edit-speaker-list">
                        ${speakers.map(s => `
                            <div class="d-flex align-items-center mb-2">
                                <span class="me-2">${s.name}:</span>
                                <i class="ms-2 bi ${s.gender === 'Male' ? 'bi-gender-male' : 'bi-gender-female'} text-dark"></i>
                                <button class="btn btn-outline-secondary edit-speaker-voice-btn" data-speaker-id="${s.id}" data-voice-id="${s.voice}">${s.voiceName}</button>
                            </div>
                        `).join('')}
                    </div>
                    <div class="mt-3">
                        <button id="cancel-edit-settings" class="btn btn-secondary">Cancel</button>
                        <button id="submit-edit-settings" class="btn btn-primary">Submit</button>
                    </div>
                `;

                document.getElementById('cancel-edit-settings').addEventListener('click', () => {
                    videoSettingsContent.innerHTML = originalContent;
                    appState.isEditingVideoSettings = false;
                });

                document.querySelectorAll('.edit-speaker-voice-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        const speakerId = e.target.dataset.speakerId;
                        appState.editingSpeakerId = speakerId;
                        const speakerToEdit = speakers.find(s => s.id === speakerId); // Find the speaker to edit
                        if (!speakerToEdit) return;
                        
                        currentEditingVoiceName = speakerToEdit.voiceName;
                        const speakerModalEl = document.getElementById('speaker-modal');
                        speakerModalEl.querySelector('.modal-title').textContent = 'Change Speaker Voice'; // Change modal title
                        speakerModalEl.querySelector('#speaker-name-input').value = speakerToEdit.name; // Populate name input

                        speakerModal.show();
                    });
                });

                document.getElementById('submit-edit-settings').addEventListener('click', async () => {
                    const newOriginalLanguage = document.getElementById('edit-original-language').value;
                    const newTranslateLanguage = document.getElementById('edit-target-language').value;
                    const originalLangChanged = newOriginalLanguage !== currentVideoData.original_language;
                    const translateLangChanged = newTranslateLanguage !== currentVideoData.translate_language;
                    const speakersChanged = JSON.stringify(speakers.map(s => ({ speaker_id: s.id, voice: s.voice }))) !== JSON.stringify(currentVideoData.speakers);

                    if (!originalLangChanged && !translateLangChanged && !speakersChanged) {
                        videoSettingsContent.innerHTML = originalContent;
                        return;
                    }

                    thinkingPopup.style.display = 'flex';

                    try {
                        if (originalLangChanged) {
                            console.log('Re-processing entire video...');
                            const formData = new FormData();
                            formData.append('video', videoInput.files[0]);
                            formData.append('original_language', newOriginalLanguage);
                            formData.append('translate_language', newTranslateLanguage);
                            formData.append('prompt_enhancements', geminiInstructions.value);
                            formData.append('adjust_speed', adjustSpeedToggle.checked);
                            const speakersToPost = speakers.map((s, index) => ({
                                id: `speaker_${(index + 1).toString()}`,
                                name: s.name,
                                voice: s.voice,
                                gender: s.gender
                            }));
                            formData.append('speakers', JSON.stringify(speakersToPost));

                            const result = await processVideo(formData);
                            currentVideoData = result;
                            currentVideoData.utterances.forEach(utterance => {
                                const matchingSpeaker = speakers.find(s => s.voice === utterance.speaker.voice);
                                if (matchingSpeaker) {
                                    utterance.speaker.gender = matchingSpeaker.gender;
                                }
                            });
                            renderTimeline(currentVideoData, videoDuration, speakers);
                            renderUtterances(currentVideoData, speakers, videoDuration);

                        } else if (translateLangChanged) {
                            console.log('Batch regenerating translations...');
                            currentVideoData.translate_language = newTranslateLanguage;
                            const translationPromises = currentVideoData.utterances.map((utterance, index) => {
                                return runRegenerateTranslation(currentVideoData, utterance, index, utterance.instructions);
                            });
                            await Promise.all(translationPromises);
                            renderTimeline(currentVideoData, videoDuration, speakers);
                            renderUtterances(currentVideoData, speakers, videoDuration);

                        } else if (speakersChanged) {
                            console.log('Batch regenerating dubbings for speaker changes...');
                            const changedSpeakers = speakers.filter(s =>
                                !currentVideoData.speakers.find(cs => cs.speaker_id === s.id && cs.voice === s.voice)
                            );
                            const changedSpeakerIds = changedSpeakers.map(cs => cs.id);

                            const dubbingPromises = currentVideoData.utterances
                                .filter(u => changedSpeakerIds.includes(u.speaker.speaker_id))
                                .map((utterance, index) => {
                                    const originalIndex = currentVideoData.utterances.findIndex(u_orig => u_orig.id === utterance.id);
                                    return runRegenerateDubbing(currentVideoData, utterance, originalIndex, utterance.instructions);
                                });
                            await Promise.all(dubbingPromises);

                            changedSpeakers.forEach(changedSpeaker => {
                                currentVideoData.utterances.forEach(utterance => {
                                    if (utterance.speaker.speaker_id === changedSpeaker.id) {
                                        utterance.speaker.voice = changedSpeaker.voice;
                                    }
                                });
                            });

                            renderTimeline(currentVideoData, videoDuration, speakers);
                            renderUtterances(currentVideoData, speakers, videoDuration);
                        }

                        currentVideoData.speakers = speakers.map(s => ({ speaker_id: s.id, name: s.name, voice: s.voice }));

                        const originalLanguageName = document.getElementById('edit-original-language').selectedOptions[0].text;
                        const translationLanguageName = document.getElementById('edit-target-language').selectedOptions[0].text;
                        videoSettingsContent.innerHTML = `
                            <p><strong>Original Language:</strong> ${originalLanguageName}</p>
                            <p><strong>Translation Language:</strong> ${translationLanguageName}</p>
                            <h6>Speakers:</h6>
                            <ul>
                                ${speakers.map(s => `<li><strong>${s.name}:</strong> ${s.voice}</li>`).join('')}
                            </ul>
                        `;

                    } catch (error) {
                        console.error('Error during settings update processing:', error);
                        showToast('An error occurred while updating settings. Please try again.', 'error');
                    } finally {
                        thinkingPopup.style.display = 'none';
                        appState.isEditingVideoSettings = false;
                    }
                });
            });

    goBackToEditingButton.addEventListener('click', () => {
        generatedVideoView.style.display = 'none';
        resultsView.style.display = 'block'; // Show Timeline and Utterances again
    });

    completeVideoButton.addEventListener('click', async () => {
        startThinkingAnimation();
        try {
            const result = await completeVideo(currentVideoData);
            completedVideoVideo.src = result.video_url;
            completedVideoModal.show();
        } catch (error) {
            console.error('Error completing video:', error);
            showToast('An error occurred while completing the video. Please try again.', 'error');
        } finally {
            stopThinkingAnimation();
        }
    });
    }
});

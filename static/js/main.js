import { fetchLanguages, fetchVoices, processVideo, generateVideo } from './api.js';
import { renderTimeline } from './timeline.js';
import { renderUtterances } from './utterance.js';
import { renderVoiceList, addVoice, handleSpeakerModalClose } from './modals.js';

document.addEventListener('DOMContentLoaded', () => {
    // Instantiate templates
    const templates = [
        'results-view-template',
        'speaker-modal-template',
        'edit-speaker-voice-modal-template',
        'confirmation-modal-template',
        'thinking-popup-template'
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
    const addVoiceBtn = document.getElementById('add-voice-btn');

    // Results View
    const mainContent = document.querySelector('.main-content');
    const resultsView = document.getElementById('results-view');
    const videoSettingsContent = document.getElementById('video-settings-content');
    const resultsVideoPreview = document.getElementById('results-video-preview');
    const editVideoSettingsBtn = document.getElementById('edit-video-settings-btn');
    const generateVideoBtn = document.getElementById('generate-video-btn');
    const resetTimelineBtn = document.getElementById('reset-timeline-btn');

    // Modals
    const speakerModal = new bootstrap.Modal(document.getElementById('speaker-modal'));
    const confirmCloseBtn = document.getElementById('confirm-close-btn');
    const editSpeakerVoiceModal = new bootstrap.Modal(document.getElementById('edit-speaker-voice-modal'));
    const editVoiceSearch = document.getElementById('edit-voice-search');
    const editVoiceListModal = document.getElementById('edit-voice-list');
    const saveVoiceBtn = document.getElementById('save-voice-btn');

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

    let voices = [];
    let speakers = [];
    let currentVideoData = null;
    let videoDuration = 0;

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
            const genderIcon = speaker.gender === 'Male' ? 'bi-gender-male' : 'bi-gender-female';
            const speakerCard = document.createElement('div');
            speakerCard.classList.add('speaker-card');
            speakerCard.dataset.speakerId = speaker.id;
            speakerCard.innerHTML = `
                <div>
                    <i class="bi ${genderIcon}"></i>
                    <strong>${speaker.name}:</strong>
                    <span>${speaker.voice}</span>
                </div>
                <div class="d-flex">
                    <button class="btn btn-sm btn-outline-secondary edit-speaker-btn me-2" data-speaker-id="${speaker.id}"><i class="bi bi-pencil"></i></button>
                    <button class="btn-close"></button>
                </div>
            `;
            speakerList.appendChild(speakerCard);
        });
    }
    let editingSpeakerId = null;

    // --- Initializations ---
    fetchLanguages(originalLanguage, translationLanguage).catch(error => console.error('Error fetching languages:', error));

    fetchVoices()
        .then(data => {
            voices = data.voices;
            renderVoiceList(voiceListModal, voiceSearch, 'gender-filter', voices);
            renderVoiceList(editVoiceListModal, editVoiceSearch, 'edit-gender-filter', voices);
        })
        .catch(error => console.error('Error fetching voices:', error));

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
    editVideoSettingsBtn.addEventListener('click', () => renderVideoSettingsEditor());
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
            displayVideo(file);
        }
        validateStartProcessing();
    });

    originalLanguage.addEventListener('change', validateStartProcessing);
    translationLanguage.addEventListener('change', validateStartProcessing);

    addSpeakerBtn.addEventListener('click', () => speakerModal.show());
    document.getElementById('speaker-modal').addEventListener('hidden.bs.modal', () => {
        // Reset modal to its default "add" state when closed
        editingSpeakerId = null;
        const speakerModalEl = document.getElementById('speaker-modal');
        speakerModalEl.querySelector('.modal-title').textContent = 'Select Speaker Voice';
        speakerModalEl.querySelector('#add-voice-btn').textContent = 'Add Voice';
        handleSpeakerModalClose();
    });

    voiceSearch.addEventListener('input', () => renderVoiceList(voiceListModal, voiceSearch, 'gender-filter', voices));
    document.querySelectorAll('input[name="gender-filter"]').forEach(radio => {
        radio.addEventListener('change', () => renderVoiceList(voiceListModal, voiceSearch, 'gender-filter', voices));
    });

    editVoiceSearch.addEventListener('input', () => renderVoiceList(editVoiceListModal, editVoiceSearch, 'edit-gender-filter', voices));
    document.querySelectorAll('input[name="edit-gender-filter"]').forEach(radio => {
        radio.addEventListener('change', () => renderVoiceList(editVoiceListModal, editVoiceSearch, 'edit-gender-filter', voices));
    });

    addVoiceBtn.addEventListener('click', () => addVoice(voices, speakers, renderSpeakers, validateStartProcessing, editingSpeakerId));

    speakerList.addEventListener('click', (e) => {
        const editBtn = e.target.closest('.edit-speaker-btn');
        if (editBtn) {
            editingSpeakerId = editBtn.dataset.speakerId;
            const speakerToEdit = speakers.find(s => s.id === editingSpeakerId);
            if (!speakerToEdit) return;

            const speakerModalEl = document.getElementById('speaker-modal');
            speakerModalEl.querySelector('.modal-title').textContent = 'Edit Speaker Voice';
            speakerModalEl.querySelector('#add-voice-btn').textContent = 'Save Changes';
            speakerModalEl.querySelector('#speaker-name-input').value = speakerToEdit.name;
            
            speakerModal.show();
            return;
        }

        if (e.target.classList.contains('btn-close')) {
            const speakerCard = e.target.closest('.speaker-card');
            if (speakerCard) {
                const speakerId = speakerCard.dataset.speakerId;
                speakers = speakers.filter(s => s.id !== speakerId);
                renderSpeakers();
                validateStartProcessing();
            }
        }
    });

    startProcessingBtn.addEventListener('click', async () => {
        thinkingPopup.style.display = 'flex';
        arielLogo.classList.add('ariel-logo-animated');

        // --- Start Animations ---
        thinkingWord.textContent = 'Thinking'; // Set initial text
        let dotCount = 0;
        dotAnimationInterval = setInterval(() => {
            dotCount = (dotCount + 1) % 4;
            animatedDots.textContent = '.'.repeat(dotCount);
        }, 500);

        phraseChangeInterval = setInterval(() => {
            let currentPhrase = thinkingWord.textContent;
            let nextPhrase = currentPhrase;
            // Simple loop to ensure we don't pick the same phrase twice
            while (nextPhrase === currentPhrase) {
                const randomIndex = Math.floor(Math.random() * thinkingPhrases.length);
                nextPhrase = thinkingPhrases[randomIndex];
            }
            thinkingWord.textContent = nextPhrase;
        }, 10000); // 10 seconds

        const formData = new FormData();
        if (videoInput.files[0]) {
            formData.append('video', videoInput.files[0]);
        }
        formData.append('original_language', originalLanguage.value);
        formData.append('translate_language', translationLanguage.value);
        formData.append('prompt_enhancements', geminiInstructions.value);
        formData.append('adjust_speed', adjustSpeedToggle.checked);
        const speakersToPost = speakers.map((s, index) => ({
            id: `speaker_${(index + 1).toString()}`,
            name: s.name,
            voice: s.voice
        }));
        formData.append('speakers', JSON.stringify(speakersToPost));

        try {
            const result = await processVideo(formData);
            console.log('Received result from backend:', JSON.stringify(result, null, 2)); // DEBUG
            currentVideoData = result;
            currentVideoData.utterances.forEach(utterance => {
                // Store the initial translated times for future reverts.
                utterance.initial_translated_start_time = utterance.translated_start_time;
                utterance.initial_translated_end_time = utterance.translated_end_time;
            });

            mainContent.style.display = 'none';
            resultsView.style.display = 'block';
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
                    });
                };
                reader.readAsDataURL(videoInput.files[0]);
            } else {
                const lastUtterance = result.utterances[result.utterances.length - 1];
                videoDuration = lastUtterance.original_end_time;
                renderTimeline(currentVideoData, videoDuration, speakers);
                renderUtterances(currentVideoData, speakers, videoDuration);
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
            // Handle error here (e.g., show an error message)
        } finally {
            thinkingPopup.style.display = 'none';
            arielLogo.classList.remove('ariel-logo-animated');
            clearInterval(dotAnimationInterval);
            clearInterval(phraseChangeInterval);
            animatedDots.textContent = '';
        }
    });

    generateVideoBtn.addEventListener('click', () => {
        generateVideo(currentVideoData)
            .then(result => {
                console.log("Got the following from the backend:");
                console.log(result.video_url);
                window.location.href = result.video_url;
            })
            .catch(error => {
                console.error('Error generating video:', error);
            });
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
                                <button class="btn btn-outline-secondary edit-speaker-voice-btn" data-speaker-id="${s.id}">${s.voice}</button>
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
                });

                document.getElementById('submit-edit-settings').addEventListener('click', () => {
                    // This part is simplified as full speaker editing is complex here
                    // It only submits language changes for now.
                    currentVideoData.original_language = document.getElementById('edit-original-language').value;
                    currentVideoData.translate_language = document.getElementById('edit-target-language').value;

                    // NOTE: The original logic for updating speakers here was complex and tied to other modals.
                    // This simplified version focuses on updating the language and then re-rendering.

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
                });
            });
    }
});

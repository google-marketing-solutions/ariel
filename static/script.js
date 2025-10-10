document.addEventListener('DOMContentLoaded', () => {
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

    geminiModelToggle.addEventListener('change', () => {
      if (geminiModelToggle.checked) {
        geminiModelLabel.textContent = 'Pro';
      } else {
        geminiModelLabel.textContent = 'Flash';
      }
    });

    // Speakers
    const addSpeakerBtn = document.getElementById('add-speaker-btn');
    const speakerList = document.getElementById('speaker-list');
    const speakerModal = new bootstrap.Modal(document.getElementById('speaker-modal'));
    const voiceSearch = document.getElementById('voice-search');
    const voiceListModal = document.getElementById('voice-list');
    const addVoiceBtn = document.getElementById('add-voice-btn');
    const speakerNameInput = document.getElementById('speaker-name-input');
    const audioPlayer = new Audio();
    let currentlyPlayingButton = null;

    audioPlayer.addEventListener('ended', () => {
        if (currentlyPlayingButton) {
            currentlyPlayingButton.innerHTML = '<i class="bi bi-play-fill"></i>';
            currentlyPlayingButton = null;
        }
    });

    // Results View
    const mainContent = document.querySelector('.main-content');
    const resultsView = document.getElementById('results-view');
    const videoSettingsContent = document.getElementById('video-settings-content');
    const resultsVideoPreview = document.getElementById('results-video-preview');
    const utterancesList = document.getElementById('utterances-list');
    const utteranceEditor = document.getElementById('utterance-editor');
    const utteranceEditorContent = document.getElementById('utterance-editor-content');
    const editVideoSettingsBtn = document.getElementById('edit-video-settings-btn');

    // Modals
    const confirmationModal = new bootstrap.Modal(document.getElementById('confirmation-modal'));
    const confirmCloseBtn = document.getElementById('confirm-close-btn');

    const editSpeakerVoiceModal = new bootstrap.Modal(document.getElementById('edit-speaker-voice-modal'));
    const editVoiceSearch = document.getElementById('edit-voice-search');
    const editVoiceListModal = document.getElementById('edit-voice-list');
    const saveVoiceBtn = document.getElementById('save-voice-btn');
    let speakerToEdit = null;

    let voices = [];
    let speakers = [];
    let currentVideoData = null;
    let videoDuration = 0;
    let rowHeight = 0;

    // --- Validation ---
    function validateStartProcessing() {
        const videoSelected = videoInput.files.length > 0;
        const speakersSelected = speakers.length > 0;
        const originalLangSelected = originalLanguage.value !== '';
        const translationLangSelected = translationLanguage.value !== '';

        if (videoSelected && speakersSelected && originalLangSelected && translationLangSelected) {
            startProcessingBtn.disabled = false;
        } else {
            startProcessingBtn.disabled = true;
        }
    }

    // --- Video Handling ---
    selectVideoComputerBtn.addEventListener('click', () => videoInput.click());
    videoInput.addEventListener('change', () => {
        handleVideoSelect(event);
        validateStartProcessing();
    });
    videoDropZone.addEventListener('dragover', (e) => e.preventDefault());
    videoDropZone.addEventListener('drop', (e) => {
        handleVideoDrop(event);
        validateStartProcessing();
    });

    function handleVideoSelect(event) {
        const file = event.target.files[0];
        if (file) {
            displayVideo(file);
        }
    }

    function handleVideoDrop(event) {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file && file.type.startsWith('video/')) {
            displayVideo(file);
        }
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

    // --- Language Dropdowns ---
    originalLanguage.addEventListener('change', validateStartProcessing);
    translationLanguage.addEventListener('change', validateStartProcessing);

    fetch('static/languages.json')
        .then(response => response.json())
        .then(data => {
            const defaultOption = new Option('Please select...', '', true, true);
            defaultOption.disabled = true;
            originalLanguage.add(defaultOption.cloneNode(true));
            translationLanguage.add(defaultOption.cloneNode(true));

            const gaLanguages = data.filter(lang => lang.readiness === 'GA');
            const previewLanguages = data.filter(lang => lang.readiness === 'Preview');

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

    // --- Speaker Management ---
    addSpeakerBtn.addEventListener('click', () => speakerModal.show());

    fetch('static/voices.json')
        .then(response => response.json())
        .then(data => {
            voices = data.voices; // Correctly access the array
            renderVoices();
            renderEditVoiceList();
        });

    voiceSearch.addEventListener('input', renderVoices);
    document.querySelectorAll('input[name="gender-filter"]').forEach(radio => {
        radio.addEventListener('change', renderVoices);
    });

    editVoiceSearch.addEventListener('input', renderEditVoiceList);
    document.querySelectorAll('input[name="edit-gender-filter"]').forEach(radio => {
        radio.addEventListener('change', renderEditVoiceList);
    });

    function renderVoices() {
        const searchTerm = voiceSearch.value.toLowerCase();
        const genderFilter = document.querySelector('input[name="gender-filter"]:checked').value;

        const filteredVoices = voices.filter(voice => {
            const nameMatch = voice.name.toLowerCase().includes(searchTerm);
            const genderMatch = genderFilter === 'all' || voice.gender === genderFilter;
            return nameMatch && genderMatch;
        });

        voiceListModal.innerHTML = '';

        filteredVoices.forEach(voice => {
            const item = document.createElement('div');
            item.classList.add('list-group-item', 'list-group-item-action', 'd-flex', 'justify-content-between', 'align-items-center');
            
            const voiceName = document.createElement('span');
            voiceName.textContent = `${voice.name} (${voice.gender})`;
            item.appendChild(voiceName);

            if (voice.url) {
                const playButton = document.createElement('button');
                playButton.classList.add('btn', 'btn-sm', 'btn-outline-secondary');
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
                const currentActive = voiceListModal.querySelector('.active');
                if (currentActive) {
                    currentActive.classList.remove('active');
                }
                item.classList.add('active');
            });
            voiceListModal.appendChild(item);
        });
    }

    function renderEditVoiceList() {
        const searchTerm = editVoiceSearch.value.toLowerCase();
        const genderFilter = document.querySelector('input[name="edit-gender-filter"]:checked').value;

        const filteredVoices = voices.filter(voice => {
            const nameMatch = voice.name.toLowerCase().includes(searchTerm);
            const genderMatch = genderFilter === 'all' || voice.gender === genderFilter;
            return nameMatch && genderMatch;
        });

        editVoiceListModal.innerHTML = '';

        filteredVoices.forEach(voice => {
            const item = document.createElement('div');
            item.classList.add('list-group-item', 'list-group-item-action', 'd-flex', 'justify-content-between', 'align-items-center');
            
            const voiceName = document.createElement('span');
            voiceName.textContent = `${voice.name} (${voice.gender})`;
            item.appendChild(voiceName);

            if (voice.url) {
                const playButton = document.createElement('button');
                playButton.classList.add('btn', 'btn-sm', 'btn-outline-secondary');
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
                const currentActive = editVoiceListModal.querySelector('.active');
                if (currentActive) {
                    currentActive.classList.remove('active');
                }
                item.classList.add('active');
            });
            editVoiceListModal.appendChild(item);
        });
    }

    addVoiceBtn.addEventListener('click', () => {
        const selectedVoiceEl = voiceListModal.querySelector('.active');
        if (!selectedVoiceEl) {
            alert('Please select a voice.');
            return;
        }

        const voiceName = selectedVoiceEl.dataset.voiceName;
        const voiceData = voices.find(v => v.name === voiceName);
        const customName = speakerNameInput.value.trim();

        const speaker = {
            id: `speaker_${speakers.length + 1}`,
            name: customName || `Speaker ${speakers.length + 1}`,
            voice: voiceData.name,
            gender: voiceData.gender
        };

        speakers.push(speaker);
        renderSpeakers();
        speakerNameInput.value = ''; // Clear the input
        speakerModal.hide();
        validateStartProcessing();
    });

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
                <button class="btn-close"></button>
            `;
            speakerList.appendChild(speakerCard);
        });
    }

    speakerList.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-close')) {
            const speakerId = e.target.closest('.speaker-card').dataset.speakerId;
            speakers = speakers.filter(s => s.id !== parseInt(speakerId));
            renderSpeakers();
            validateStartProcessing();
        }
    });

    const thinkingPopup = document.getElementById('thinking-popup');

    // --- Start Processing ---
    startProcessingBtn.addEventListener('click', async () => {
        thinkingPopup.style.display = 'flex';

        const formData = new FormData();

        // 1. Video file
        if (videoInput.files[0]) {
            formData.append('video', videoInput.files[0]);
        }

        // 2. Languages
        formData.append('original_language', originalLanguage.value);
        formData.append('translate_language', translationLanguage.value);

        // 3. Prompt Enhancements
        formData.append('prompt_enhancements', geminiInstructions.value);

        // 4. Speakers
        const speakersToPost = speakers.map(s => ({ id: s.id, voice: s.voice }));
        formData.append('speakers', JSON.stringify(speakersToPost));

        try {
            // Replace '/process' with your actual backend endpoint
            const response = await fetch('/process', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            console.log('Received result from backend:', JSON.stringify(result, null, 2)); // DEBUG
            currentVideoData = result; // Store the video data
            
            // Show results view
            mainContent.style.display = 'none';
            resultsView.style.display = 'block';

            // Set video preview
            if (videoInput.files[0]) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    resultsVideoPreview.src = e.target.result;
                    resultsVideoPreview.addEventListener('loadedmetadata', () => {
                        videoDuration = resultsVideoPreview.duration;
                        const timelineContainer = document.getElementById('timeline');
                        const timelineHeight = timelineContainer.clientHeight;
                        const numUtterances = currentVideoData.utterances.length;
                        rowHeight = timelineHeight / (numUtterances + 1);
                        if (rowHeight < 20) {
                            rowHeight = 20;
                        }
                        renderTimeline(currentVideoData, videoDuration);
                    });
                };
                reader.readAsDataURL(videoInput.files[0]);
            } else {
                // If there is no video, use a default duration from the utterances
                const lastUtterance = result.utterances[result.utterances.length - 1];
                videoDuration = lastUtterance.original_end_time;
                const timelineContainer = document.getElementById('timeline');
                const timelineHeight = timelineContainer.clientHeight;
                const numUtterances = result.utterances.length;
                rowHeight = timelineHeight / (numUtterances + 1);
                if (rowHeight < 20) {
                    rowHeight = 20;
                }
                renderTimeline(currentVideoData, videoDuration);
            }

            // Populate video settings
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

            renderUtterances(result.utterances, result.speakers);

        } catch (error) {
            console.error('Error during processing:', error);
            // Handle error here (e.g., show an error message)
        } finally {
            thinkingPopup.style.display = 'none';
        }
    });

    // --- Edit Video Settings ---
    editVideoSettingsBtn.addEventListener('click', () => {
        renderVideoSettingsEditor(currentVideoData);
    });

    function renderVideoSettingsEditor(videoData) {
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
                            ${renderLanguageOptions(videoData.original_language)}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label for="edit-target-language" class="form-label">Translation Language</label>
                        <select id="edit-target-language" class="form-select">
                            ${renderLanguageOptions(videoData.translate_language)}
                        </select>
                    </div>
                    <h6>Speakers:</h6>
                    <div id="edit-speaker-list">
                        ${videoData.speakers.map((speaker, index) => `
                            <div class="d-flex align-items-center mb-2">
                                <span class="me-2">Speaker ${speaker.speaker_number}:</span>
                                <button class="btn btn-outline-secondary edit-speaker-voice-btn" data-speaker-number="${speaker.speaker_number}">${speaker.voice}</button>
                            </div>
                        `).join('')}
                    </div>
                    <div class="mt-3">
                        <button id="cancel-edit-settings" class="btn btn-secondary">Cancel</button>
                        <button id="submit-edit-settings" class="btn btn-primary">Submit</button>
                    </div>
                `;

                // Add event listeners
                document.getElementById('cancel-edit-settings').addEventListener('click', () => {
                    videoSettingsContent.innerHTML = originalContent;
                });

                document.querySelectorAll('.edit-speaker-voice-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        speakerToEdit = parseInt(e.target.dataset.speakerNumber);
                        renderEditVoiceList();
                        editSpeakerVoiceModal.show();
                    });
                });

                document.getElementById('submit-edit-settings').addEventListener('click', () => {
                    const updatedVideoData = {
                        ...videoData,
                        original_language: document.getElementById('edit-original-language').value,
                        translate_language: document.getElementById('edit-target-language').value,
                        speakers: Array.from(document.querySelectorAll('#edit-speaker-list button.edit-speaker-voice-btn')).map(button => ({
                            speaker_number: parseInt(button.dataset.speakerNumber),
                            voice: button.textContent
                        }))
                    };

                    // POST to backend
                    fetch('/process', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify(updatedVideoData)
                    })
                    .then(response => response.json())
                    .then(result => {
                        console.log('Successfully updated video settings:', result);
                        currentVideoData = result;
                        // Restore the original content and update it
                        videoSettingsContent.innerHTML = `
                            <p><strong>Original Language:</strong> ${result.original_language}</p>
                            <p><strong>Translation Language:</strong> ${result.translate_language}</p>
                            <h6>Speakers:</h6>
                            <ul>
                                ${result.speakers.map(s => `<li>Speaker ${s.speaker_number}: ${s.voice}</li>`).join('')}
                            </ul>
                        `;
                        renderTimeline(result, videoDuration);
                    })
                    .catch(error => {
                        console.error('Error updating video settings:', error);
                    });
                });
            });
    }

    saveVoiceBtn.addEventListener('click', () => {
        const selectedVoiceEl = editVoiceListModal.querySelector('.active');
        if (!selectedVoiceEl) {
            alert('Please select a voice.');
            return;
        }

        const voiceName = selectedVoiceEl.dataset.voiceName;
        
        // Update the button text in the editor
        const speakerButton = document.querySelector(`#edit-speaker-list button[data-speaker-number="${speakerToEdit}"]`);
        speakerButton.textContent = voiceName;

        editSpeakerVoiceModal.hide();
    });

    function renderUtterances(utterances, allSpeakers) {
        utterancesList.innerHTML = '';
        utterances.forEach((utterance, index) => {
            const utteranceCard = document.createElement('div');
            utteranceCard.classList.add('utterance-card');
            utteranceCard.innerHTML = `
                    <div>
                        <h6 class="mb-0">U: ${index + 1}</h6>
                        <div class="utterance-content-wrapper">
                            <div class="utterance-card-content mt-2">
                                <p><strong>Original:</strong> ${utterance.original_text.substring(0, 100)}...</p>
                                <p><strong>Translated:</strong> ${utterance.translated_text.substring(0, 100)}...</p>
                                <p><strong>Speaker:</strong> ${utterance.speaker.voice}</p>
                            </div>
                            <div class="utterance-overlay" style="display: none;"></div>
                        </div>
                    </div>
                    <div class="d-flex flex-column">
                        <button class="btn btn-sm btn-outline-secondary remove-utterance-btn mb-2"><i class="bi bi-trash"></i></button>
                        <button class="btn btn-sm btn-outline-secondary mute-utterance-btn mb-2"><i class="bi bi-mic-mute"></i></button>
                        <button class="btn btn-sm btn-outline-secondary edit-utterance-btn"><i class="bi bi-pencil"></i></button>
                    </div>
            `;

            utteranceCard.querySelector('.edit-utterance-btn').addEventListener('click', () => {
                editUtterance(utterance, allSpeakers, utterances, index);
            });

            const removeBtn = utteranceCard.querySelector('.remove-utterance-btn');
            const content = utteranceCard.querySelector('.utterance-card-content');
            const overlay = utteranceCard.querySelector('.utterance-overlay');

            removeBtn.addEventListener('click', () => {
                content.classList.toggle('removed');
                if (content.classList.contains('removed')) {
                    overlay.textContent = 'No audio will be generated';
                    overlay.style.display = 'flex';
                } else {
                    overlay.style.display = 'none';
                }
            });

            const muteBtn = utteranceCard.querySelector('.mute-utterance-btn');
            muteBtn.addEventListener('click', () => {
                content.classList.toggle('muted');
                if (content.classList.contains('muted')) {
                    overlay.textContent = 'Original audio will be used';
                    overlay.style.display = 'flex';
                } else {
                    overlay.style.display = 'none';
                }
            });

            utterancesList.appendChild(utteranceCard);
        });
    }

    function checkOverlap(utterance, allUtterances) {
        const messages = [];
        for (const other of allUtterances) {
            if (utterance.id === other.id) continue;

            // Check for overlap
            if (utterance.translated_start_time < other.translated_end_time && other.translated_start_time < utterance.translated_end_time) {
                messages.push(`Translated time overlaps with another utterance.`);
                break; // No need to check further
            }
        }
        return messages;
    }

    function renderTimeline(videoData, videoDuration) {
        const timelineContainer = document.getElementById('timeline');
        const originalTimeline = document.getElementById('original-utterances-timeline');
        const translatedTimeline = document.getElementById('translated-utterances-timeline');
        const timelineWidth = timelineContainer.offsetWidth;
        const scale = timelineWidth / videoDuration;

        originalTimeline.innerHTML = '';
        translatedTimeline.innerHTML = '';

        originalTimeline.style.height = `${rowHeight}px`;

        // Render original utterances in one row
        videoData.utterances.forEach((utterance, index) => {
            const originalBlock = document.createElement('div');
            originalBlock.className = 'utterance-block original';
            originalBlock.style.left = `${utterance.original_start_time * scale}px`;
            originalBlock.style.width = `${(utterance.original_end_time - utterance.original_start_time) * scale}px`;
            originalBlock.textContent = `U: ${index + 1}`;
            originalTimeline.appendChild(originalBlock);

            // Check for overlaps with subsequent utterances
            for (let i = index + 1; i < videoData.utterances.length; i++) {
                const other = videoData.utterances[i];
                
                const overlap_start = Math.max(utterance.original_start_time, other.original_start_time);
                const overlap_end = Math.min(utterance.original_end_time, other.original_end_time);

                if (overlap_start < overlap_end) {
                    // There is an overlap
                    const overlapBlock = document.createElement('div');
                    overlapBlock.className = 'utterance-block overlap';
                    overlapBlock.style.left = `${overlap_start * scale}px`;
                    overlapBlock.style.width = `${(overlap_end - overlap_start) * scale}px`;
                    originalTimeline.appendChild(overlapBlock);
                }
            }
        });

        // Render translated utterances in separate rows
        videoData.utterances.forEach((utterance, index) => {
            const translatedRow = document.createElement('div');
            translatedRow.className = 'timeline-row';
            translatedRow.style.height = `${rowHeight}px`;

            const translatedBlock = document.createElement('div');
            translatedBlock.className = 'utterance-block';
            translatedBlock.style.left = `${utterance.translated_start_time * scale}px`;
            translatedBlock.style.width = `${(utterance.translated_end_time - utterance.translated_start_time) * scale}px`;
            translatedBlock.textContent = `U: ${index + 1}`;
            translatedBlock.dataset.utteranceId = utterance.id;
            
            translatedBlock.addEventListener('dblclick', () => {
                editUtterance(utterance, videoData.speakers, videoData.utterances, index);
            });

            // Drag and drop
            translatedBlock.addEventListener('mousedown', (e) => {
                let initialX = e.clientX;
                let initialLeft = translatedBlock.offsetLeft;
                const blockWidth = translatedBlock.offsetWidth;

                function handleMouseMove(e) {
                    const dx = e.clientX - initialX;
                    let newLeft = initialLeft + dx;

                    // Constrain movement
                    if (newLeft < 0) {
                        newLeft = 0;
                    }
                    if (newLeft + blockWidth > timelineWidth) {
                        newLeft = timelineWidth - blockWidth;
                    }

                    translatedBlock.style.left = `${newLeft}px`;

                    const newStartTime = newLeft / scale;
                    const utteranceDuration = utterance.translated_end_time - utterance.translated_start_time;
                    const newEndTime = newStartTime + utteranceDuration;

                    // Temporarily update the dragged utterance times
                    const originalStartTime = utterance.translated_start_time;
                    const originalEndTime = utterance.translated_end_time;
                    utterance.translated_start_time = newStartTime;
                    utterance.translated_end_time = newEndTime;

                    // Update editor if open
                    if (utteranceEditor.style.display === 'block') {
                        const editedUtteranceId = utteranceEditor.dataset.utteranceId;
                        const editedUtterance = videoData.utterances.find(u => u.id === editedUtteranceId);

                        if (editedUtterance) {
                            // Update input fields if dragging the same utterance
                            if (editedUtteranceId === utterance.id) {
                                utteranceEditorContent.querySelector('#translated-start-time-input').value = newStartTime.toFixed(2);
                                utteranceEditorContent.querySelector('#translated-end-time-input').value = newEndTime.toFixed(2);
                            }

                            const overlapMessages = checkOverlap(editedUtterance, videoData.utterances);
                            const warningBox = utteranceEditorContent.querySelector('#translated-overlap-warning');
                            if (overlapMessages.length > 0) {
                                warningBox.innerHTML = overlapMessages.join('<br>');
                                warningBox.style.display = 'block';
                            } else {
                                warningBox.style.display = 'none';
                            }
                        }
                    }
                    
                    // Restore the original times
                    utterance.translated_start_time = originalStartTime;
                    utterance.translated_end_time = originalEndTime;
                }

                function handleMouseUp(e) {
                    document.removeEventListener('mousemove', handleMouseMove);
                    document.removeEventListener('mouseup', handleMouseUp);

                    const newLeft = translatedBlock.offsetLeft;
                    const newStartTime = parseFloat((newLeft / scale).toFixed(2));
                    const utteranceDuration = utterance.translated_end_time - utterance.translated_start_time;
                    const newEndTime = parseFloat((newStartTime + utteranceDuration).toFixed(2));

                    // Update the utterance data
                    utterance.translated_start_time = newStartTime;
                    utterance.translated_end_time = newEndTime;

                    // Re-render the timeline
                    renderTimeline(videoData, videoDuration);
                }

                document.addEventListener('mousemove', handleMouseMove);
                document.addEventListener('mouseup', handleMouseUp);
            });

            translatedRow.appendChild(translatedBlock);

            // Check for overlaps with other translated utterances
            for (let i = 0; i < videoData.utterances.length; i++) {
                if (i === index) continue;

                const other = videoData.utterances[i];
                
                const overlap_start = Math.max(utterance.translated_start_time, other.translated_start_time);
                const overlap_end = Math.min(utterance.translated_end_time, other.translated_end_time);

                if (overlap_start < overlap_end) {
                    const overlapBlock = document.createElement('div');
                    overlapBlock.className = 'utterance-block overlap';
                    overlapBlock.style.left = `${overlap_start * scale}px`;
                    overlapBlock.style.width = `${(overlap_end - overlap_start) * scale}px`;
                    translatedRow.appendChild(overlapBlock);
                }
            }
            
            translatedTimeline.appendChild(translatedRow);
        });
    }

    function editUtterance(utterance, allSpeakers, utterances, index) {
        console.log('Editing utterance:', JSON.stringify(utterance, null, 2)); // DEBUG

        const originalDuration = (utterance.original_end_time - utterance.original_start_time).toFixed(2);
        const translatedDuration = (utterance.translated_end_time - utterance.translated_start_time).toFixed(2);

        utteranceEditor.style.display = 'block';
        utteranceEditor.dataset.utteranceId = utterance.id;
        utteranceEditorContent.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-1">
                <label class="form-label mb-0">Original Text <i class="bi bi-volume-up-fill text-to-speech-icon me-2 fs-5" data-text-type="original"></i></label>
                <span class="badge bg-secondary">${originalDuration}s</span>
            </div>
            <textarea id="original-text-area" class="form-control" rows="3" readonly>${utterance.original_text}</textarea>

            <div class="d-flex justify-content-between align-items-center mt-3 mb-1">
                <label class="form-label mb-0">Translated Text <i class="bi bi-volume-up-fill text-to-speech-icon me-2 fs-5" data-text-type="translated"></i></label>
                <span class="badge bg-secondary">${translatedDuration}s</span>
            </div>
            <textarea id="translated-text-area" class="form-control" rows="3">${utterance.translated_text}</textarea>

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
                    ${allSpeakers.map(s => `<option value="${s.voice}" ${s.voice === utterance.speaker.voice ? 'selected' : ''}>${s.voice}</option>`).join('')}
                </select>
            </div>
            <button id="regenerate-translation-btn" class="btn btn-primary">Regenerate Translation</button>
            <button id="regenerate-dubbing-btn" class="btn btn-success">Regenerate Dubbing</button>
        `;

        // Store initial values
        const initialTranslatedText = utterance.translated_text;
        const initialInstructions = utterance.instructions || '';
        const initialSpeaker = utterance.speaker.voice;
        const initialGeminiPrompt = ''; // Assuming it's always empty initially

        const closeButton = utteranceEditor.querySelector('#close-utterance-editor');
        closeButton.addEventListener('click', () => {
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
            } else {
                utteranceEditor.style.display = 'none';
            }
        });

        // Add event listeners for the text-to-speech icons
        const ttsIcons = utteranceEditorContent.querySelectorAll('.text-to-speech-icon');
        ttsIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                const textType = e.target.dataset.textType;
                let textToSpeak = '';
                if (textType === 'original') {
                    textToSpeak = utterance.original_text;
                } else if (textType === 'translated') {
                    textToSpeak = utteranceEditorContent.querySelector('#translated-text-area').value;
                }
                console.log(`Playing ${textType} text: ${textToSpeak}`);
                // Here you would make a call to the backend to get the audio
            });
        });


        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(utteranceEditorContent.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });

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

    confirmCloseBtn.addEventListener('click', () => {
        utteranceEditor.style.display = 'none';
        confirmationModal.hide();
    });
});

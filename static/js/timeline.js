import { checkOverlap } from './utils.js';
import { editUtterance } from './utterance.js';

export function renderTimeline(videoData, videoDuration, speakers) {
    const timelineContainer = document.getElementById('timeline');
    const timelineMarkersContainer = document.getElementById('timeline-markers');
    const originalSpeakerLabelsContainer = document.getElementById('original-speaker-labels');
    const originalUtterancesTracksContainer = document.getElementById('original-utterances-tracks');
    const translatedSpeakerLabelsContainer = document.getElementById('translated-speaker-labels');
    const translatedUtterancesTracksContainer = document.getElementById('translated-utterances-tracks');

    // Clear previous content
    timelineMarkersContainer.innerHTML = '';
    originalSpeakerLabelsContainer.innerHTML = '';
    originalUtterancesTracksContainer.innerHTML = '';
    translatedSpeakerLabelsContainer.innerHTML = '';
    translatedUtterancesTracksContainer.innerHTML = '';

    // Add section headers
    const originalHeader = document.createElement('h6');
    originalHeader.textContent = 'Original';
    originalHeader.classList.add('timeline-section-header');
    originalSpeakerLabelsContainer.appendChild(originalHeader);

    const translatedHeader = document.createElement('h6');
    translatedHeader.textContent = 'Translated';
    translatedHeader.classList.add('timeline-section-header');
    translatedSpeakerLabelsContainer.appendChild(translatedHeader);

    // Add spacer divs to the tracks columns to align with headers
    const originalSpacer = document.createElement('div');
    originalSpacer.classList.add('timeline-section-header');
    originalSpacer.innerHTML = '&nbsp;'; // Ensure it takes up space
    originalUtterancesTracksContainer.appendChild(originalSpacer);

    const translatedSpacer = document.createElement('div');
    translatedSpacer.classList.add('timeline-section-header');
    translatedSpacer.innerHTML = '&nbsp;'; // Ensure it takes up space
    translatedUtterancesTracksContainer.appendChild(translatedSpacer);

    const SPEAKER_LABEL_COLUMN_WIDTH = 150; // Assuming a fixed width for the speaker label column
    const timelineWidth = timelineContainer.offsetWidth - SPEAKER_LABEL_COLUMN_WIDTH; // Subtract label column width
    const scale = timelineWidth / videoDuration;

    // Add timeline markers
    for (let i = 0; i <= videoDuration; i += 5) {
        const marker = document.createElement('div');
        marker.classList.add('timeline-marker');
        marker.style.left = `${i * scale}px`;
        marker.textContent = `${i}s`;
        timelineMarkersContainer.appendChild(marker);
    }

    // Collect all unique voices present in the utterances from the backend
    const uniqueVoicesInUtterances = new Set();
    videoData.utterances.forEach(u => {
        uniqueVoicesInUtterances.add(u.speaker.voice);
    });

    // Create a map from voice to speaker name using the client-side speakers array
    const voiceToSpeakerNameMap = new Map();
    speakers.forEach(s => {
        voiceToSpeakerNameMap.set(s.voice, s.name);
    });

    // Now, create the list of speaker voices to render tracks for
    // Prioritize voices from utterances, and resolve their names
    const speakerVoicesToRender = Array.from(uniqueVoicesInUtterances);

    // Create speaker rows and labels
    speakerVoicesToRender.forEach(speakerVoice => {
        const speakerName = voiceToSpeakerNameMap.get(speakerVoice) || speakerVoice; // Fallback to voice if name not found

        // Original section
        const originalLabel = document.createElement('div');
        originalLabel.classList.add('speaker-label');
        originalLabel.textContent = speakerName;
        originalSpeakerLabelsContainer.appendChild(originalLabel);

        const originalTrack = document.createElement('div');
        originalTrack.classList.add('speaker-timeline-row');
        originalTrack.id = `original-speaker-track-${speakerVoice.replace(/[^a-zA-Z0-9-_]/g, '')}`; // Sanitize voice for ID
        originalUtterancesTracksContainer.appendChild(originalTrack);

        // Translated section
        const translatedLabel = document.createElement('div');
        translatedLabel.classList.add('speaker-label');
        translatedLabel.textContent = speakerName;
        translatedSpeakerLabelsContainer.appendChild(translatedLabel);

        const translatedTrack = document.createElement('div');
        translatedTrack.classList.add('speaker-timeline-row');
        translatedTrack.id = `translated-speaker-track-${speakerVoice.replace(/[^a-zA-Z0-9-_]/g, '')}`; // Sanitize voice for ID
        translatedUtterancesTracksContainer.appendChild(translatedTrack);
    });

    // Render original utterances
    videoData.utterances.forEach((utterance, index) => {
        const originalTrack = document.getElementById(`original-speaker-track-${utterance.speaker.voice.replace(/[^a-zA-Z0-9-_]/g, '')}`); // Use sanitized voice for ID
        if (originalTrack) {
            const originalBlock = document.createElement('div');
            originalBlock.className = 'utterance-block original';
            originalBlock.style.left = `${utterance.original_start_time * scale}px`;
            originalBlock.style.width = `${(utterance.original_end_time - utterance.original_start_time) * scale}px`;
            originalBlock.textContent = `U: ${index + 1}`;
            originalTrack.appendChild(originalBlock);
        }
    });

    // Render translated utterances
    videoData.utterances.forEach((utterance, index) => {
        const translatedTrack = document.getElementById(`translated-speaker-track-${utterance.speaker.voice.replace(/[^a-zA-Z0-9-_]/g, '')}`); // Use sanitized voice for ID
        if (translatedTrack) {
            const translatedBlock = document.createElement('div');
            translatedBlock.className = 'utterance-block';
            if (utterance.muted) {
                translatedBlock.classList.add('muted');
            }
            if (utterance.removed) {
                translatedBlock.classList.add('removed');
            }
            translatedBlock.style.left = `${utterance.translated_start_time * scale}px`;
            translatedBlock.style.width = `${(utterance.translated_end_time - utterance.translated_start_time) * scale}px`;
            translatedBlock.textContent = `U: ${index + 1}`;
            translatedBlock.dataset.utteranceId = utterance.id;

            // Check for initial overlaps and apply class
            const initialOverlapMessages = checkOverlap(utterance, videoData.utterances);
            if (initialOverlapMessages.length > 0) {
                translatedBlock.classList.add('overlap');
            }

            translatedBlock.addEventListener('dblclick', () => {
                editUtterance(utterance, videoData.speakers, videoData.utterances, index, speakers);
            });

            // Drag and drop functionality
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
                    utterance.translated_start_time = newStartTime;
                    utterance.translated_end_time = newEndTime;

                    // Update editor if open
                    const utteranceEditor = document.getElementById('utterance-editor');
                    if (utteranceEditor.style.display === 'block') {
                        const editedUtteranceId = utteranceEditor.dataset.utteranceId;
                        const editedUtterance = videoData.utterances.find(u => u.id === editedUtteranceId);

                        if (editedUtterance) {
                            // Update input fields if dragging the same utterance
                            if (editedUtteranceId === utterance.id) {
                                document.getElementById('translated-start-time-input').value = newStartTime.toFixed(2);
                                document.getElementById('translated-end-time-input').value = newEndTime.toFixed(2);
                            }

                            const overlapMessages = checkOverlap(editedUtterance, videoData.utterances);
                            const warningBox = document.getElementById('translated-overlap-warning');
                            if (overlapMessages.length > 0) {
                                warningBox.innerHTML = overlapMessages.join('<br>');
                                warningBox.style.display = 'block';
                            } else {
                                warningBox.style.display = 'none';
                            }
                        }
                    }
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
                    renderTimeline(videoData, videoDuration, speakers);
                }

                document.addEventListener('mousemove', handleMouseMove);
                document.addEventListener('mouseup', handleMouseUp);
            });

            translatedTrack.appendChild(translatedBlock);
        }
    });
}

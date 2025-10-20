export function fetchLanguages(originalLanguage, translationLanguage) {
    return fetch('static/languages.json')
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
}

export function fetchVoices() {
    return fetch('static/voices.json').then(response => response.json());
}

export function processVideo(formData) {
    return fetch('/process', {
        method: 'POST',
        body: formData
    }).then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    });
}

export function regenerateTranslation(videoData, utteranceIndex, instructions) {
    return fetch('/regenerate_translation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            video: videoData,
            utterance: utteranceIndex,
            instructions: instructions
        })
    }).then(response => response.json());
}

export function generateVideo(videoData) {
    return fetch('/generate_video', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(videoData)
    }).then(response => response.json());
}

export function updateVideoSettings(updatedVideoData) {
    return fetch('/process', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(updatedVideoData)
    }).then(response => response.json());
}

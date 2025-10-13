self.addEventListener('install', event => {
    console.log('Service worker installed');
});

self.addEventListener('activate', event => {
    console.log('Service worker activated');
});

self.addEventListener('fetch', event => {
    console.log('Service Worker intercepted a fetch request:', event.request.url, 'with method:', event.request.method);
    if (event.request.url.endsWith('/process_video') && event.request.method === 'POST') {
        console.log('Intercepting POST request to /process');
        const mockResponse = {
            "video_id": "12345",
            "original_language": "en-US",
            "translate_language": "es-ES",
            "prompt_enhancements": "Some special instructions",
            "speakers": [
                { "speaker_number": 1, "voice": "en-US-Standard-A" },
                { "speaker_number": 2, "voice": "en-US-Standard-C" }
            ],
            "utterances": [
                {
                    "id": "utt1",
                    "original_text": "Hello, this is the first utterance.",
                    "translated_text": "Hola, esta es la primera elocución.",
                    "instructions": "speak clearly",
                    "speaker": { "speaker_number": 1, "voice": "en-US-Standard-A" },
                    "original_start_time": 0.5,
                    "original_end_time": 2.5,
                    "translated_start_time": 0.5,
                    "translated_end_time": 2.8,
                    "is_dirty": false,
                    "audio_url": "/audio/utt1.mp3"
                },
                {
                    "id": "utt2",
                    "original_text": "And this is the second one, spoken by a different person.",
                    "translated_text": "Y esta es la segunda, pronunciada por una persona diferente.",
                    "instructions": "",
                    "speaker": { "speaker_number": 2, "voice": "en-US-Standard-C" },
                    "original_start_time": 2.0,
                    "original_end_time": 6.0,
                    "translated_start_time": 3.0,
                    "translated_end_time": 6.5,
                    "is_dirty": false,
                    "audio_url": "/audio/utt2.mp3"
                }
            ]
        };

        event.respondWith(
            new Response(JSON.stringify(mockResponse), {
                status: 200,
                statusText: 'OK',
                headers: { 'Content-Type': 'application/json' }
            })
        );
    }
});

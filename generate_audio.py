import base64
import io
import re
import wave
from google.genai import types


def pcm_to_wav_base64(
    pcm_data: bytes,
    sample_rate: int,
    bit_depth: int,
) -> str:
    """Converts raw PCM audio data to a base64 encoded WAV string."""
    with io.BytesIO() as wav_file:
        with wave.open(wav_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(bit_depth // 8)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)
        wav_bytes = wav_file.getvalue()

    base64_wav = base64.b64encode(wav_bytes).decode('utf-8')
    return base64_wav


def _process_audio_part(audio_part) -> str:
    """Processes the audio part, extracts metadata, and converts to base64 WAV."""
    # Parse the mime_type string "audio/L16;codec=pcm;rate=24000"
    mime_type = audio_part.inline_data.mime_type

    match = re.search(r'L(\d+);codec=(?:\w+);rate=(\d+)', mime_type)
    if not match:
        raise ValueError(f'Could not parse mime_type: {mime_type}')
    bit_depth = int(match.group(1))
    sample_rate = int(match.group(2))

    return pcm_to_wav_base64(audio_part.inline_data.data,
                             sample_rate=sample_rate,
                             bit_depth=bit_depth)


def generate_audio(
    client,
    prompt: str,
    voice_name: str,
    model_name: str = 'gemini-2.5-pro-preview-tts',
):
    voice_config = types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name))

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=voice_config),
        ))

    audio_part = response.candidates[0].content.parts[0]
    return _process_audio_part(audio_part)

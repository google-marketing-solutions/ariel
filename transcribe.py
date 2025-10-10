from dataclasses import dataclass
import json
from typing import List, Dict
from pydantic import TypeAdapter
from google.genai import types

VOICE_OPTIONS = {
    'Zephyr': {
        'gender': 'female',
        'tone': 'Bright',
        'pitch': 'Higher'
    },
    'Puck': {
        'gender': 'male',
        'tone': 'Upbeat',
        'pitch': 'Middle'
    },
    'Charon': {
        'gender': 'male',
        'tone': 'Informative',
        'pitch': 'Lower'
    },
    'Kore': {
        'gender': 'female',
        'tone': 'Firm',
        'pitch': 'Middle'
    },
    'Fenrir': {
        'gender': 'female',
        'tone': 'Excitable',
        'pitch': 'Lower middle',
    },
    'Leda': {
        'gender': 'female',
        'tone': 'Youthful',
        'pitch': 'Higher'
    },
    'Orus': {
        'gender': 'male',
        'tone': 'Firm',
        'pitch': 'Lower middle'
    },
    'Aoede': {
        'gender': 'female',
        'tone': 'Breezy',
        'pitch': 'Middle'
    },
    'Callirrhoe': {
        'gender': 'female',
        'tone': 'Easy-going',
        'pitch': 'Middle',
    },
    'Autonoe': {
        'gender': 'female',
        'tone': 'Bright',
        'pitch': 'Middle'
    },
    'Enceladus': {
        'gender': 'male',
        'tone': 'Breathy',
        'pitch': 'Lower'
    },
    'Iapetus': {
        'gender': 'male',
        'tone': 'Clear',
        'pitch': 'Lower middle'
    },
    'Umbriel': {
        'gender': 'male',
        'tone': 'Easy-going',
        'pitch': 'Lower middle',
    },
    'Algieba': {
        'gender': 'male',
        'tone': 'Smooth',
        'pitch': 'Lower'
    },
    'Despina': {
        'gender': 'female',
        'tone': 'Smooth',
        'pitch': 'Middle'
    },
    'Erinome': {
        'gender': 'female',
        'tone': 'Clear',
        'pitch': 'Middle'
    },
    'Algenib': {
        'gender': 'male',
        'tone': 'Gravelly',
        'pitch': 'Lower'
    },
    'Rasalgethi': {
        'gender': 'male',
        'tone': 'Informative',
        'pitch': 'Middle',
    },
    'Laomedeia': {
        'gender': 'female',
        'tone': 'Upbeat',
        'pitch': 'Higher'
    },
    'Achernar': {
        'gender': 'female',
        'tone': 'Soft',
        'pitch': 'Higher'
    },
    'Alnilam': {
        'gender': 'male',
        'tone': 'Firm',
        'pitch': 'Lower middle'
    },
    'Schedar': {
        'gender': 'male',
        'tone': 'Even',
        'pitch': 'Lower middle'
    },
    'Gacrux': {
        'gender': 'female',
        'tone': 'Mature',
        'pitch': 'Middle'
    },
    'Pulcherrima': {
        'gender': 'female',
        'tone': 'Forward',
        'pitch': 'Middle'
    },
    'Achird': {
        'gender': 'male',
        'tone': 'Friendly',
        'pitch': 'Lower middle'
    },
    'Zubenelgenubi': {
        'gender': 'female',
        'tone': 'Casual',
        'pitch': 'Lower middle',
    },
    'Vindemiatrix': {
        'gender': 'female',
        'tone': 'Gentle',
        'pitch': 'Middle'
    },
    'Sadachbia': {
        'gender': 'male',
        'tone': 'Lively',
        'pitch': 'Lower'
    },
    'Sadaltager': {
        'gender': 'male',
        'tone': 'Knowledgeable',
        'pitch': 'Middle',
    },
    'Sulafat': {
        'gender': 'female',
        'tone': 'Warm',
        'pitch': 'Middle'
    },
}


@dataclass
class TranscribeSegment:
    speaker_id: str
    gender: str
    transcript: str
    tone: str
    start_time: float
    end_time: float


def transcribe_video(
    client,
    model_name,
    gcs_uri: str,
) -> List[TranscribeSegment]:
    prompt = """
    Provide a transcript of this audio file.
    Identify different speakers and attempt to infer their gender.
    For each utterance of the transcript, describe the tone of voice used
    (e.g., enthusiastic, calm, angry, neutral).
    Provide the start and end timestamps in seconds.
    **An utterance should be a distinct segment of speech, typically a sentence
    or a complete phrase, separated by a noticeable pause.**
    """

    video = types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4")

    response = client.models.generate_content(
        model=model_name,
        contents=[video, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema={
                "type": "array",
                "items": {
                    "type":
                    "object",
                    "properties": {
                        "speaker_id": {
                            "type": "string"
                        },
                        "gender": {
                            "type": "string"
                        },
                        "transcript": {
                            "type": "string"
                        },
                        "tone": {
                            "type": "string"
                        },
                        "start_time": {
                            "type": "number",
                            "format": "float"
                        },
                        "end_time": {
                            "type": "number",
                            "format": "float"
                        }
                    },
                    "required": [
                        "speaker_id", "gender", "transcript", "tone",
                        "start_time", "end_time"
                    ]
                }
            }),
    )

    response_json = json.loads(response.text)
    return TypeAdapter(List[TranscribeSegment]).validate_python(response_json)


def match_voice(
    client,
    model_name: str,
    segments: List[TranscribeSegment],
) -> Dict[str, str]:
    """
    Matches speakers to voices from VOICE_OPTIONS using a generative model.

    Args:
        client: The Gemini API client.
        model_name: The name of the generative model to use.
        segments: A list of transcription segments.

    Returns:
        A dictionary mapping speaker IDs to voice names.
    """
    speaker_info = {}
    for segment in segments:
        if segment.speaker_id not in speaker_info:
            speaker_info[segment.speaker_id] = {
                "gender": segment.gender,
                "tones": [],
            }
        speaker_info[segment.speaker_id]["tones"].append(segment.tone)

    voice_map = {}
    for speaker_id, info in speaker_info.items():
        prompt = f"""
        Based on the speaker's gender and vocal tones, select the most fitting voice from the provided options.
        Ensure that a voice option is only used for a single speaker and not for multiple speakers at the same time.


        **Speaker Profile:**
        - **Gender:** {info['gender']}
        - **Vocal Tones:** {', '.join(list(set(info['tones'])))}

        **Voice Options:**
        ```json
        {json.dumps(VOICE_OPTIONS, indent=2)}
        ```

        Analyze the voice options and choose the one that best aligns with the speaker's profile.
        Your response must be a single JSON object with a single key, "voice_name",
        containing the name of the selected voice.
        """

        response = client.models.generate_content(
            model=model_name,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema={
                    "type": "object",
                    "properties": {
                        "voice_name": {
                            "type": "string"
                        }
                    },
                    "required": ["voice_name"]
                }),
        )
        response_json = json.loads(response.text)
        voice_map[speaker_id] = response_json["voice_name"]

    return voice_map

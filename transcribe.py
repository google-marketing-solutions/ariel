from dataclasses import dataclass
import json
from typing import List
from pydantic import TypeAdapter
from google.genai import types


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

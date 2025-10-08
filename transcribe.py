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


def transcribe_video(
    client,
    model_name,
    gcs_uri: str,
) -> List[TranscribeSegment]:
    prompt = """
    Provide a transcript of this audio file.
    Identify different speakers and attempt to infer their gender.
    For each segment of the transcript, describe the tone of voice used
    (e.g., enthusiastic, calm, angry, neutral).
    """

    video = types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4")

    response = client.models.generate_content(
        model=model_name,
        contents=[video, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema={
                "type": "array",
                "description":
                "A list of transcribed audio segments, each with speaker and analysis details.",
                "items": {
                    "type": "object",
                    "description":
                    "Represents a single segment of a transcription with speaker and sentiment analysis.",
                    "properties": {
                        "speaker_id": {
                            "type": "string",
                            "description": "The identifier for the speaker."
                        },
                        "gender": {
                            "type": "string",
                            "description":
                            "The perceived gender of the speaker."
                        },
                        "transcript": {
                            "type": "string",
                            "description":
                            "The transcribed text of the segment."
                        },
                        "tone": {
                            "type":
                            "string",
                            "description":
                            "The detected tone of the speech in the segment."
                        }
                    },
                    "required": ["speaker_id", "gender", "transcript", "tone"]
                }
            }),
    )

    response_json = json.loads(response.text)
    return TypeAdapter(List[TranscribeSegment]).validate_python(response_json)

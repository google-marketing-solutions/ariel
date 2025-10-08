import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import TypeAdapter, ValidationError

from google import genai
from google.genai import types
from video import Transcription

router = APIRouter()


@router.get("/transcribe", response_model=Transcription)
def transcribe_video(
    gcs_uri: str,
    project: str,
    model_name: str = "gemini-2.5-flash",
    location='us-central1',
):
    client = genai.Client(vertexai=True, project=project, location=location)

    prompt = """
    Provide a transcript of this audio file.
    Identify different speakers and attempt to infer their gender.

    For each segment of the transcript, describe the tone of voice used (e.g., enthusiastic, calm, angry, neutral).
    Format the output as a JSON object with two lists: speakers and segments.
    Each speaker object has 'speaker_id', 'name', and 'gender' fields.
    Each segment object has 'speaker_id', 'gender', 'transcript', and 'tone' fields.
    """

    video = types.Part.from_uri(file_uri=gcs_uri, mime_type="video/mp4")

    response = client.models.generate_content(
        model=model_name,
        contents=[video, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"))

    try:
        response_json = json.loads(response.text)
        return TypeAdapter(Transcription).validate_python(response_json)
    except (ValidationError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate the transcription schema: {e}",
        )

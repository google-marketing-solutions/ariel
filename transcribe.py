import json
from fastapi import APIRouter
import vertexai
from vertexai.generative_models import GenerativeModel, Part

router = APIRouter()


@router.get("/transcribe")
def transcribe_video(
    gcs_uri: str, project: str, model_name: str = "gemini-1.5-flash"
):
    """
    Transcribes a video from a GCS bucket using the specified Gemini model.
    """
    vertexai.init(project=project)

    model = GenerativeModel(model_name)

    prompt = """
    Provide a transcript of this audio file.
    Identify different speakers and attempt to infer their gender.

    For each segment of the transcript, describe the tone of voice used (e.g., enthusiastic, calm, angry, neutral).
    Format the output as a JSON object with two lists: speakers and segments.
    Each speaker object has 'speaker_id', 'name', and 'gender' fields.
    Each segment object has 'speaker_id', 'gender', 'transcript', and 'tone' fields.
    """

    video = Part.from_uri(gcs_uri, mime_type="video/mp4")

    response = model.generate_content(
        [video, prompt],
        generation_config={"response_mime_type": "application/json"},
    )

    return json.loads(response.text)

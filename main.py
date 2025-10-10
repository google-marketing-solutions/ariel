from typing import Annotated, List
from cloud_storage import upload_video_to_gcs
from configuration import get_config
from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from generate_audio import generate_audio
from transcribe import TranscribeSegment, transcribe_video, match_voice
from translate import translate_text
from google import genai

from models import Video

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

config = get_config()


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process_video")
async def process_video(
    video: UploadFile,
    original_language: Annotated[str, Form()],
    translate_language: Annotated[str, Form()],
    prompt_enhancements: Annotated[str, Form()],
    speakers: Annotated[str, Form()],
) -> Video:
    video_name = video.filename or "video.mp4"
    gcs_path = upload_video_to_gcs(video_name, video.file,
                                   config.gcs_bucket_name)
    video_gcs_uri = f"gcs://{config.gcs_bucket_name}/{gcs_path}"

    genai_client = genai.Client(vertexai=True,
                                project=config.gcp_project_id,
                                location=config.gcp_project_location)
    transcriptions = transcribe_video(client=genai_client,
                                      model_name=config.gemini_model,
                                      gcs_uri=video_gcs_uri)


##############################
## TESTING END POINTS BELOW ##
##############################


@app.get("/test", response_class=HTMLResponse)
async def read_item_test(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})


@app.get("/transcribe", response_model=list[TranscribeSegment])
def transcribe(
    gcs_uri: str,
    project: str,
    location='us-central1',
):
    client = genai.Client(vertexai=True, project=project, location=location)
    return transcribe_video(client,
                            model_name=config.gemini_model,
                            gcs_uri=gcs_uri)


@app.get("/generate_audio_test")
def generate_audio_test(
    prompt: str,
    voice_name: str,
):
    client = genai.Client(api_key=config.gemini_api_key)
    audio_data = generate_audio(client,
                                prompt=prompt,
                                voice_name=voice_name,
                                model_name=config.gemini_tts_model)

    return JSONResponse(content={"audio_data": audio_data})


@app.post("/match_voice")
def match_voice_endpoint(segments: List[TranscribeSegment]):
    # Initialize the genai client
    client = genai.Client(vertexai=True,
                          project=config.gcp_project_id,
                          location=config.gcp_project_location)

    # Match voices for all speakers
    voice_map = match_voice(client,
                            model_name=config.gemini_model,
                            segments=segments)

    return voice_map

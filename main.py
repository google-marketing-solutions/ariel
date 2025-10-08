from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from generate_audio import generate_audio
from transcribe import TranscribeSegment, transcribe_video
from google import genai

app = FastAPI()

templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/transcribe", response_model=list[TranscribeSegment])
def transcribe(
    gcs_uri: str,
    project: str,
    model_name: str = "gemini-2.5-pro",
    location='us-central1',
):
    client = genai.Client(vertexai=True, project=project, location=location)
    return transcribe_video(client, model_name=model_name, gcs_uri=gcs_uri)


@app.get("/generate_audio_test")
def generate_audio_test(
    api_key: str,
    prompt: str,
):
    client = genai.Client(api_key=api_key)
    audio_data = generate_audio(client,
                                prompt=prompt,
                                voice_name='Rasalgethi',
                                model_name="gemini-2.5-flash-preview-tts")

    return JSONResponse(content={"audio_data": audio_data})

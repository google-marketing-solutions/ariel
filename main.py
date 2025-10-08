from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
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

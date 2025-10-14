import base64
import json
import os
import shutil
import uuid
from typing import Annotated
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

from models import Video, Utterance, Speaker

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

config = get_config()


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
  return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process")
async def process_video(
  video: UploadFile,
  original_language: Annotated[str, Form()],
  translate_language: Annotated[str, Form()],
  prompt_enhancements: Annotated[str, Form()],
  speakers: Annotated[str, Form()],
) -> Video:
  local_video_path, gcs_video_uri = save_video(video)
  genai_client = genai.Client(
    vertexai=True,
    project=config.gcp_project_id,
    location=config.gcp_project_location,
  )
  speaker_list = json.loads(speakers)
  speaker_list = [
    Speaker(speaker_id=s["id"], voice=s["voice"]) for s in speaker_list
  ]
  speaker_map = {s.speaker_id: s for s in speaker_list}

  transcriptions = transcribe_video(
    client=genai_client,
    model_name=config.gemini_tts_model,
    gcs_uri=gcs_video_uri,
    num_speakers=len(speaker_list),
  )

  local_dir = os.path.dirname(local_video_path)
  # original_vocal_path, background_sound_path = separate_audio_from_video(
  #   local_video_path, local_dir
  # )

  utterances: list[Utterance] = []
  for i, t in enumerate(transcriptions):
    uid = str(uuid.uuid4())
    speaker = speaker_map[t.speaker_id]

    translated_text = translate_text(
      genai_client, original_language, translate_language, t.transcript, t.tone
    )
    # Needed until we have an allow-listed project for Gemini TTS
    audio_client = genai.Client(api_key=config.gemini_api_key)
    generated_audio, audio_duration = generate_audio(
      audio_client, translated_text, speaker.voice
    )
    local_audio_path = os.path.join(local_dir, f"audio_{i}.wav")
    save_audio_file(generated_audio, local_audio_path)
    translated_end_time = t.start_time + (audio_duration / 1000)

    u = Utterance(
      id=uid,
      original_text=t.transcript,
      translated_text=translated_text,
      instructions=t.tone,
      speaker=speaker,
      original_start_time=t.start_time,
      original_end_time=t.end_time,
      translated_start_time=t.start_time,
      translated_end_time=translated_end_time,
      is_dirty=False,
      audio_url=local_audio_path,
    )
    utterances.append(u)

  to_return = Video(
    video_id=local_video_path.split("/")[-2],
    original_language=original_language,
    translate_language=translate_language,
    prompt_enhancements=prompt_enhancements,
    speakers=speaker_list,
    utterances=utterances,
  )

  return to_return


def save_video(video: UploadFile) -> tuple[str, str]:
  video_name = video.filename or "video.mp4"
  gcs_path = upload_video_to_gcs(video_name, video.file, config.gcs_bucket_name)
  # save the file locally
  local_dir = f"static/temp/{os.path.dirname(gcs_path)}"
  os.makedirs(name=local_dir, exist_ok=True)
  local_path = f"static/temp/{gcs_path}"
  with open(local_path, "wb") as local_file:
    shutil.copyfileobj(video.file, local_file)

  # save the file to GCS
  video_gcs_uri = f"gs://{config.gcs_bucket_name}/{gcs_path}"
  return local_path, video_gcs_uri


def save_audio_file(audio: str, path: str) -> None:
  with open(path, "wb") as audio_file:
    audio_file.write(base64.b64decode(audio))


##############################
## TESTING END POINTS BELOW ##
##############################


@app.get("/test", response_class=HTMLResponse)
async def read_item_test(request: Request):
  return templates.TemplateResponse("test.html", {"request": request})


@app.get("/transcribe", response_model=list[TranscribeSegment])
def transcribe(gcs_uri: str):
  client = genai.Client(
    vertexai=True,
    project=config.gcp_project_id,
    location=config.gcp_project_location,
  )
  return transcribe_video(
    client, model_name=config.gemini_model, gcs_uri=gcs_uri
  )


@app.get("/generate_audio_test")
def generate_audio_test(
  api_key: str,
  prompt: str,
  voice_name: str,
):
  client = genai.Client(api_key=api_key)
  audio_data = generate_audio(
    client,
    prompt=prompt,
    voice_name=voice_name,
    model_name="gemini-2.5-flash-preview-tts",
  )

  return JSONResponse(content={"audio_data": audio_data})


@app.post("/match_voice")
def match_voice_endpoint(segments: list[TranscribeSegment]):
  # Initialize the genai client
  client = genai.Client(
    vertexai=True,
    project=config.gcp_project_id,
    location=config.gcp_project_location,
  )

  # Match voices for all speakers
  voice_map = match_voice(
    client, model_name=config.gemini_model, segments=segments
  )

  return voice_map

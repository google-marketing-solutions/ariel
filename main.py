import base64
import google.cloud.logging
import json
import logging
import os
import shutil
import uuid
from typing import Annotated
from cloud_storage import (
  get_url_for_path,
  upload_file_to_gcs,
  upload_video_to_gcs,
)
from configuration import get_config
from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from generate_audio import generate_audio
from transcribe import TranscribeSegment, transcribe_video, match_voice
from translate import translate_text
from google import genai
from process import (
  separate_audio_from_video,
  merge_background_and_vocals,
  combine_video_and_audio,
)

from models import (
  RegenerateRequest,
  Video,
  Utterance,
  Speaker,
  RegenerateResponse,
)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

config = get_config()

logging_client = google.cloud.logging.Client()
logging_client.setup_logging(log_level=logging.INFO)



@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
  return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process")
async def process_video(
  video: UploadFile,
  original_language: Annotated[str, Form()],
  translate_language: Annotated[str, Form()],
  prompt_enhancements: Annotated[str, Form()],
  adjust_speed: Annotated[bool, Form()],
  speakers: Annotated[str, Form()],
) -> Video:
  logging.info(f"Starting Process Video for {video.filename}")
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

  logging.info(f"Transcribing {video.filename}")
  transcriptions = transcribe_video(
    client=genai_client,
    model_name=config.gemini_model,
    gcs_uri=gcs_video_uri,
    num_speakers=len(speaker_list),
  )

  local_dir = os.path.dirname(local_video_path)

  utterances: list[Utterance] = []
  logging.info(
    f"Starting to translate utterances and generate audio for {video.filename}"
  )
  for i, t in enumerate(transcriptions):
    uid = str(uuid.uuid4())
    speaker = speaker_map[t.speaker_id]

    translated_text = translate_text(
      genai_client, original_language, translate_language, t.transcript, t.tone
    )
    # Needed until we have an allow-listed project for Gemini TTS
    audio_client = genai.Client(api_key=config.gemini_api_key)
    generated_audio, audio_duration = generate_audio(
      audio_client,
      translated_text,
      speaker.voice,
      model_name=config.gemini_tts_model,
    )
    if audio_duration > 0.0:
      local_audio_path = os.path.join(local_dir, f"audio_{i}.wav")
      save_audio_file(generated_audio, local_audio_path)
    else:
      local_audio_path = ""
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

  logging.info(f"Completed processing {video.filename}")
  return to_return


@app.post("/generate_video")
def generate_video(video_data: Video) -> JSONResponse:
  """Generates the final, translated video.

  Args:
    video_data: the Video object representing the final video.
  """
  logging.info(f"Generating final video for {video_data.video_id}")
  local_dir = f"static/temp/{video_data.video_id}"
  local_video_path = f"{local_dir}/{video_data.video_id}"
  logging.info(f"Separating background for {video_data.video_id}")
  _, background_sound_path = separate_audio_from_video(
    local_video_path, local_dir
  )
  logging.info(f"Merging background and vocals for {video_data.video_id}")
  merged_audio_path = merge_background_and_vocals(
    background_audio_file=background_sound_path,
    dubbed_vocals_metadata=video_data.utterances,
    output_directory=local_dir,
    target_language=video_data.translate_language,
  )
  combined_video_path = (
    f"{local_dir}/{video_data.video_id}.{video_data.translate_language}.mp4"
  )
  combine_video_and_audio(
    local_video_path, merged_audio_path, combined_video_path
  )
  with open(combined_video_path, "rb") as video_file:
    gcs_path = f"{video_data.video_id}/{video_data.video_id}.{video_data.translate_language}.mp4"
    upload_file_to_gcs(
      gcs_path, video_file, config.gcs_bucket_name, "video/mp4"
    )
  #return get_url_for_path(config.gcs_bucket_name, gcs_path)
  to_return = {"video_url": f"{combined_video_path}"}
  return JSONResponse(content=to_return)


@app.post("/regenerate_translation")
def regenerate_translation(req: RegenerateRequest) -> RegenerateResponse:
  """Regenerates the translation for a given utterance.

  Args:
    req: The request object with the video, utterance index, and
        additional instructions.

  Returns:
    A response with the new translation, updated audio file path,
    and the duration of the audio.
  """
  genai_client = genai.Client(
    vertexai=True,
    project=config.gcp_project_id,
    location=config.gcp_project_location,
  )
  utterance = req.video.utterances[req.utterance]
  new_translation = translate_text(
    genai_client,
    req.video.original_language,
    req.video.translate_language,
    utterance.original_text,
    req.instructions,
  )
  audio_client = genai.Client(api_key=config.gemini_api_key)
  audio_data, duration = generate_audio(
    audio_client, new_translation, utterance.speaker.voice
  )
  new_path = utterance.audio_url + str(uuid.uuid1()) + ".wav" # cache busting
  save_audio_file(audio_data, new_path)
  return RegenerateResponse(
    translated_text=new_translation, audio_url=new_path, duration=duration
  )

@app.post("/regenerate_dubbing")
def regenerate_dubbing(req: RegenerateRequest) -> RegenerateResponse:
  """Regenerates the dubbing for a given utterance.

  Args:
    req: The request with the video, utterance index, and additional instructions.

  Returns:
    A response with the new path to the dubbed audio.
  """
  audio_client  = genai.Client(api_key=config.gemini_api_key)
  utterance = req.video.utterances[req.utterance]
  prompt = f"""Generate audio for the TEXT following the INSTRUCTIONS.
  ## Instructions
  {req.instructions}

  ## TEXT
  {utterance.translated_text}
  """
  audio_data, duration = generate_audio(
    audio_client, prompt, utterance.speaker.voice
  )
  new_path = utterance.audio_url + str(uuid.uuid1()) + ".wav" # cache busting
  save_audio_file(audio_data, new_path)
  return RegenerateResponse(
    translated_text=utterance.translated_text, audio_url=new_path, duration=duration
  )


def save_video(video: UploadFile) -> tuple[str, str]:
  """Saves a video file on GCS and locally so that it can be found again.

  Args:
    video: the file to be saved.

  Returns:
    The local path to the and the path on GCS.
  """
  video_name = video.filename or "video.mp4"
  video_name = video_name.replace(" ", "_")
  print(f"#### DEBUG #### The GCS bucket is {config.gcs_bucket_name}")
  gcs_path = upload_video_to_gcs(video_name, video.file, config.gcs_bucket_name)
  # save the file locally
  video.file.seek(0)
  local_dir = f"static/temp/{os.path.dirname(gcs_path)}"
  os.makedirs(name=local_dir, exist_ok=True)
  local_path = f"static/temp/{gcs_path}"
  with open(local_path, "wb") as local_file:
    shutil.copyfileobj(video.file, local_file)

  # save the file to GCS
  video_gcs_uri = f"gs://{config.gcs_bucket_name}/{gcs_path}"
  return local_path, video_gcs_uri


def save_audio_file(audio: str, path: str) -> None:
  """Saves a base64 encoded audio file to the given path.

  Args:
    audio: the base64 encoded audio data.
    path: the path to save the file to.
  """
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

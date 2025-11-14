import json
import logging
import os
import shutil
import uuid
from typing import Annotated

import google.cloud.logging
from cloud_storage import (
    upload_file_to_gcs,
    upload_video_to_gcs,
)
from configuration import get_config
from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from generate_audio import generate_audio, shorten_audio
from google import genai
from google.cloud.logging.handlers import CloudLoggingHandler
from models import (
    RegenerateRequest,
    RegenerateResponse,
    Speaker,
    Utterance,
    Video,
)
from process import (
    combine_video_and_audio,
    merge_background_and_vocals,
    separate_audio_from_video,
)
from transcribe import transcribe_media
from translate import translate_text

# Set up Google Cloud Logging
if "K_SERVICE" in os.environ:
    client = google.cloud.logging.Client()
    handler = CloudLoggingHandler(client)
    google.cloud.logging.handlers.setup_logging(handler)
else:
    logging.basicConfig(level=logging.INFO)

app = FastAPI()

# Check if running in Google Cloud Run
if 'K_SERVICE' in os.environ:
  MOUNT_POINT = "/mnt/ariel"
  app.mount("/mnt", StaticFiles(directory="/mnt"), name="temp")
else:
  # Running locally.
  MOUNT_POINT = "static/temp"
  app.mount("/mnt", StaticFiles(directory="static/temp"), name="temp")

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
    adjust_speed: Annotated[bool, Form()],
    speakers: Annotated[str, Form()],
) -> Video:
  logging.info(f"Starting Process Video for {video.filename}")
  local_video_path, gcs_video_uri = save_video(video)

  logging.info(f"Separating vocals and background music from {video.filename}")
  local_dir = os.path.dirname(local_video_path)
  original_audio_path, vocals_path, background_path = separate_audio_from_video(
      local_video_path, local_dir
  )

  logging.info(
      f"Uploading original audio, vocals and background music to GCS for {video.filename}"
  )
  with open(original_audio_path, "rb") as f:
    upload_file_to_gcs(original_audio_path, f, config.gcs_bucket_name)
  with open(vocals_path, "rb") as f:
    upload_file_to_gcs(vocals_path, f, config.gcs_bucket_name)
  with open(background_path, "rb") as f:
    upload_file_to_gcs(background_path, f, config.gcs_bucket_name)

  gcs_original_audio_uri = f"gs://{config.gcs_bucket_name}/{original_audio_path}"

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
  transcriptions = transcribe_media(
      client=genai_client,
      model_name=config.gemini_model,
      gcs_uri=gcs_original_audio_uri,
      num_speakers=len(speaker_list),
      mime_type="audio/wav",
  )

  utterances: list[Utterance] = []
  logging.info(
      f"Starting to translate utterances and generate audio for {video.filename}"
  )
  for i, t in enumerate(transcriptions):
    uid = str(uuid.uuid4())
    speaker = speaker_map[t.speaker_id]

    translated_text = translate_text(
        genai_client, original_language, translate_language, t.transcript,
        t.tone
    )

    local_audio_path = os.path.join(local_dir, f"audio_{i}.wav")
    audio_duration = generate_audio(
        translated_text,
        t.tone,
        translate_language,
        speaker.voice,
        local_audio_path,
        model_name=config.gemini_tts_model,
    )
    original_duration = t.end_time - t.start_time
    if adjust_speed and audio_duration and audio_duration > original_duration:
      audio_duration = shorten_audio(
          local_audio_path, audio_duration, original_duration
      )

    translated_end_time = t.start_time + audio_duration

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
        removed=False,
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
  local_dir = os.path.join(MOUNT_POINT, video_data.video_id)
  local_video_path = os.path.join(local_dir, video_data.video_id)
  background_sound_path = os.path.join(
      local_dir, "htdemucs", "original_audio", "no_vocals.wav"
  )
  # logging.info(f"Separating background for {video_data.video_id}")
  # _, background_sound_path = separate_audio_from_video(
  #     local_video_path, local_dir
  # )
  logging.info(f"Merging background and vocals for {video_data.video_id}")
  merged_audio_path = merge_background_and_vocals(
      background_audio_file=background_sound_path,
      dubbed_vocals_metadata=video_data.utterances,
      output_directory=local_dir,
      target_language=video_data.translate_language,
  )
  combined_video_path = os.path.join(
      local_dir, f"{video_data.video_id}.{video_data.translate_language}.mp4"
  )
  combine_video_and_audio(
      local_video_path, merged_audio_path, combined_video_path
  )
  public_video_path = f"{MOUNT_POINT}/{video_data.video_id}/{video_data.video_id}.{video_data.translate_language}.mp4"
  to_return = {"video_url": f"{public_video_path}"}
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
  target_dir = os.path.dirname(utterance.audio_url)
  new_file_name = (
      f"audio_{req.utterance}-" + str(uuid.uuid1()) + ".wav"
  )  # cache busting
  new_path = os.path.join(target_dir, new_file_name)
  duration = generate_audio(
      new_translation,
      utterance.instructions,
      req.video.translate_language,
      utterance.speaker.voice,
      new_path,
      config.gemini_tts_model,
  )
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
  utterance = req.video.utterances[req.utterance]
  target_dir = os.path.dirname(utterance.audio_url)
  new_file_name = (
      f"audio_{req.utterance}-" + str(uuid.uuid1()) + ".wav"
  )  # cache busting
  new_path = os.path.join(target_dir, new_file_name)
  duration = generate_audio(
      utterance.translated_text,
      req.instructions,
      req.video.translate_language,
      utterance.speaker.voice,
      new_path,
      config.gemini_tts_model,
  )
  return RegenerateResponse(
      translated_text=utterance.translated_text,
      audio_url=new_path,
      duration=duration,
  )


def save_video(video: UploadFile) -> tuple[str, str]:
  """Saves a video file on GCS and locally so that it can be found again.

  Args:
    video: the file to be saved.

  Returns:
    The local path to the and the path on GCS.
  """
  video_name = video.filename or "video.mp4"
  video_name = sanitize_filename(video_name)
  gcs_path = upload_video_to_gcs(video_name, video.file, config.gcs_bucket_name)
  # save the file locally
  video.file.seek(0)
  local_dir = os.path.join(MOUNT_POINT, os.path.dirname(gcs_path))
  os.makedirs(name=local_dir, exist_ok=True)
  local_path = os.path.join(MOUNT_POINT, gcs_path)
  with open(local_path, "wb") as local_file:
    shutil.copyfileobj(video.file, local_file)

  # save the file to GCS
  video_gcs_uri = f"gs://{config.gcs_bucket_name}/{gcs_path}"
  return local_path, video_gcs_uri


def sanitize_filename(orig: str) -> str:
  """Sanitizes a file name for shell commands.

  Characters in the file name that might cause issues when used in a shell
  command are removed from the name.

  Args:
    orig: the original file name.

  Returns:
    a sanitized version of the name.
  """
  special_chars = " \"'$&*()[]{}<>|;?/~"
  trans_map = str.maketrans(dict.fromkeys(special_chars))
  new_name = orig.translate(trans_map)
  if not new_name:
    return "video.mp4"
  return new_name

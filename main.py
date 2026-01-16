"""Entry point into the Ariel v2 solution."""

# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import concurrent.futures
import functools
import json
import logging
import os
import shutil
from typing import Annotated
import uuid

from cloud_storage import upload_file_to_gcs
from cloud_storage import upload_video_to_gcs
from configuration import get_config
from fastapi import FastAPI
from fastapi import Form
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from generate_audio import generate_audio
from generate_audio import shorten_audio
from google import genai
import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler
from models import RegenerateRequest
from models import RegenerateResponse
from models import Speaker
from models import Utterance
from models import Video
from process import combine_video_and_audio
from process import merge_background_and_vocals
from process import merge_vocals
from process import separate_audio_from_video
from transcribe import annotate_transcript
from transcribe import transcribe_media
from transcribe import TranscribeSegment
from translate import translate_text

# Set up Google Cloud Logging
if "K_SERVICE" in os.environ:
  client = google.cloud.logging.Client()
  handler = CloudLoggingHandler(client)
  google.cloud.logging.handlers.setup_logging(handler)
else:
  logging.basicConfig(level=logging.INFO, force=True)

app = FastAPI()

# Check if running in Google Cloud Run
if "K_SERVICE" in os.environ:
  mount_point = "/mnt/ariel"
  app.mount("/mnt", StaticFiles(directory="/mnt"), name="temp")
else:
  # Running locally.
  mount_point = "temp"
  app.mount("/mnt", StaticFiles(directory="temp"), name="temp")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

config = get_config()


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
  return templates.TemplateResponse("index.html", {"request": request})


def _process_utterance(
    i: int,
    t: TranscribeSegment,
    speaker_map: dict[str, Speaker],
    genai_client: genai.Client,
    original_language: str,
    translate_language: str,
    gemini_model: str,
    gemini_tts_model: str,
    local_dir: str,
    adjust_speed: bool,
) -> Utterance:
  """Processes a single utterance: translates and generates audio.

  Args:
    i: The index of the utterance.
    t: The TranscribeSegment object.
    speaker_map: A map of speaker IDs to Speaker objects.
    genai_client: The GenAI client.
    original_language: The original language.
    translate_language: The target language.
    gemini_model: The Gemini model for translation.
    gemini_tts_model: The Gemini TTS model.
    local_dir: The directory to save audio.
    adjust_speed: Whether to adjust audio speed.

  Returns:
    The processed Utterance object.
  """
  uid = str(uuid.uuid4())
  speaker = speaker_map[t.speaker_id]

  translated_text = translate_text(
      genai_client,
      original_language,
      translate_language,
      t.transcript,
      gemini_model,
      t.tone,
  )

  local_audio_path = os.path.join(local_dir, f"audio_{i}.wav")
  audio_duration = generate_audio(
      translated_text,
      t.tone,
      translate_language,
      speaker.voice,
      local_audio_path,
      model_name=gemini_tts_model,
  )
  original_duration = t.end_time - t.start_time
  if adjust_speed and audio_duration and audio_duration > original_duration:
    audio_duration = shorten_audio(
        local_audio_path, audio_duration, original_duration
    )

  translated_end_time = t.start_time + audio_duration

  return Utterance(
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


@app.post("/process")
async def process_video(
    video: UploadFile,
    original_language: Annotated[str, Form()],
    translate_language: Annotated[str, Form()],
    adjust_speed: Annotated[bool, Form()],
    speakers: Annotated[str, Form()],
    prompt_enhancements: Annotated[str, Form()] = "",
    use_pro_model: Annotated[bool, Form()] = False,
) -> Video:
  """Endpoint to run the initial video processing workflow.

  This function provides the workflow to separate the audio from the video,
  transcribes the audio track, translates the utterances, generates new audio
  from the translations, and returns a new Video object with all of the
  information.

  Args:
    video: the original video file.
    original_language: the language of speech in the original video.
    translate_language: the language to translate the video to.
    prompt_enhancements: extra instructions to send Gemini during translation
        and audio generation.
    adjust_speed: whether to automatically match the length of the generated
        utterances to the original.
    speakers: a list of the speakers in the video. They must be in the order
        they speak in the video.
    use_pro_model: whether to use the pro version of Gemini. If true, the pro
        model defined in the configuration will be used. Otherwise the flash
        version is used.

  Returns:
    A Video object with the information for the dubbing.

  """
  logging.info("Starting Process Video for %s", video.filename)
  local_video_path, _ = save_video(video)

  logging.info("Separating vocals and background music from %s", video.filename)
  local_dir = os.path.dirname(local_video_path)
  original_audio_path, vocals_path, background_path = separate_audio_from_video(
      local_video_path, local_dir
  )

  logging.info(
      "Uploading original audio, vocals and background music to GCS for %s",
      video.filename
  )
  with open(original_audio_path, "rb") as f:
    upload_file_to_gcs(original_audio_path, f, config.gcs_bucket_name)
  with open(vocals_path, "rb") as f:
    upload_file_to_gcs(vocals_path, f, config.gcs_bucket_name)
  with open(background_path, "rb") as f:
    upload_file_to_gcs(background_path, f, config.gcs_bucket_name)

  gcs_original_audio_uri = (
      f"gs://{config.gcs_bucket_name}/{original_audio_path}"
  )

  genai_client = genai.Client(
      vertexai=True,
      project=config.gcp_project_id,
      location="global",
  )
  speaker_list = json.loads(speakers)
  speaker_list = [
      Speaker(speaker_id=s["id"], voice=s["voice"]) for s in speaker_list
  ]
  speaker_map = {s.speaker_id: s for s in speaker_list}

  logging.info("Transcribing %s", video.filename)
  transcript = transcribe_media(original_audio_path)

  if use_pro_model:
    gemini_model = config.gemini_pro_model
    gemini_tts_model = config.gemini_pro_tts_model
  else:
    gemini_model = config.gemini_flash_model
    gemini_tts_model = config.gemini_flash_tts_model

  logging.info("Annotating transcript for %s", video.filename)
  annotated_transcript = annotate_transcript(
      client=genai_client,
      model_name=gemini_model,
      gcs_uri=gcs_original_audio_uri,
      num_speakers=len(speaker_list),
      script=transcript,
      mime_type="audio/wav",
  )

  utterances: list[Utterance] = []
  logging.info(
      "Starting to translate utterances and generate audio for %s",
      video.filename
  )

  process_func = functools.partial(
      _process_utterance,
      speaker_map=speaker_map,
      genai_client=genai_client,
      original_language=original_language,
      translate_language=translate_language,
      gemini_model=gemini_model,
      gemini_tts_model=gemini_tts_model,
      local_dir=local_dir,
      adjust_speed=adjust_speed,
  )

  with concurrent.futures.ThreadPoolExecutor() as executor:
    utterances = list(
        executor.map(
            process_func, range(len(annotated_transcript)), annotated_transcript
        )
    )

  to_return = Video(
      video_id=local_video_path.split("/")[-2],
      original_language=original_language,
      translate_language=translate_language,
      prompt_enhancements=prompt_enhancements,
      speakers=speaker_list,
      utterances=utterances,
      model_name=gemini_model,
      tts_model_name=gemini_tts_model,
  )

  logging.info("Completed processing %s", video.filename)
  return to_return


@app.post("/generate_audio")
def generate_audio_endpoint(video_data: Video) -> JSONResponse:
  """Generates just the audio for the given video.

  Args:
    video_data: the Video object representing the current video.

  Returns:
    A JSON object with the URL to the generated audio.
  """
  logging.info("Generating audio for %s", video_data.video_id)
  local_dir = os.path.join(mount_point, video_data.video_id)
  dubbed_vocals_path = merge_vocals(
      dubbed_vocals_metadata=video_data.utterances,
      output_directory=local_dir,
      target_language=video_data.translate_language,
  )
  public_vocals_path = f"{mount_point}/{video_data.video_id}/{os.path.basename(dubbed_vocals_path)}"
  to_return = {
      "audio_url": f"{public_vocals_path}?v={uuid.uuid4()}",
  }
  return JSONResponse(content=to_return)


@app.post("/generate_video")
def generate_video(video_data: Video) -> JSONResponse:
  """Generates the final, translated video.

  Args:
    video_data: the Video object representing the final video.

  Returns:
    A JSON object with the URL to the completed video.
  """
  logging.info("Generating final video for %s", video_data.video_id)
  local_dir = os.path.join(mount_point, video_data.video_id)
  local_video_path = os.path.join(local_dir, video_data.video_id)
  background_sound_path = os.path.join(
      local_dir, "htdemucs", "original_audio", "no_vocals.wav"
  )
  dubbed_vocals_path = merge_vocals(
      dubbed_vocals_metadata=video_data.utterances,
      output_directory=local_dir,
      target_language=video_data.translate_language,
  )
  logging.info("Merging background and vocals for %s", video_data.video_id)
  merged_audio_path = merge_background_and_vocals(
      background_audio_file=background_sound_path,
      dubbed_vocals_path=dubbed_vocals_path,
      output_directory=local_dir,
      target_language=video_data.translate_language,
  )
  combined_video_path = os.path.join(
      local_dir, f"{video_data.video_id}.{video_data.translate_language}.mp4"
  )
  combine_video_and_audio(
      local_video_path, merged_audio_path, combined_video_path
  )
  public_video_path = f"{mount_point}/{video_data.video_id}/{video_data.video_id}.{video_data.translate_language}.mp4"
  public_vocals_path = f"{mount_point}/{video_data.video_id}/{os.path.basename(dubbed_vocals_path)}"
  public_merged_audio_path = f"{mount_point}/{video_data.video_id}/{os.path.basename(merged_audio_path)}"
  to_return = {
      "video_url": f"{public_video_path}?v={uuid.uuid4()}",
      "vocals_url": f"{public_vocals_path}?v={uuid.uuid4()}",
      "merged_audio_url": f"{public_merged_audio_path}?v={uuid.uuid4()}",
  }
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
      location="global",
  )
  utterance = req.video.utterances[req.utterance]
  new_translation = translate_text(
      genai_client,
      req.video.original_language,
      req.video.translate_language,
      utterance.original_text,
      req.video.model_name,
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
      req.video.tts_model_name,
  )
  return RegenerateResponse(
      translated_text=new_translation, audio_url=new_path, duration=duration
  )


@app.post("/regenerate_dubbing")
def regenerate_dubbing(req: RegenerateRequest) -> RegenerateResponse:
  """Regenerates the dubbing for a given utterance.

  Args:
    req: The request with the video, utterance index, and additional
        instructions.

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
      req.video.tts_model_name,
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
  local_dir = os.path.join(mount_point, os.path.dirname(gcs_path))
  os.makedirs(name=local_dir, exist_ok=True)
  local_path = os.path.join(mount_point, gcs_path)
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
    a sanitized version of the name. If the name is empty after sanitizing,
        video.mp4 is returned.
  """
  special_chars = " \"'$&*()[]{}<>|;?/~"
  trans_map = str.maketrans(dict.fromkeys(special_chars))
  new_name = orig.translate(trans_map)
  if not new_name:
    return "video.mp4"
  return new_name

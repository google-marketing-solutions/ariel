"""Entry point into the Ariel v2.2 solution."""

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
import datetime
import functools
import json
import logging
import os
import shutil
from typing import Annotated, cast
import uuid

from cloud_storage import clean_video_name
from cloud_storage import delete_video_from_gcs
from cloud_storage import download_file_from_gcs
from cloud_storage import fetch_access_token
from cloud_storage import fetch_service_account_email
from cloud_storage import generate_signed_upload_url
from cloud_storage import list_all_videos
from cloud_storage import upload_file_to_gcs
from cloud_storage import upload_video_to_gcs
from configuration import get_config
from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Request
from fastapi import UploadFile
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from generate_audio import generate_audio
from google import genai
import google.cloud.exceptions
import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler
from models import GenerateVideoRequest
from models import RegenerateRequest
from models import RegenerateResponse
from models import Utterance
from models import Video
from models import VideoMetadata
import moviepy
from process import combine_video_and_audio
from process import merge_background_and_vocals
from process import merge_vocals
from process import separate_audio_from_video
import pydantic
from transcribe import transcribe_video
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
  app.mount("/temp", StaticFiles(directory="temp"), name="temp")

config = get_config()


def _process_utterance(
    i: int,
    u: Utterance,
    translate_language: str,
    gemini_tts_model: str,
    local_dir: str,
) -> Utterance:
  """Generates audio for a single utterance.

  Generates audio and updates the utterance timing-related fields.

  Args:
    i: The index of the utterance.
    u: The Utterance object.
    translate_language: The target language.
    gemini_tts_model: The Gemini TTS model.
    local_dir: The directory to save audio.

  Returns:
    The processed Utterance object.
  """
  local_audio_path = os.path.join(local_dir, f"audio_{i}.wav")
  audio_duration = generate_audio(
      u.translated_text,
      u.speaking_instructions,
      translate_language,
      u.speaker.voice,
      1.0,
      local_audio_path,
      model_name=gemini_tts_model,
  )
  translated_end_time = u.original_start_time + audio_duration
  u.audio_url = local_audio_path
  u.translated_start_time = u.original_start_time
  u.translated_end_time = translated_end_time

  return u


@app.post("/api/generate-upload-url")
def generate_upload_url(
    filename: str, content_type: str = "video/mp4"
) -> JSONResponse:
  """Generates a signed URL for uploading a file directly to GCS."""
  now = datetime.datetime.now().isoformat()
  video_name_without_ext, _ = os.path.splitext(filename)
  dir_name = f"{now}-{uuid.uuid4()}-{video_name_without_ext}"
  dir_name = dir_name.replace(":", "_")
  object_name = f"{dir_name}/{dir_name}"

  service_account_email = fetch_service_account_email()
  access_token = fetch_access_token()

  url = generate_signed_upload_url(
      config.gcs_bucket_name,
      object_name,
      content_type=content_type,
      service_account_email=service_account_email,
      access_token=access_token,
  )

  return JSONResponse(content={"url": url, "object_name": object_name})


@app.post("/process")
def process_video(
    translate_language: Annotated[str, Form()],
    use_pro_model: Annotated[bool, Form()] = False,
    video: UploadFile | None = None,
    source_video_id: Annotated[str, Form()] = "",
    update_existing: Annotated[bool, Form()] = False,
    gcs_object_path: Annotated[str, Form()] = "",
) -> JSONResponse:
  """Endpoint to run the initial video processing workflow.

  This function provides the workflow to separate the audio from the video,
  transcribes the audio track, translates the utterances, generates new audio
  from the translations, and returns a new Video object with all of the
  information.

  Args:
    translate_language: the language to translate the video to.
    use_pro_model: whether to use the pro version of Gemini. If true, the pro
      model defined in the configuration will be used. Otherwise the flash
      version is used.
    video: the original video file. Optional if source_video_id is provided.
    source_video_id: the ID of an existing video to fork/process from.
    update_existing: if true, updates the existing project in-place instead of
      forking. This is used when changing the language on the editor page.
    gcs_object_path: the path of the video in GCS. Optional if video or
      source_video_id is provided.

  Returns:
    A Video object with the information for the dubbing.
  """
  if not video and not source_video_id and not gcs_object_path:
    raise HTTPException(
        status_code=400,
        detail=(
            "Either video file, source_video_id, or gcs_object_path must be"
            " provided"
        ),
    )

  logging.info("Starting Process Video")

  local_dir = ""
  video_name = ""
  local_video_path = ""

  # If we're doing something with an existing video project.
  if source_video_id and not update_existing:
    source_dir = os.path.join(mount_point, source_video_id)
    if not os.path.exists(source_dir):
      logging.error("Source video %s not found.", source_video_id)
      return JSONResponse(
          status_code=500,
          content={"error": f"Source video {source_video_id} not found."},
      )

    logging.info("Forking from source_video_id: %s", source_video_id)
    now = datetime.datetime.now().isoformat().replace(":", "_")

    parts = source_video_id.split("-", 3)
    if len(parts) == 4:
      new_id = f"{now}-{parts[3]}"
    else:
      new_id = f"{now}-{uuid.uuid4()}-{source_video_id}"
      new_id = new_id.replace(":", "_")

    local_dir = os.path.join(mount_point, new_id)
    os.makedirs(local_dir, exist_ok=True)

    # Copy video file
    local_video_path = os.path.join(local_dir, new_id)
    shutil.copy2(os.path.join(source_dir, source_video_id), local_video_path)
    video_name = new_id
    gcs_object_name = f"{video_name}/{video_name}"
    with open(local_video_path, "rb") as f:
      upload_file_to_gcs(gcs_object_name, f, config.gcs_bucket_name)

    gcs_video_path = f"gs://{config.gcs_bucket_name}/{gcs_object_name}"

    # Copy separated audio files if present
    for fname in ["original_audio.wav", "background.wav", "vocals.wav"]:
      src_file = os.path.join(source_dir, fname)
      if os.path.exists(src_file):
        shutil.copy2(src_file, os.path.join(local_dir, fname))
  elif update_existing:
    logging.info("Updating existing project: %s", source_video_id)
    gcs_video_path = (
        f"gs://{config.gcs_bucket_name}/{source_video_id}/{source_video_id}"
    )
    source_dir = os.path.join(mount_point, source_video_id)
    local_video_path = os.path.join(source_dir, source_video_id)
  elif gcs_object_path:
    logging.info("Processing video from GCS path: %s", gcs_object_path)
    gcs_video_path = f"gs://{config.gcs_bucket_name}/{gcs_object_path}"
    local_video_path = os.path.join(mount_point, gcs_object_path)
    local_dir = os.path.dirname(local_video_path)
    os.makedirs(local_dir, exist_ok=True)

    # Ensure file is local (download if not exists)
    if not os.path.exists(local_video_path):
      logging.info("Downloading video from GCS to %s", local_video_path)
      download_file_from_gcs(
          config.gcs_bucket_name, gcs_object_path, local_video_path
      )

    video_name = os.path.basename(gcs_object_path)
  else:
    assert video is not None
    logging.info("Processing new video upload: %s", video.filename)
    local_video_path, gcs_video_path = save_video(video)
    local_dir = os.path.dirname(local_video_path)
    video_name = video.filename

  # Check/Run Separation
  logging.info("Separating vocals and background music from %s", video_name)

  # Check if files already exist (e.g. from fork)
  expected_vocals = os.path.join(local_dir, "vocals.wav")
  expected_background = os.path.join(local_dir, "background.wav")
  expected_original = os.path.join(local_dir, "original_audio.wav")

  if os.path.exists(expected_vocals) and os.path.exists(expected_background):
    logging.info("Found existing separated audio, skipping separation.")
    vocals_path = expected_vocals
    background_path = expected_background
    # We still need original_audio_path.
    if os.path.exists(expected_original):
      original_audio_path = expected_original
    else:
      logging.info("Original audio missing, re-running separation.")
      original_audio_path, vocals_path, background_path = (
          separate_audio_from_video(local_video_path, local_dir)
      )
  else:
    original_audio_path, vocals_path, background_path = (
        separate_audio_from_video(local_video_path, local_dir)
    )

  logging.info(
      "Uploading original audio, vocals and background music to GCS for %s",
      video_name,
  )
  with open(original_audio_path, "rb") as f:
    upload_file_to_gcs(original_audio_path, f, config.gcs_bucket_name)
  with open(vocals_path, "rb") as f:
    upload_file_to_gcs(vocals_path, f, config.gcs_bucket_name)
  with open(background_path, "rb") as f:
    upload_file_to_gcs(background_path, f, config.gcs_bucket_name)

  genai_client = genai.Client(
      vertexai=True,
      project=config.gcp_project_id,
      location="global",
  )

  video_clip = moviepy.VideoFileClip(local_video_path)
  duration: float = cast(float, video_clip.duration)
  video_clip.close()

  if use_pro_model:
    gemini_model = config.gemini_pro_model
    gemini_tts_model = config.gemini_pro_tts_model
  else:
    gemini_model = config.gemini_flash_model
    gemini_tts_model = config.gemini_flash_tts_model

  original_language, speaker_list, utterances = transcribe_video(
      gcs_video_path, translate_language, duration, genai_client, gemini_model
  )

  process_func = functools.partial(
      _process_utterance,
      translate_language=translate_language,
      gemini_tts_model=gemini_tts_model,
      local_dir=local_dir,
  )

  with concurrent.futures.ThreadPoolExecutor() as executor:
    utterances = list(
        executor.map(process_func, range(len(utterances)), utterances)
    )

  to_return = Video(
      video_id=os.path.basename(local_dir),
      original_language=original_language,
      translate_language=translate_language,
      speakers=speaker_list,
      utterances=utterances,
      model_name=gemini_model,
      tts_model_name=gemini_tts_model,
  )

  try:
    metadata = to_return.model_dump()
    duration = 0
    try:
      video_clip = moviepy.VideoFileClip(local_video_path)
      duration = cast(float, video_clip.duration)
      video_clip.close()
    except (OSError, AttributeError, KeyError, IndexError):
      if to_return.utterances:
        duration = max([u.translated_end_time for u in to_return.utterances])

    metadata["name"] = clean_video_name(video_name)
    metadata["duration"] = duration
    if "K_SERVICE" in os.environ:
      metadata["url"] = ""
      metadata["download_url"] = ""
      metadata["original_video_url"] = (
          f"{to_return.video_id}/{to_return.video_id}"
      )
    else:
      metadata["url"] = ""
      metadata["download_url"] = ""
      metadata["original_video_url"] = (
          f"{mount_point}/{to_return.video_id}/{to_return.video_id}"
      )
    metadata["created_at"] = str(datetime.datetime.now())
    metadata["has_metadata"] = True

    metadata_path = os.path.join(local_dir, "metadata.json")
    with open(metadata_path, "w") as f:
      json.dump(metadata, f)
    logging.info("Saved draft metadata to %s", metadata_path)

  except (OSError, TypeError) as e:
    logging.warning("Failed to save draft metadata: %s", e)

  logging.info("Completed processing %s", video_name)
  return JSONResponse(content=to_return.model_dump())


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
  mount_path = mount_point.lstrip("/")
  public_vocals_path = f"/{mount_path}/{video_data.video_id}/{os.path.basename(dubbed_vocals_path)}"
  to_return = {
      "audio_url": f"{public_vocals_path}?v={uuid.uuid4()}",
  }
  return JSONResponse(content=to_return)


@app.post("/generate_video")
def generate_video(request: GenerateVideoRequest) -> JSONResponse:
  """Generates the final, translated video.

  Args:
    request: the request to create the final video.

  Returns:
    A JSON object with the URL to the completed video.
  """
  video_data = request.video

  try:
    logging.info("Generating final video for %s", video_data.video_id)
    local_dir = os.path.join(mount_point, video_data.video_id)

    # Find the video file dynamically
    local_video_path = os.path.join(local_dir, video_data.video_id)
    if not os.path.exists(local_video_path):
      # Fallback to find shortest mp4
      video_files = [
          f
          for f in os.listdir(local_dir)
          if f.endswith(".mp4")
          and not f.endswith(f".{video_data.translate_language}.mp4")
      ]
      if not video_files:
        logging.error("No source video file found in %s", local_dir)
        return JSONResponse(
            status_code=500,
            content={"error": f"Source video file not found in {local_dir}"},
        )
      local_video_path = os.path.join(local_dir, min(video_files, key=len))

    background_sound_path = os.path.join(local_dir, "background.wav")
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
        local_dir,
        f"{video_data.video_id}.{video_data.translate_language}.mp4",
    )
    combine_video_and_audio(
        local_video_path, merged_audio_path, combined_video_path
    )
    mount_path = mount_point.lstrip("/")
    public_video_path = f"/{mount_path}/{video_data.video_id}/{video_data.video_id}.{video_data.translate_language}.mp4"
    public_vocals_path = f"/{mount_path}/{video_data.video_id}/{os.path.basename(dubbed_vocals_path)}"
    public_merged_audio_path = f"/{mount_path}/{video_data.video_id}/{os.path.basename(merged_audio_path)}"
    to_return = {
        "video_url": f"{public_video_path}?v={uuid.uuid4()}",
        "vocals_url": f"{public_vocals_path}?v={uuid.uuid4()}",
        "merged_audio_url": f"{public_merged_audio_path}?v={uuid.uuid4()}",
    }

    duration = 0
    try:
      video_clip = moviepy.VideoFileClip(local_video_path)
      duration = cast(float, video_clip.duration)
      video_clip.close()
    except (OSError, AttributeError, KeyError, IndexError):
      if video_data.utterances:
        duration = max([u.translated_end_time for u in video_data.utterances])

    metadata = video_data.model_dump()
    metadata["name"] = (
        f"{clean_video_name(video_data.video_id)}.{video_data.translate_language}.mp4"
    )
    if "K_SERVICE" in os.environ:
      metadata["original_video_url"] = (
          f"{video_data.video_id}/{video_data.video_id}"
      )
    else:
      metadata["original_video_url"] = (
          f"{mount_point}/{video_data.video_id}/{video_data.video_id}"
      )

    if "K_SERVICE" in os.environ:
      # Upload the final video to GCS
      final_video_gcs_path = (
          f"{video_data.video_id}/{os.path.basename(combined_video_path)}"
      )
      with open(combined_video_path, "rb") as f:
        upload_file_to_gcs(final_video_gcs_path, f, config.gcs_bucket_name)
      metadata["url"] = final_video_gcs_path
      metadata["download_url"] = final_video_gcs_path
    else:
      metadata["url"] = public_video_path
      metadata["download_url"] = public_video_path

    metadata["duration"] = duration
    metadata["created_at"] = str(datetime.datetime.now())
    metadata["has_metadata"] = True

    with open(os.path.join(local_dir, "metadata.json"), "w") as f:
      json.dump(metadata, f)
      print(f"metadata.json successfully saved to {local_dir}")

    video_gcs_folder = os.path.dirname(
        local_video_path.split(mount_point + "/")[-1]
    )
    metadata_gcs_path = f"{video_gcs_folder}/metadata.json"
    with open(os.path.join(local_dir, "metadata.json"), "rb") as f:
      upload_file_to_gcs(
          metadata_gcs_path,
          f,
          config.gcs_bucket_name,
          mime_type="application/json",
      )

    return JSONResponse(content=to_return)

  except (OSError, json.JSONDecodeError) as e:
    logging.exception("Error with the metadata file: %s", e)
    return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/regenerate_translation")
def regenerate_translation(req: RegenerateRequest) -> RegenerateResponse:
  """Regenerates the translation for a given utterance.

  Args:
    req: The request object with the video, utterance index, and additional
      instructions.

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
  duration = utterance.translated_end_time - utterance.translated_start_time
  return RegenerateResponse(
      translated_text=new_translation,
      audio_url=utterance.audio_url,
      duration=duration,
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
  target_dir = os.path.join(mount_point, req.video.video_id)
  new_file_name = (
      f"audio_{req.utterance}-" + str(uuid.uuid1()) + ".wav"
  )  # cache busting
  new_path = os.path.join(target_dir, new_file_name)
  duration = generate_audio(
      utterance.translated_text,
      req.instructions,
      req.video.translate_language,
      utterance.speaker.voice,
      float(req.speaking_rate),
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


@app.get("/api/videos")
def get_videos(
    page_token: str | None = None, max_results: int = 5
) -> dict[str, list[VideoMetadata] | str | None]:
  """Fetches the list of videos based on the environment.

  Args:
    page_token: The page token used by pagination with GCS.
    max_results: The maximum number of results to return at a time.

  Returns:
    A dict with keys:
      videos: the list of VideoMetadata objects for the videos found.
      next_page_token: the next page token or an empty string.
  """
  if "K_SERVICE" in os.environ:
    return list_all_videos(
        config.gcs_bucket_name,
        page_token=page_token,
        max_results=max_results,
    )

  videos_list: list[VideoMetadata] = []
  try:
    for root, _, files in os.walk(mount_point):
      for file in files:
        if file.lower().endswith(".mp4"):
          folder_name = os.path.basename(root)
          if file == folder_name:
            continue
          full_path = os.path.join(root, file)
          relative_path = os.path.relpath(full_path, mount_point)
          web_path = f"/temp/{relative_path}".replace(os.path.sep, "/")
          creation_time = os.path.getmtime(full_path)
          meta_path = os.path.join(root, "metadata.json")
          if os.path.exists(meta_path):
            try:
              with open(meta_path) as f:
                file_data = f.read()
                video = VideoMetadata.model_validate_json(file_data)
                videos_list.append(video)
            except (OSError, pydantic.ValidationError) as e:
              print("Error reading metadata for %s: %s", file, e)
          else:
            videos_list.append(
                VideoMetadata(
                    video_id=folder_name,
                    name=clean_video_name(file),
                    url=web_path,
                    download_url=web_path,
                    created_at=datetime.datetime.fromtimestamp(creation_time),
                    original_language="Unknown",
                    translate_language="Unknown",
                    duration=0,
                    speakers=[],
                    has_metadata=False,
                    original_video_url=f"/temp/{folder_name}/{folder_name}",
                )
            )
      videos_list.sort(key=lambda x: x.created_at, reverse=True)
  except OSError as e:
    print("Error listing videos: %s", e)
  return {"videos": videos_list, "next_page_token": ""}


@app.get("/api/projects/{video_id}")
def load_project(video_id: str):
  """Loads and returns the metadata for a given video project.

  Args:
    video_id: The ID of the video project to load.

  Returns:
    The project metadata as a JSON object, or an error object with error
    details.
  """
  try:
    local_dir = os.path.join(mount_point, video_id)
    metadata_path = os.path.join(local_dir, "metadata.json")

    with open(metadata_path) as f:
      return json.load(f)
  except (OSError, json.JSONDecodeError) as e:
    logging.exception("Error loading the metadata for %s: %s", video_id, e)
    return JSONResponse(
        status_code=404, content={"error": "The file doesn't exist"}
    )


@app.delete("/api/videos/{video_id}")
def delete_video(video_id: str) -> JSONResponse:
  """Deletes the given video project from the library.

  Args:
    video_id: The ID of the video project to delete.

  Returns:
    A JSONResponse with either success or the error if one occurs.
  """
  try:
    if "K_SERVICE" in os.environ:
      delete_video_from_gcs(config.gcs_bucket_name, video_id)
      return JSONResponse(
          status_code=200,
          content={"message": "Video deleted successfully"},
      )
    else:
      local_dir = os.path.join(mount_point, video_id)
      if os.path.exists(local_dir):
        shutil.rmtree(local_dir)
        return JSONResponse(
            status_code=200,
            content={"message": "Video deleted successfully"},
        )
      else:
        return JSONResponse(
            status_code=404, content={"error": "Video not found"}
        )
  except (OSError, google.cloud.exceptions.GoogleCloudError) as e:
    print("Error deleting video project: %s", e)
    return JSONResponse(
        status_code=500, content={"error": f"Error deleting video: {e}"}
    )


@app.get("/{catchall:path}")
async def catch_all(
    request: Request,
    catchall: str,  # pyright: ignore[reportUnusedParameter]
):
  """Used to server the frontend files or a 404.

  Args:
    request: The fastAPI request object (not used)
    catchall: The path being requested.

  Returns:
    The contents of the file at catchall from the frontend, or a 404 response.
  """
  file_path = os.path.join("frontend/dist/frontend/browser", catchall)
  if os.path.isfile(file_path):
    return FileResponse(file_path)

  index_path = os.path.join("frontend/dist/frontend/browser", "index.html")
  if os.path.isfile(index_path):
    return FileResponse(index_path)

  return HTMLResponse(status_code=404, content="Frontend not found")

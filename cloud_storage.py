"""Functions to upload files to Google Cloud Storage."""

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

import datetime
import logging
import mimetypes
import re
import typing
import uuid
from google.cloud import storage
import json
import os
import google.auth



def upload_video_to_gcs(
    video_name: str, video_file: typing.BinaryIO, bucket_name: str
) -> str:
  """Uploads a video to a Google Cloud Storage bucket, creating a new folder.

  This is used for the initial upload of a video. A new, unique path is created
  to upload it to, ensuring multiple users don't end up using the same video.

  Args:
    video_name: the name of the video being uploaded.
    video_file: the file-like object with the video's data.
    bucket_name: The name of the Google Cloud Storage bucket to store the
        video in.

  Returns:
    The path to the uploaded file in GCS.
  """
  now = datetime.datetime.now().isoformat()
  mime_type = mimetypes.guess_type(video_name)[0] or "video/mp4"
  dir_name = f"{now}-{str(uuid.uuid4())}-{video_name}"
  dir_name = dir_name.replace(":", "_")
  dest_path = f"{dir_name}/{dir_name}"

  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(dest_path)

  blob.upload_from_file(video_file, content_type=mime_type)
  logging.info("Initial GCS upload of video to %s.", dest_path)

  return dest_path


def upload_file_to_gcs(
    target_path: str,
    file_object: typing.BinaryIO,
    bucket_name: str,
    mime_type: str = "",
) -> str:
  """Uploads a file to GCS.

  Args:
    target_path: the path to save the file to, including the file name.
    file_object: the binary file-like object to store.
    bucket_name: the name of the GCS bucket to use.
    mime_type: the file's mime-type. If not provided, it is guessed using the
      target path.

  Returns:
    the path to the file in GCS.
  """
  if not mime_type:
    mime_type = (
        mimetypes.guess_type(target_path)[0] or "application/octet-stream"
    )

  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(target_path)
  blob.upload_from_file(file_object, content_type=mime_type)
  logging.info("Uploaded file %s to GCS.", target_path)
  return target_path


def get_url_for_path(bucket_name: str, path: str, download_filename: str = "", service_account_email: str = None, access_token: str = None) -> str:
  """Returns a URL that can be used to fetch the files stored in GCS.

  Args:
    bucket_name: the name of the GCS bucket the files is stored in.
    path: the path to the file the URL will point to.
    download_filename: optional filename to force download with Content-Disposition.

  Returns:
    A URL that points to the file requested. The URL is valid for 24 hours.
  """
  storage_client = storage.Client()

  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(path)
  kwargs = {
      "version": "v4",
      "expiration": (60 * 60 * 24),
      "method": "GET",
      "service_account_email": service_account_email,
      "access_token": access_token,
  }
  if download_filename:
      kwargs["response_disposition"] = f'attachment; filename="{download_filename}"'
  url = blob.generate_signed_url(**kwargs)

  return url

def fetch_service_account_email() -> str:
  service_account_email = None
  try:
      credentials, _ = google.auth.default()
      if hasattr(credentials, "service_account_email"):
          service_account_email = credentials.service_account_email
  except Exception as e:
      logging.warning(f"Could not get default credentials: {e}")

  if not service_account_email or service_account_email == "default":
        # Fallback to metadata server if email is not in credentials or is 'default'
        import requests
        try:
             metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
             headers = {"Metadata-Flavor": "Google"}
             response = requests.get(metadata_url, headers=headers, timeout=2)
             response.raise_for_status()
             service_account_email = response.text.strip()
        except Exception:
             logging.warning("Could not determine service account email, signed URL generation might fail.")
  return service_account_email

def fetch_access_token() -> str:
  """Fetches the access token for the current request."""
  access_token = None
  try:
      if not credentials.token:
          from google.auth.transport.requests import Request
          credentials.refresh(Request())
      access_token = credentials.token
  except Exception as e:
      logging.warning(f"Could not refresh credentials: {e}")
  return access_token

def clean_video_name(filename: str) -> str:
  """Removes the timestamp and UUID prefix from the filename."""
  name = os.path.basename(filename)
  pattern = r"^.+?-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-"
  clean_name = re.sub(pattern, "", name)
  return clean_name

def list_all_videos(bucket_name: str) -> list[dict]:
  """Returns a list of translated videos with their metadata."""
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blobs = storage_client.list_blobs(bucket_name)

  videos = []

  for blob in blobs:
    if blob.name.lower().endswith(".mp4"):
      parts = blob.name.split("/")
      if len(parts) >= 2:
          folder_name = parts[-2]
          file_name = parts[-1]
          if folder_name == file_name:
              continue

      try:
        service_account_email = fetch_service_account_email()
        access_token = fetch_access_token()
        url = get_url_for_path(bucket_name, blob.name, service_account_email=service_account_email, access_token=access_token)
        download_url = get_url_for_path(bucket_name, blob.name, download_filename=clean_video_name(blob.name), service_account_email=service_account_email, access_token=access_token)
      except Exception as e:
        logging.error(f"Error generating signed URL for {blob.name}: {e}")
        url = ""
        download_url = ""


      folder = os.path.dirname(blob.name)
      metadata_path = f"{folder}/metadata.json"
      meta = {
          "original_language": "Unknown",
          "translate_language": "Unknown",
          "duration": 0,
          "speakers": []
      }
      metadata_blob = bucket.blob(metadata_path)
      if metadata_blob.exists():
          try:
              json_str = metadata_blob.download_as_text()
              file_data = json.loads(json_str)
              meta.update(file_data)
          except Exception as e:
              logging.error(f"Error fetching metadata for {blob.name}: {e}")

      raw_speakers = meta.get("speakers", [])
      clean_speakers = []
      for s in raw_speakers:
          if "voice" in s:
              clean_speakers.append({"voice": s["voice"]})

      videos.append({
        "name": clean_video_name(blob.name),
        "url": url,
        "download_url": download_url,
        "created_at": blob.time_created,
        "original_language": meta.get("original_language", "Unknown"),
        "translate_language": meta.get("translate_language", "Unknown"),
        "duration": meta.get("duration", 0),
        "speakers": clean_speakers
      })

  videos.sort(key=lambda x: x['created_at'], reverse=True)

  return videos

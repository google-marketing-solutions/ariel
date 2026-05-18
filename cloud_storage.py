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
import os
import re
import typing
import uuid

from fastapi import status
import google.auth
from google.auth.credentials import Credentials
import google.auth.exceptions
from google.auth.transport.requests import Request
from google.cloud import storage
import google.cloud.exceptions
from models import VideoMetadata
import pydantic
import requests


def generate_gcs_path(filename: str) -> str:
  """Generates a unique GCS path for a file based on current time and UUID.

  Args:
    filename: The original name of the file.

  Returns:
    A string representing the GCS path in the format 'dir_name/dir_name'.
  """
  now = datetime.datetime.now().isoformat()
  video_name_without_ext, _ = os.path.splitext(filename)
  dir_name = f"{now}-{uuid.uuid4()}-{video_name_without_ext}"
  dir_name = dir_name.replace(":", "_")
  return f"{dir_name}/{dir_name}"


def upload_video_to_gcs(
    video_name: str, video_file: typing.BinaryIO, bucket_name: str
) -> str:
  """Uploads a video to a Google Cloud Storage bucket, creating a new folder.

  This is used for the initial upload of a video. A new, unique path is created
  to upload it to, ensuring multiple users don't end up using the same video.

  Args:
    video_name: the name of the video being uploaded.
    video_file: the file-like object with the video's data.
    bucket_name: The name of the Google Cloud Storage bucket to store the video
      in.

  Returns:
    The path to the uploaded file in GCS.
  """
  mime_type = mimetypes.guess_type(video_name)[0] or "video/mp4"
  dest_path = generate_gcs_path(video_name)

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


def generate_signed_upload_url(
    bucket_name: str,
    object_name: str,
    content_type: str = "video/mp4",
    service_account_email: str = "",
    access_token: str = "",
) -> str:
  """Generates a signed URL for uploading a file to GCS using PUT.

  Args:
    bucket_name: the name of the GCS bucket.
    object_name: the path/name of the object to create.
    content_type: the expected content type of the file to be uploaded.
    service_account_email: optional service account email.
    access_token: optional access token.

  Returns:
    A signed URL string.
  """
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(object_name)

  url = blob.generate_signed_url(
      version="v4",
      expiration=datetime.timedelta(minutes=15),
      method="PUT",
      content_type=content_type,
      service_account_email=service_account_email,
      access_token=access_token,
  )
  return url


def download_file_from_gcs(bucket_name: str, object_name: str, local_path: str):
  """Downloads a file from GCS to a local path.

  Args:
    bucket_name: the name of the GCS bucket.
    object_name: the path/name of the object in GCS.
    local_path: the local path to save the file to.
  """
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(object_name)
  blob.download_to_filename(local_path)
  logging.info("Downloaded %s from GCS to %s", object_name, local_path)


def get_url_for_path(
    bucket_name: str,
    path: str,
    download_filename: str = "",
    service_account_email: str = "",
    access_token: str = "",
) -> str:
  """Returns a URL that can be used to fetch the files stored in GCS.

  Args:
    bucket_name: the name of the GCS bucket the files is stored in.
    path: the path to the file the URL will point to.
    download_filename: optional filename to force download with
      Content-Disposition.
    service_account_email: optional service account email to use for
      authentication.
    access_token: optional access token to use for authentication.

  Returns:
    A URL that points to the file requested. The URL is valid for 24 hours.
  """
  storage_client = storage.Client()

  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(path)
  kwargs = {
      "version": "v4",
      "expiration": 60 * 60 * 24,
      "method": "GET",
      "service_account_email": service_account_email,
      "access_token": access_token,
  }
  if download_filename:
    kwargs["response_disposition"] = (
        f'attachment; filename="{download_filename}"'
    )
  url = blob.generate_signed_url(**kwargs)

  return url


def fetch_service_account_email() -> str:
  """Fetches the email of the default service account.

  Returns:
    The service account email address.
  """
  if "GCP_SERVICE_ACCOUNT_EMAIL" in os.environ:
    return os.environ["GCP_SERVICE_ACCOUNT_EMAIL"]

  service_account_email = ""
  try:
    credentials, _ = typing.cast(tuple[Credentials, str], google.auth.default())
    if hasattr(credentials, "service_account_email"):
      service_account_email = typing.cast(
          str, credentials.service_account_email
      )
  except google.auth.exceptions.DefaultCredentialsError as e:
    logging.warning("Could not get default credentials: %s", e)

  if not service_account_email or service_account_email == "default":
    # Fallback to metadata server if email is not in credentials or is 'default'
    try:
      metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"
      headers = {"Metadata-Flavor": "Google"}
      response = requests.get(metadata_url, headers=headers, timeout=5)
      if response.status_code == status.HTTP_200_OK:
        service_account_email = response.text.strip()
    except requests.exceptions.RequestException as e:
      logging.warning(
          "Could not determine service account email from metadata server: %s",
          e,
      )
  return service_account_email


def fetch_access_token() -> str:
  """Fetches the access token for the current request.

  If the current credentials do not have a token, an attempt is made to refresh
  the token.

  Returns:
    If available, the credentials access token, otherwise an empty string.
  """
  access_token = ""
  try:
    credentials, _ = typing.cast(tuple[Credentials, str], google.auth.default())
    if not credentials.token:
      credentials.refresh(Request())
    access_token = credentials.token
  except (
      google.auth.exceptions.DefaultCredentialsError,
      google.auth.exceptions.RefreshError,
  ) as e:
    logging.warning("Could not refresh credentials: %s", e)
  if access_token:
    return access_token
  return ""


def clean_video_name(filename: str) -> str:
  """Removes the timestamp and UUID prefix from the filename.

  Args:
    filename: The original name of the file.

  Returns:
    The name without a timestamp or UUID.
  """
  name = os.path.basename(filename)
  pattern = (
      r"^.+?-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-"
  )
  clean_name = re.sub(pattern, "", name)
  return clean_name


def list_all_videos(
    bucket_name: str, page_token: str | None, max_results: int = 5
) -> dict[str, list[VideoMetadata] | str | None]:
  """Returns a list of translated videos with their metadata.

  Args:
    bucket_name: the name of the GCS bucket to list videos from.
    page_token: optional token to fetch the next page.
    max_results: max number of videos per page.

  Returns:
    A dict with 'videos' list and 'next_page_token' string.
  """
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)

  # The match_glob filters out uncompleted/raw video files,
  # keeping only the translated ones (`.es-ES.mp4`, etc)
  iterator = storage_client.list_blobs(
      bucket_name,
      max_results=max_results,
      page_token=page_token,
      match_glob="**/*.??-??.mp4",
  )

  pages = iterator.pages

  try:
    page = next(pages)
    blobs: list[storage.Blob] = list(page)
    next_page_token: str = iterator.next_page_token
  except StopIteration:
    blobs = []
    next_page_token = ""

  videos: list[VideoMetadata] = []

  for blob in blobs:
    if not blob.name:
      continue
    blob_name = typing.cast(str, blob.name)
    if blob_name.lower().endswith(".mp4"):
      parts = blob_name.split("/")
      if len(parts) < 2:
        continue
      folder_name = parts[-2]
      file_name = parts[-1]
      if folder_name == file_name:
        continue

      try:
        service_account_email = fetch_service_account_email()
        access_token = fetch_access_token()
        url = get_url_for_path(
            bucket_name,
            blob_name,
            service_account_email=service_account_email,
            access_token=access_token,
        )
        download_url = get_url_for_path(
            bucket_name,
            blob_name,
            download_filename=clean_video_name(blob_name),
            service_account_email=service_account_email,
            access_token=access_token,
        )
      except google.cloud.exceptions.GoogleCloudError as e:
        logging.error("Error generating signed URL for %s: %s", blob.name, e)
        url = ""
        download_url = ""

      folder = str(os.path.dirname(blob_name))
      metadata_path = f"{folder}/metadata.json"
      metadata_blob = bucket.blob(metadata_path)
      try:
        json_str = metadata_blob.download_as_text()
        video = VideoMetadata.model_validate_json(json_str)
        video.url = url
        video.download_url = download_url
        videos.append(video)
      except google.cloud.exceptions.NotFound:
        original_video_path = f"{folder_name}/{folder_name}"
        original_video_url = get_url_for_path(
            bucket_name,
            original_video_path,
            service_account_email=service_account_email,
            access_token=access_token,
        )
        # Backwards compatibility for older deployments.
        videos.append(
            VideoMetadata(
                name=clean_video_name(blob.name),
                url=url,
                original_video_url=original_video_url,
                download_url=download_url,
                created_at=blob.time_created or datetime.datetime.now(),
                original_language="Unknown",
                translate_language="Unknown",
                duration=0,
                speakers=[],
                video_id=folder_name,
                has_metadata=False,
            )
        )
      except (
          google.cloud.exceptions.GoogleCloudError,
          pydantic.ValidationError,
      ) as e:
        logging.error(
            "Error fetching or parsing metadata for %s: %s", blob.name, e
        )

  videos.sort(key=lambda x: x.created_at, reverse=True)
  return {"videos": videos, "next_page_token": next_page_token}


def delete_video_from_gcs(bucket_name: str, video_id: str):
  """Deletes a given video project from the given GCS bucket.

  Args:
    bucket_name: The name of the bucket the video is in.
    video_id: The ID string of the video to delete.

  Raises:
    google.cloud.exceptions.GoogleCloudError: raised if there is an issue
    removing the project.
  """
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blobs: list[storage.Blob] = list(bucket.list_blobs(prefix=video_id))

  for blob in blobs:
    try:
      blob.delete()
      logging.info("Deleted blob: %s", blob.name)
    except google.cloud.exceptions.GoogleCloudError as e:
      logging.warning("Failed to delete blob %s: %s", blob.name, e)
      raise e

  logging.info("Deleted video %s from GCS.", video_id)

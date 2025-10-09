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

from datetime import datetime
import mimetypes
import typing
import uuid
from google.cloud import storage


def upload_video_to_gcs(video_file: typing.BinaryIO, mime_type: str, bucket_name: str) -> str:
  """Uploads a video to a Google Cloud Storage bucket, creating a new folder.

  This is used for the initial upload of a video. A new, unique path is created
  to upload it to, ensuring multiuple users don't end up using the same video.

  Args:
      file_object: A file-like object to upload.
      mime_type: the mime-type of the video (e.g. "video/mp4")
      bucket_name: The name of the Google Cloud Storage bucket to store the video
          in.

  Returns: The path to the uploaded file in GCS.
  """

  extension = mimetypes.guess_extension(mime_type)
  dir_name = datetime.now().isoformat() + str(uuid.uuid4())
  dest_path = f"{dir_name}/{dir_name}{extension}"

  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(dest_path)

  blob.upload_from_file(video_file, content_type=mime_type)
  print(f"Uploaded {dest_path} to GCS.")

  return dest_path

def upload_file_to_gcs(target_path: str, file_object: typing.BinaryIO, bucket_name: str, mime_type: str="") -> None:
  """Uploads a file to GCS.

  Args:
    target_path: the path to save the file to, including the file name.
    file_object: the binary file-like object to store.
    bucket_name: the name of the GCS bucket to use.
    mime_type: the file's mime-type. If not provided, it is guessed using the target path.
  """
  if not mime_type:
    mime_type = mimetypes.guess_file_type(target_path)[0] or "application/octet-stream"

  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(target_path)
  blob.upload_from_file(file_object, content_type=mime_type)

def get_url_for_path(bucket_name: str, path: str) -> str:
  """Returns a URL that can be used to fetch the files stored in GCS.

  Args:
    bucket_name: the name of the GCS bucket the files is stored in.
    path: the path to the file the URL will point to.

  Returns:
    A URL that points to the file requested. The URL is valid for 24 hours.
  """
  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(path)

  url = blob.generate_signed_url(version="v4", expiration=(60*60*24), method="GET")

  return url


if __name__ == "__main__":
  test_bucket = "ariel-v2-test-bucket"
  with open("cloud_storage.py", "rb") as in_file:
    mime_type = "text/x-python"
    save_path = upload_video_to_gcs(
      in_file, "text/x-python", test_bucket
    )
    print(f"The file was saved to {save_path}")
    return_url = get_url_for_path(test_bucket, save_path)
    print(f"You can get the file at {return_url}")


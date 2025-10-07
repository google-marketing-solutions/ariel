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
import uuid
from google.cloud import storage


def upload_video_to_gcs(file_object, mime_type, bucket_name) -> str:
  """Uploads a file to a Google Cloud Storage bucket.

  Args:
      file_object: A file-like object to upload.
      bucket_name: The name of the Google Cloud Storage bucket.
      destination_blob_name: The name of the blob (file) in the bucket.

  Returns: The path to the uploaded file in GCS.
  """

  extension = mimetypes.guess_extension(mime_type)
  dir_name = datetime.now().isoformat() + str(uuid.uuid4())
  dest_path = f"{dir_name}/{dir_name}{extension}"

  storage_client = storage.Client()
  bucket = storage_client.bucket(bucket_name)
  blob = bucket.blob(dest_path)

  blob.upload_from_file(file_object, content_type=mime_type)
  print(f"Uploaded {dest_path} to GCS.")

  return dest_path


if __name__ == "__main__":
  with open("cloud_storage.py", "rb") as in_file:
    mime_type = "text/x-python"
    save_path = upload_video_to_gcs(
      in_file, "text/x-python", "ariel-v2-test-bucket"
    )
    print(f"The file was saved to {save_path}")

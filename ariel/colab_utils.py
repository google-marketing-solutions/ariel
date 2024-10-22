# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A module streamlining Ariel runs in Google Colab only."""

import os
from typing import Final
from absl import logging
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
import tensorflow as tf

_BASE_DIRECTORY_COLAB: Final[str] = "/content"
_BASE_DIRECTORY_DRIVE: Final[str] = "/content/drive"


def extract_file_id(sharable_link: str) -> str | None:
  """Extracts the file ID from a sharable link.

  Args:
    sharable_link: The sharable link to the file.

  Returns:
    The file ID, or None if the ID could not be extracted.
  """
  try:
    if "id=" in sharable_link:
      return sharable_link.split("id=")[1]
    elif "/d/" in sharable_link:
      return sharable_link.split("/d/")[1].split("/")[0]
    elif "/file/d/" in sharable_link:
      return sharable_link.split("/file/d/")[1].split("/")[0]
    else:
      return
  except Exception:
    return


def get_parent_path(service: Resource, parent_id: str) -> str:
  """Recursively retrieves the path of parent folders.

  Args:
    service: The Drive API service instance.
    parent_id: The ID of the parent folder.

  Returns:
    The path of the parent folders.
  """
  parent_metadata = (
      service.files()
      .get(fileId=parent_id, fields="name,parents", supportsAllDrives=True)
      .execute()
  )
  parent_path = f"/{parent_metadata['name']}"
  if "parents" in parent_metadata:
    parent_path = (
        get_parent_path(service, parent_metadata["parents"][0]) + parent_path
    )
  return parent_path


def get_file_path_from_sharable_link(sharable_link: str) -> str | None:
  """Determines the file path on Google Drive given a sharable link.

  Args:
    sharable_link: The sharable link to the file.

  Returns:
    The file path on Google Drive, or None if the path could not be determined.
  """
  try:
    file_id = extract_file_id(sharable_link)
    if not file_id:
      return
    creds, _ = default()
    service = build("drive", "v3", credentials=creds)
    metadata = (
        service.files()
        .get(fileId=file_id, fields="name,parents", supportsAllDrives=True)
        .execute()
    )
    path = _BASE_DIRECTORY_DRIVE
    if "parents" in metadata:
      parent_id = metadata["parents"][0]
      path += get_parent_path(service, parent_id)
    path = f'{path}/{metadata["name"]}'
    return path
  except Exception as e:
    logging.error(f"Could not determine the file path due to the error: {e}")
    return


def copy_file_to_colab(
    *, source_file_path: str, destination_folder: str = _BASE_DIRECTORY_COLAB
) -> str:
  """Returns a file path to the copied input file.

  Args:
    source_file_path: The path to the source file.
    destination_folder: The destination directory in Colab.
  """
  destination_file_path = (
      f"{destination_folder}/{os.path.basename(source_file_path)}"
  )
  tf.io.gfile.copy(source_file_path, destination_file_path, overwrite=True)
  return destination_file_path


def copy_output_to_google_drive(
    *, colab_dir: str, google_drive_dir: str
) -> None:
  """Copies the contents of the 'output' subdirectory in a Colab directory.

  to a new directory in Google Drive with the same name as the Colab directory.

  Args:
    colab_dir: The path to the Colab directory.
    google_drive_dir: The path to the Google Drive directory.
  """
  output_dir = os.path.join(colab_dir, "output")
  destination_dir = os.path.join(google_drive_dir, os.path.basename(colab_dir))
  tf.io.gfile.makedirs(destination_dir)
  for filename in os.listdir(output_dir):
    source_path = os.path.join(output_dir, filename)
    destination_path = os.path.join(destination_dir, filename)
    if not tf.io.gfile.exists(destination_path):
      tf.io.gfile.copy(source_path, destination_path, overwrite=True)

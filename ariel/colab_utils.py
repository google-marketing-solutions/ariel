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

import dataclasses
import os
from typing import Final
from typing import Mapping, Sequence
from absl import logging
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
import gspread
import pandas as pd
import tensorflow as tf

_BASE_DIRECTORY_COLAB: Final[str] = "/content"
_BASE_DIRECTORY_DRIVE: Final[str] = "/content/drive"
_STRING_COLUMNS: Final[Sequence[str]] = (
    "text",
    "translated_text",
    "speaker_id",
    "ssml_gender",
    "assigned_voice",
)
_FLOAT_COLUMNS: Final[Sequence[str]] = (
    "start",
    "end",
    "pitch",
    "speed",
    "volume_gain_db",
    "stability",
    "similarity_boost",
    "style",
)
_BOOL_COLUMNS: Final[Sequence[str]] = (
    "for_dubbing",
    "adjust_speed",
    "use_speaker_boost",
)


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
  print(f"The output is saved in: {destination_dir}")


def get_google_sheet_as_dataframe(sheet_link: str) -> pd.DataFrame:
  """Returns Google Sheet using the provided URL as a Pandas DataFrame.

  Args:
    sheet_link: The URL of the Google Sheet.

  Returns:
    A Pandas DataFrame containing the sheet data.
  """
  creds, _ = default()
  gc = gspread.authorize(creds)
  spreadsheet = gc.open_by_url(sheet_link)
  worksheet = spreadsheet.sheet1
  rows = worksheet.get_all_values()
  return pd.DataFrame(rows[1:], columns=rows[0])


@dataclasses.dataclass
class ScriptMetadata:
  """Instance with script metadata.

  Attributes:
      script_with_timestamps: A sequence of dictionaries, where each dictionary
        represents a speech segment and contains the keys "start", "end", and
        "text".
      assigned_voice: A sequence of assigned voices for speech segments.
      google_text_to_speech_parameters: A sequence of mappings with Google
        Text-to-Speech parameters ("pitch", "speed", "volume_gain_db"), or None
        if not applicable.
      elevenlabs_text_to_speech_parameters: A sequence of mappings with
        ElevenLabs Text-to-Speech parameters ("stability", "similarity_boost",
        "style", "use_speaker_boost"), or None if not applicable.
  """

  script_with_timestamps: Sequence[Mapping[str, float | str]]
  assigned_voice: Sequence[str]
  google_text_to_speech_parameters: (
      Sequence[Mapping[str, float | int]] | None
  ) = None
  elevenlabs_text_to_speech_parameters: (
      Sequence[Mapping[str, float | int | bool]] | None
  ) = None


def create_script_metadata_from_dataframe(df: pd.DataFrame) -> ScriptMetadata:
  """Returns a ScriptMetadata instance from a Pandas DataFrame.

  Args:
    df: The DataFrame to process.
  """
  script_with_timestamps = [
      {
          "start": float(start),
          "end": float(end),
          "text": str(text),
          "speaker_id": str(speaker_id),
          "ssml_gender": str(ssml_gender),
      }
      for start, end, text, speaker_id, ssml_gender in zip(
          df["start"],
          df["end"],
          df["text"],
          df["speaker_id"],
          df["ssml_gender"],
      )
  ]
  metadata_kwargs = {
      "script_with_timestamps": script_with_timestamps,
      "assigned_voice": df["assigned_voice"].tolist(),
  }
  if {"stability", "similarity_boost", "style", "use_speaker_boost"} <= set(
      df.columns
  ):
    metadata_kwargs["elevenlabs_text_to_speech_parameters"] = [
        {
            "stability": float(stability),
            "similarity_boost": float(similarity_boost),
            "style": float(style),
            "use_speaker_boost": bool(use_speaker_boost),
        }
        for stability, similarity_boost, style, use_speaker_boost in zip(
            df["stability"],
            df["similarity_boost"],
            df["style"],
            df["use_speaker_boost"],
        )
    ]
  elif {"pitch", "speed", "volume_gain_db"} <= set(df.columns):
    metadata_kwargs["google_text_to_speech_parameters"] = [
        {
            "pitch": float(pitch),
            "speed": float(speed),
            "volume_gain_db": float(volume_gain_db),
        }
        for pitch, speed, volume_gain_db in zip(
            df["pitch"], df["speed"], df["volume_gain_db"]
        )
    ]
  return ScriptMetadata(**metadata_kwargs)


def convert_utterance_metadata(
    utterance_metadata: pd.DataFrame,
) -> pd.DataFrame:
  """Converts specific columns in utterance metadata.

  Expected columns:
      Always present:
          - text: The original text of the utterance.
          - translated_text: The translated text of the utterance.
          - speaker_id: An identifier for the speaker.
          - ssml_gender: The gender specified in SSML for the speaker.
          - assigned_voice: The voice assigned to the speaker.
          - start: The start time of the utterance in seconds.
          - end: The end time of the utterance in seconds.
          - for_dubbing: Whether the utterance is for dubbing.
          - adjust_speed: Whether to adjust the speed of the utterance.

      Optional:
          Case 1:
              - pitch: The pitch adjustment for the utterance.
              - speed: The speed adjustment for the utterance.
              - volume_gain: The volume gain for the utterance.

          Case 2:
              - stability: A stability value for the utterance (e.g., for voice
              synthesis).
              - similarity_boost: A similarity boost value (e.g., for voice
              synthesis).
              - style: A style value (e.g., for voice synthesis).
              - use_speaker_boost: Whether to use speaker boost.

  Args:
    utterance_metadata: The input utterance metadata with the expected columns.

  Returns:
    The converted utterance metadata with the correct data types.
  """
  for col in _STRING_COLUMNS:
    if col in utterance_metadata.columns:
      utterance_metadata[col] = utterance_metadata[col].astype(str)
  for col in _FLOAT_COLUMNS:
    if col in utterance_metadata.columns:
      utterance_metadata[col] = utterance_metadata[col].astype(float)
  for col in _BOOL_COLUMNS:
    if col in utterance_metadata.columns:
      utterance_metadata[col] = utterance_metadata[col].astype(bool)
  return utterance_metadata

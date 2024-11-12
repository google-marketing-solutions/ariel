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
import datetime
import os
import re
import time
from typing import Any, Final, Mapping, Sequence
from absl import logging
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
import gspread
from gspread_dataframe import set_with_dataframe
from IPython.display import clear_output
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
) -> str:
  """Copies the contents of the 'output' subdirectory in a Colab directory.

  to a new directory in Google Drive with the same name as the Colab directory.

  Args:
    colab_dir: The path to the Colab directory.
    google_drive_dir: The path to the Google Drive directory.

  Returns:
    The path to the Google Drive destination directory.
  """
  output_dir = os.path.join(colab_dir, "output")
  destination_dir = os.path.join(google_drive_dir, os.path.basename(colab_dir))
  tf.io.gfile.makedirs(destination_dir)
  for filename in os.listdir(output_dir):
    source_path = os.path.join(output_dir, filename)
    destination_path = os.path.join(destination_dir, filename)
    if not tf.io.gfile.exists(destination_path):
      tf.io.gfile.copy(source_path, destination_path, overwrite=True)
  return destination_dir


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
  df = pd.DataFrame(rows[1:], columns=rows[0])
  df.columns = df.columns.str.replace(r"\s+", "", regex=True)
  return df


@dataclasses.dataclass
class ScriptMetadata:
  """Instance with script metadata.

  Attributes:
      script_with_timestamps: A sequence of dictionaries, where each dictionary
        represents a speech segment and contains the keys "start", "end",
        "text", "speaker_id", "ssml_gender", "assigned_voice" and "adjust_speed"
      google_text_to_speech_parameters: A sequence of mappings with Google
        Text-to-Speech parameters ("pitch", "speed", "volume_gain_db"), or None
        if not applicable.
      elevenlabs_text_to_speech_parameters: A sequence of mappings with
        ElevenLabs Text-to-Speech parameters ("stability", "similarity_boost",
        "style", "use_speaker_boost"), or None if not applicable.
  """

  script_with_timestamps: Sequence[Mapping[str, float | str]]
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
          "start": start,
          "end": end,
          "text": text,
          "speaker_id": speaker_id,
          "ssml_gender": ssml_gender,
          "assigned_voice": assigned_voice,
          "adjust_speed": adjust_speed,
      }
      for start, end, text, speaker_id, ssml_gender, assigned_voice, adjust_speed in zip(
          df["start"],
          df["end"],
          df["text"],
          df["speaker_id"],
          df["ssml_gender"],
          df["assigned_voice"],
          df["adjust_speed"],
      )
  ]
  metadata_kwargs = {
      "script_with_timestamps": script_with_timestamps,
  }
  if {"stability", "similarity_boost", "style", "use_speaker_boost"} <= set(
      df.columns
  ):
    metadata_kwargs["elevenlabs_text_to_speech_parameters"] = [
        {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
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
            "pitch": pitch,
            "speed": speed,
            "volume_gain_db": volume_gain_db,
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
      utterance_metadata[col] = utterance_metadata[col].str.lower() == "true"
  return utterance_metadata


def get_folder_id_by_path(path: str) -> str:
  """Returns the Google Drive folder ID for a specified path.

  Args:
    path: The full path of the folder in Google Drive, starting from
    '/content/drive/My Drive/...'. For example: '/content/drive/My
    Drive/parent_folder/sub_folder'.

  Raises:
    FileNotFoundError: If any part of the specified path does not exist in
    Google Drive.
  """
  path_parts = path.split("/")[4:]
  folder_id = "root"
  creds, _ = default()
  service = build("drive", "v3", credentials=creds)
  for part in path_parts:
    query = (
        f"'{folder_id}' in parents and name = '{part}' and mimeType ="
        " 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get("files", [])
    if not items:
      raise FileNotFoundError(f"Folder '{part}' not found in the current path.")
    folder_id = items[0]["id"]
  return folder_id


def save_dataframe_to_gdrive(
    *, dataframe: str, google_drive_directory_id: str, sheet_name: str
) -> None:
  """Saves a DataFrame as a Google Sheet in a specified folder.

  Args:
    dataframe: The DataFrame to be saved as a Google Sheet.
    google_drive_directory_id: The ID of the Google Drive folder where the
      Google Sheet should be saved.
    sheet_name: The desired name of the Google Sheet.
  """
  creds, _ = default()
  service = build("drive", "v3", credentials=creds)
  client = gspread.authorize(creds)
  file_metadata = {
      "name": sheet_name,
      "mimeType": "application/vnd.google-apps.spreadsheet",
      "parents": [google_drive_directory_id],
  }
  file = service.files().create(body=file_metadata, fields="id").execute()
  spreadsheet_id = file.get("id")
  spreadsheet = client.open_by_key(spreadsheet_id)
  worksheet = spreadsheet.get_worksheet(0)
  set_with_dataframe(worksheet, dataframe)


def convert_utterance_metadata_to_google_sheets(
    *,
    input_file_google_drive_path: str,
    output_directory: str,
    wait: bool = True,
    wait_time: int = 10,
    remove_json: bool = True,
) -> None:
  """Converts utterance metadata from JSON files to Google Sheets.

  Args:
    input_file_google_drive_path: The Google Drive path of the input directory
      containing JSON files.
    output_directory: The output directory in Google Drive where the Google
      Sheets will be saved.
    wait: Whether to wait for JSON files to appear in Google Drive.
    wait_time: How long to wait for all the files to appear on Google Drive.
    remove_json: Whether to remove the original JSON files after conversion.
      Defaults to True.
  """
  google_drive_directory = os.path.join(
      os.path.split(input_file_google_drive_path)[0],
      os.path.split(output_directory)[1],
  )
  if wait:
    logging.info(
        f"Waiting {wait_time}s for all the files to appear on Google Drive."
    )
    time.sleep(wait_time)
  google_drive_directory_id = get_folder_id_by_path(google_drive_directory)
  json_files = [
      file
      for file in tf.io.gfile.listdir(google_drive_directory)
      if file.endswith(".json")
  ]
  if not json_files:
    logging.info(
        f"No JSON files found in the directory: {google_drive_directory}"
    )
    return
  json_paths = [
      os.path.join(google_drive_directory, file) for file in json_files
  ]
  spreadsheet_names = [os.path.splitext(file)[0] for file in json_files]
  for json_path, spreadsheet_name in zip(json_paths, spreadsheet_names):
    utterance_metadata_df = pd.read_json(json_path)
    save_dataframe_to_gdrive(
        dataframe=utterance_metadata_df,
        google_drive_directory_id=google_drive_directory_id,
        sheet_name=spreadsheet_name,
    )
    if remove_json:
      tf.io.gfile.remove(json_path)


@dataclasses.dataclass
class ColabPaths:
  """Instance with Colab file paths.

  Attributes:
    input_file_google_drive_path: The Google Drive path of the input file.
    input_file_colab_path: The path to the input file in Colab after copying
      from Google Drive.
    vocals_file_colab_path: The path to the vocals file in Colab after copying
      from Google Drive, or None if not provided.
    background_file_colab_path: The path to the background file in Colab after
      copying from Google Drive, or None if not provided.
  """

  input_file_google_drive_path: str
  input_file_colab_path: str | None
  vocals_file_colab_path: str | None = None
  background_file_colab_path: str | None = None


def generate_colab_file_paths(
    *,
    video_google_drive_link: str,
    vocals_google_drive_link: str | None = None,
    background_google_drive_link: str | None = None,
) -> ColabPaths:
  """Generates Colab file paths for the specified Google Drive links and copies files to Colab.

  Args:
      video_google_drive_link: The Google Drive link to the main input file.
      vocals_google_drive_link: The Google Drive link to the vocals file, if
        available. Defaults to None.
      background_google_drive_link: The Google Drive link to the background
        file, if available. Defaults to None.

  Returns:
      ColabPaths: An instance of ColabPaths containing the Google Drive and
      Colab paths for each file.
  """
  input_file_google_drive_path = get_file_path_from_sharable_link(
      video_google_drive_link
  )
  input_file_colab_path = copy_file_to_colab(
      source_file_path=input_file_google_drive_path
  )
  vocals_file_colab_path = None
  if vocals_google_drive_link:
    vocals_file_google_drive_path = get_file_path_from_sharable_link(
        vocals_google_drive_link
    )
    vocals_file_colab_path = copy_file_to_colab(
        source_file_path=vocals_file_google_drive_path
    )
  background_file_colab_path = None
  if background_google_drive_link:
    background_file_google_drive_path = get_file_path_from_sharable_link(
        background_google_drive_link
    )
    background_file_colab_path = copy_file_to_colab(
        source_file_path=background_file_google_drive_path
    )
  return ColabPaths(
      input_file_google_drive_path=input_file_google_drive_path,
      input_file_colab_path=input_file_colab_path,
      vocals_file_colab_path=vocals_file_colab_path,
      background_file_colab_path=background_file_colab_path,
  )


def _generate_default_output_folder(advertiser_name: str) -> str:
  """Generates a default output folder path.

  The function removes any non-alphabet characters from the advertiser's name,
  converts it to lowercase,
  and appends a timestamp (in the format YYYYMMDDHHMMSSffffff) to ensure the
  folder name is unique.

  Args:
      advertiser_name: The name of the advertiser used to create the folder
        name.

  Returns:
    A string representing the full path of the output folder, starting with
    '/content' and ending
    with the formatted advertiser name and timestamp.
  """
  formatted_advertiser_name = re.sub(r"[^a-zA-Z]", "", advertiser_name).lower()
  now = datetime.datetime.now()
  return os.path.join(
      "/content",
      "dubbing_" + formatted_advertiser_name + now.strftime("%Y%m%d%H%M%S%f"),
  )


def setup_output_folder(
    *,
    advertiser_name: str,
    input_file_google_drive_path: str,
    output_folder: str | None = None,
    metadata_google_drive_link: str | None = None,
) -> str:
  """Returns output folder path, either based on user input or generated automatically.

  If `output_folder` is not provided, a default folder name will be generated
  using the advertiser's
  name and a timestamp. If a folder with the specified name already exists in
  Google Drive, the user
  will be prompted to overwrite it or enter a new name. If the user leaves the
  input blank, a default
  folder name will be created automatically.

  Args:
      advertiser_name: The name of the advertiser, used for generating a default
        folder name.
      input_file_google_drive_path: The path of the input file in Google Drive.
      output_folder: An optional specified output folder name. Defaults to None.
      metadata_google_drive_link: A link to a utterance metadata Google Sheet.

  Returns:
      The path of the created output folder.
  """
  if not output_folder:
    output_folder = _generate_default_output_folder(advertiser_name)
  google_drive_output_path = os.path.join(
      os.path.split(input_file_google_drive_path)[0], output_folder
  )
  while tf.io.gfile.exists(google_drive_output_path):
    user_response = input(
        f"The folder '{google_drive_output_path}' already exists in your Google"
        " Drive. Do you want to overwrite it? (yes/no): "
    )
    if user_response.lower() == "yes":
      break
    else:
      output_folder = input(
          "Please enter a new output folder name, or leave it empty to"
          " auto-generate one: "
      ).strip()
      if not output_folder:
        output_folder = _generate_default_output_folder(advertiser_name)
      google_drive_output_path = os.path.join(
          os.path.split(input_file_google_drive_path)[0], output_folder
      )
  output_folder = os.path.join("/content", output_folder)
  if metadata_google_drive_link:
    logging.info(
        "You're using utterance metadata from Google Sheets. The Colab output"
        " directory will be cleaned if it exists already."
    )
    try:
      tf.io.gfile.rmtree(output_folder)
    except tf.errors.NotFoundError:
      pass
  tf.io.gfile.makedirs(output_folder)
  return output_folder


def process_dubbing(
    *,
    dubber: Any,
    input_file_google_drive_path: str,
    output_folder: str,
    script_google_drive_link: str | None = None,
    metadata_google_drive_link: str | None = None,
) -> None:
  """Processes the dubbing workflow based on provided Google Drive links for script or metadata.

  This function authenticates the user, retrieves data from Google Sheets, and
  performs the dubbing
  based on the type of metadata provided. If a script link is provided, it
  processes it with voice
  metadata; if only a metadata link is provided, it uses utterance metadata. If
  neither is provided,
  it defaults to a basic dubbing process. Finally, it copies the output to
  Google Drive.

  Args:
      dubber: The dubbing object responsible for dubbing functionality.
      input_file_google_drive_path: The path of the input file in Google Drive.
      output_folder: The output folder in Google Drive where results will be
        saved.
      script_google_drive_link: Google Drive link to the script with voice
        metadata.
      metadata_google_drive_link: Google Drive link to the utterance metadata.
  """
  if script_google_drive_link:
    script_with_voice_metadata_df = convert_utterance_metadata(
        get_google_sheet_as_dataframe(script_google_drive_link)
    )
    script_with_voice_metadata = create_script_metadata_from_dataframe(
        script_with_voice_metadata_df
    )
    _ = dubber.dub_ad_from_script(
        script_with_timestamps=script_with_voice_metadata.script_with_timestamps,
        google_text_to_speech_parameters=script_with_voice_metadata.google_text_to_speech_parameters,
        elevenlabs_text_to_speech_parameters=script_with_voice_metadata.elevenlabs_text_to_speech_parameters,
    )
  elif metadata_google_drive_link:
    utterance_metadata_df = get_google_sheet_as_dataframe(
        metadata_google_drive_link
    )
    converted_utterance_metadata_df = convert_utterance_metadata(
        utterance_metadata_df
    )
    utterance_metadata = converted_utterance_metadata_df.to_dict("records")
    _ = dubber.dub_ad_with_utterance_metadata(
        utterance_metadata=utterance_metadata
    )
  else:
    _ = dubber.dub_ad()
  clear_output(wait=True)
  print(
      "The dubbing process is finished. Copying files to your Google Drive."
      " Please wait..."
  )
  destination_dir = copy_output_to_google_drive(
      colab_dir=output_folder,
      google_drive_dir=os.path.dirname(input_file_google_drive_path),
  )
  convert_utterance_metadata_to_google_sheets(
      input_file_google_drive_path=input_file_google_drive_path,
      output_directory=output_folder,
  )
  print(f"The output is saved in: {destination_dir}")

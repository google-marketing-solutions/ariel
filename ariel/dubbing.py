"""A dubbing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import dataclasses
import json
import os
import shutil
from typing import Final, Mapping, Sequence
from absl import logging


_ACCEPTED_VIDEO_FORMATS: Final[tuple[str, ...]] = (".mp4",)
_ACCEPTED_AUDIO_FORMATS: Final[tuple[str, ...]] = (".wav", ".mp3", ".flac")
_UTTERNACE_METADATA_FILE_NAME: Final[str] = "utterance_metadata.json"


def is_video(*, input_file: str) -> bool:
  """Checks if a given file is a video (MP4) or audio (WAV, MP3, FLAC).

  Args:
      input_file: The path to the input file.

  Returns:
      True if it's an MP4 video, False otherwise.

  Raises:
      ValueError: If the file format is unsupported.
  """

  _, file_extension = os.path.splitext(input_file)
  file_extension = file_extension.lower()

  if file_extension in _ACCEPTED_VIDEO_FORMATS:
    return True
  elif file_extension in _ACCEPTED_AUDIO_FORMATS:
    return False
  else:
    raise ValueError(f"Unsupported file format: {file_extension}")


def save_utterance_metadata(
    *,
    utterance_metadata: Sequence[Mapping[str, float | str]],
    output_directory: str,
) -> str:
  """Saves a Python dictionary to a JSON file.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "start", "end", "chunk_path", "translated_text",
        "speaker_id", "ssml_gender" and "dubbed_path".
      output_directory: The directory where utterance metadata should be saved.

  Returns:
    A path to the saved uttterance metadata.
  """
  utterance_metadata_file = os.path.join(
      output_directory, _UTTERNACE_METADATA_FILE_NAME
  )
  try:
    with open(utterance_metadata_file, "w") as json_file:
      json.dump(utterance_metadata, json_file)
    logging.info(
        f"Utterance metadata saved successfully to '{utterance_metadata_file}'"
    )
  except Exception as e:
    logging.warning(f"Error saving utterance metadata: {e}")
  return utterance_metadata_file


def clean_directory(*, directory: str, keep_files: Sequence[str]) -> None:
  """Removes all files and directories from a directory, except for those listed in keep_files."""
  for filename in os.listdir(directory):
    file_path = os.path.join(directory, filename)
    if filename in keep_files:
      continue
    if os.path.isfile(file_path):
      os.remove(file_path)
    elif os.path.isdir(file_path):
      shutil.rmtree(file_path)


def read_system_settings(input_string: str) -> str:
  """Processes an input string.

  - If it's a .txt file, reads and returns the content. - If it has another
  extension, raises a ValueError. - If it's just a string, returns it as is.

  Args:
      input_string: The string to process.

  Returns:
      The content of the .txt file or the input string.

  Raises:
      ValueError: If the input has an unsupported extension.
      TypeError: If the input file doesn't exist.
      FileNotFoundError: If the .txt file doesn't exist.
  """
  if not isinstance(input_string, str):
    raise TypeError("Input must be a string")

  _, extension = os.path.splitext(input_string)

  if extension == ".txt":
    try:
      with open(input_string, "r") as file:
        return file.read()
    except FileNotFoundError:
      raise FileNotFoundError(f"File not found: {input_string}")
  elif extension:
    raise ValueError(f"Unsupported file type: {extension}")
  else:
    return input_string


@dataclasses.dataclass
class PreprocessingArtifacts:
  """Instance with preprocessing outputs.

  Attributes:
      video_file: A path to a video ad with no audio.
      audio_file: A path to an audio track form the ad.
      audio_background_file: A path to and audio track from the ad with removed
        vocals.
      utterance_metadata: The sequence of utterance metadata dictionaries. Each
        dictionary represents a chunk of audio and contains the "path", "start",
        "stop" keys.
  """

  video_file: str
  audio_file: str
  audio_background_file: str
  utterance_metadata: Sequence[Mapping[str, str | float]]

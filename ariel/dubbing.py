"""An dubbing processing module of the Google EMEA gTech Ads Data Science Ariel."""

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
    utterance_metadata: Sequence[Mapping[str, float | str]],
    output_directory: str,
) -> None:
  """Saves a Python dictionary to a JSON file.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "start", "end", "chunk_path", "translated_text",
        "speaker_id", "ssml_gender" and "dubbed_path".
      output_directory: The directory where utterance metadata should be saved.
  """
  file_path = os.path.join(output_directory, _UTTERNACE_METADATA_FILE_NAME)
  try:
    with open(file_path, "w") as json_file:
      json.dump(utterance_metadata, json_file)
    logging.info(f"Utterance metadata saved successfully to '{file_path}'")
  except Exception as e:
    logging.error(f"Error saving utterance metadata: {e}")


def clean_directory(directory: str, keep_files: Sequence[str]) -> None:
  """Removes all files and directories from a directory, except for those listed in keep_files."""
  for filename in os.listdir(directory):
    file_path = os.path.join(directory, filename)
    if filename in keep_files:
      continue
    if os.path.isfile(file_path):
      os.remove(file_path)
    elif os.path.isdir(file_path):
      shutil.rmtree(file_path)

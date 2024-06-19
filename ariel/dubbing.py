"""An dubbing processing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import os
from typing import Final

_ACCEPTED_VIDEO_FORMATS: Final[tuple[str, ...]] = (".mp4",)
_ACCEPTED_AUDIO_FORMATS: Final[tuple[str, ...]] = (".wav", ".mp3", ".flac")


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
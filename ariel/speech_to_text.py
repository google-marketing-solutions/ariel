"""A speech-to-text module of Ariel package from the Google EMEA gTech Ads Data Science."""

import time
from typing import Final, Mapping, Sequence
from absl import logging
from faster_whisper import WhisperModel
import google.generativeai as genai
from google.generativeai.types import file_types
import torch

_DEFAULT_MODEL: Final[str] = "large-v3"
_DEVICE: Final[str] = "gpu" if torch.cuda.is_available() else "cpu"
_COMPUTE_TYPE: Final[str] = "float16" if _DEVICE == "gpu" else "int8"
_DEFAULT_TRANSCRIPTION_MODEL: Final[WhisperModel] = WhisperModel(
    model_size_or_path=_DEFAULT_MODEL,
    device=_DEVICE,
    compute_type=_COMPUTE_TYPE,
)
_PROCESSING: Final[str] = "PROCESSING"
_ACTIVE: Final[str] = "ACTIVE"
_SLEEP_TIME: Final[int] = 10


def transcribe(
    *,
    vocals_filepath: str,
    advertiser_name: str,
    original_language: str,
    model: WhisperModel = _DEFAULT_TRANSCRIPTION_MODEL,
) -> str:
  """Transcribes an audio.

  Args:
      vocals_filepath: The path to the audio file ot be transcribed.
      advertiser_name: The name of the advertiser to use as a hotword.
      original_language: The original language of the audio. It's either ISO
        639-1 or ISO 3166-1 alpha-2 country code.
      model: The pre-initialized transcription model.

  Returns:
      The transcribed text.
  """
  segments, _ = model.transcribe(
      vocals_filepath,
      language=original_language.split("-")[0],
      hotwords=advertiser_name,
  )
  return " ".join(segment.text for segment in segments)


def transcribe_audio_chunks(
    *,
    chunk_data_list: Sequence[Mapping[str, float | str]],
    advertiser_name: str,
    original_language: str,
    model: WhisperModel = _DEFAULT_TRANSCRIPTION_MODEL,
) -> Sequence[Mapping[str, float | str]]:
  """Transcribes each audio chunk in the provided list and returns a new list with transcriptions added.

  Args:
      chunk_data_list: A sequence of mappings, each containing information about
        a single audio chunk, including the 'path' key.
      advertiser_name: The name of the advertiser.
      original_language: The original language of the audio.
      model: The pre-initialized transcription model.

  Returns:
      A new sequence of mappings, where each mapping is a copy of the original
      with an added 'text' key containing the transcription.
  """
  transcribed_chunk_data = []
  for item in chunk_data_list:
    new_item = item.copy()
    new_item["text"] = transcribe(
        vocals_filepath=item["path"],
        advertiser_name=advertiser_name,
        original_language=original_language,
        model=model,
    )
    transcribed_chunk_data.append(new_item)
  return transcribed_chunk_data


def upload_to_gemini(video_path: str) -> file_types.File:
  """Uploads an MP4 video file to Gemini and logs the URI.

  Args:
      video_path: The path to the MP4 video file to upload.

  Returns:
      The uploaded file object.
  """
  file = genai.upload_file(video_path, mime_type="video/mp4")
  logging.info(f"Uploaded file '{file.display_name}' as: {file.uri}")
  return file


class FileProcessingError(Exception):
  pass


def wait_for_file_active(*, file: file_types.File) -> None:
  """Waits for a single file to reach an 'ACTIVE' state.

  Args:
      file: A file object to wait for.

  Raises:
      Exception: If the file fails to reach the 'ACTIVE' state.
  """
  logging.info("Processing the video file for Gemini.")
  while file.state.name == _PROCESSING:
    time.sleep(_SLEEP_TIME)
    file = genai.get_file(file.name)
  if file.state.name != _ACTIVE:
    raise FileProcessingError(f"File {file.name} failed to process.")
  logging.info(
      "The video file is ready to be used by Gemini for speaker diarization."
  )


def process_speaker_diarization_response(
    *, response: str
) -> list[tuple[str, str]]:
  """Processes a speaker diarization response string and returns a list of speaker-timestamp tuples.

  Args:
      response: The speaker diarization response string.

  Returns:
      A list of tuples, where each tuple contains a speaker and their
      corresponding timestamp.
  """

  input_list = [
      item.strip()
      for item in response.replace("(", "")
      .replace(")", "")
      .replace("\n", "")
      .split(",")
  ]
  tuples_list = [
      (speaker, timestamp)
      for speaker, timestamp in zip(input_list[::2], input_list[1::2])
      if speaker and timestamp
  ]

  return tuples_list

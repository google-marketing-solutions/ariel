"""A speech-to-text module of Ariel package from the Google EMEA gTech Ads Data Science."""

import time
from typing import Final, Mapping, Sequence
from absl import logging
from faster_whisper import WhisperModel
import google.generativeai as genai
from google.generativeai.types import file_types
from google.generativeai.types import HarmBlockThreshold, HarmCategory
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
_DIARIZATION_PROMPT: Final[str] = (
    "You got the video attached. The transcript is: {}. The number of speakers"
    " in the video is: {}. You must provide only {} annotations, each for one"
    " dictionary in the transcript. And the specific instructions are: {}."
)


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
    utterance_metadata: Sequence[Mapping[str, float | str]],
    advertiser_name: str,
    original_language: str,
    model: WhisperModel = _DEFAULT_TRANSCRIPTION_MODEL,
) -> Sequence[Mapping[str, float | str]]:
  """Transcribes each audio chunk in the provided list and returns a new list with transcriptions added.

  Args:
      utterance_metadata: A sequence of mappings, each containing information
        about a single audio chunk, including the 'path' key.
      advertiser_name: The name of the advertiser.
      original_language: The original language of the audio.
      model: The pre-initialized transcription model.

  Returns:
      A new sequence of mappings, where each mapping is a copy of the original
      with an added 'text' key containing the transcription.
  """
  updated_utterance_metadata = []
  for item in utterance_metadata:
    new_item = item.copy()
    new_item["text"] = transcribe(
        vocals_filepath=item["path"],
        advertiser_name=advertiser_name,
        original_language=original_language,
        model=model,
    )
    updated_utterance_metadata.append(new_item)
  return updated_utterance_metadata


def upload_to_gemini(*, video_path: str) -> file_types.File:
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


def diarize_speakers(
    *,
    video_file: str,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    number_of_speakers: int,
    model: genai.GenerativeModel,
    diarization_instructions: str | None = None,
) -> Sequence[tuple[str, str]]:
  """Diarizes speakers in a video using a Gemini generative model.

  Args:
      video_file: The path to the video file.
      utterance_metadata: The transcript of the video, represented as a sequence
        of mappings with keys "start", "stop", and "text".
      number_of_speakers: The number of speakers in the video.
      model: The pre-configured Gemini GenerativeModel instance.
      diarization_instructions: The specific instructions for diarization.

  Returns:
      A sequence of tuples representing speaker annotations, where each tuple
      contains the speaker name and the start time of the speaker
      segment.
  """
  file = upload_to_gemini(video_file=video_file)
  wait_for_file_active(file=file)
  chat_session = model.start_chat(history=[{"role": "user", "parts": file}])
  prompt = _DIARIZATION_PROMPT.format(
      utterance_metadata,
      number_of_speakers,
      len(utterance_metadata),
      diarization_instructions or "",
  )
  response = chat_session.send_message(prompt)
  chat_session.rewind()
  return process_speaker_diarization_response(response=response.text)


def add_speaker_info(
    utterance_metadata: Sequence[Mapping[str, str | float]],
    speaker_info: Sequence[tuple[str, str]],
) -> Sequence[Mapping[str, str | float]]:
  """Adds speaker information to each utterance metadata.

  Args:
      utterance_metadata: The sequence of utterance metadata dictionaries. Each
        dictionary represents a chunk of audio and contains the "text", "start",
        "stop" keys.
      speaker_info: The sequence of tuples containing (speaker_id, gender)
        information. The order of tuples in this list should correspond to the
        order of utterance_metadata.

  Returns:
      The sequence of updated utterance metadata dictionaries with speaker
      information added.
      Each dictionary will include the "speaker_id" and "ssml_gender" keys.

  Raises:
      ValueError: If the lengths of "utterance_metadata" and "speaker_info" do
      not match.
  """

  if len(utterance_metadata) != len(speaker_info):
    raise ValueError(
        "The length of 'utterance_metadata' and 'speaker_info' must be the"
        " same."
    )

  return [
      {
          "text": chunk["text"],
          "start": chunk["start"],
          "stop": chunk["stop"],
          "speaker_id": speaker_id,
          "ssml_gender": gender,
      }
      for chunk, (speaker_id, gender) in zip(utterance_metadata, speaker_info)
  ]

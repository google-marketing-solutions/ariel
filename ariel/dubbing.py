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

"""A dubbing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import dataclasses
import datetime
import functools
import importlib.resources
import json
import os
import re
import readline
import shutil
import sys
import time
from typing import Final, Mapping, Set, Sequence
from absl import logging
from ariel import audio_processing
from ariel import colab_utils
from ariel import speech_to_text
from ariel import text_to_speech
from ariel import translation
from ariel import video_processing
from elevenlabs.client import ElevenLabs
from elevenlabs.core import ApiError
from faster_whisper import WhisperModel
from google.api_core.exceptions import ServiceUnavailable
from google.cloud import texttospeech
from IPython.display import Audio
from IPython.display import clear_output
from IPython.display import display
from IPython.display import HTML
from IPython.display import Video
from pyannote.audio import Pipeline
import tensorflow as tf
import torch
from tqdm import tqdm
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.generative_models import HarmBlockThreshold
from vertexai.generative_models import HarmCategory

_ACCEPTED_VIDEO_FORMATS: Final[tuple[str, ...]] = (".mp4",)
_ACCEPTED_AUDIO_FORMATS: Final[tuple[str, ...]] = (".wav", ".mp3", ".flac")
_UTTERNACE_METADATA_FILE_NAME: Final[str] = "utterance_metadata"
_EXPECTED_HUGGING_FACE_ENVIRONMENTAL_VARIABLE_NAME: Final[str] = (
    "HUGGING_FACE_TOKEN"
)
_EXPECTED_ELEVENLABS_ENVIRONMENTAL_VARIABLE_NAME: Final[str] = (
    "ELEVENLABS_TOKEN"
)
_DEFAULT_PYANNOTE_MODEL: Final[str] = "pyannote/speaker-diarization-3.1"
_DEFAULT_ELEVENLABS_MODEL: Final[str] = "eleven_multilingual_v2"
_DEFAULT_TRANSCRIPTION_MODEL: Final[str] = "large-v3"
_DEFAULT_GEMINI_MODEL: Final[str] = "gemini-1.5-flash"
_DEFAULT_GEMINI_TEMPERATURE: Final[float] = 1.0
_DEFAULT_GEMINI_TOP_P: Final[float] = 0.95
_DEFAULT_GEMINI_TOP_K: Final[int] = 40
_DEFAULT_GEMINI_MAX_OUTPUT_TOKENS: Final[int] = 8192
_DEFAULT_GEMINI_RESPONSE_MIME_TYPE: Final[str] = "text/plain"
_DEFAULT_GEMINI_SAFETY_SETTINGS: Final[
    Mapping[HarmCategory, HarmBlockThreshold]
] = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: (
        HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    HarmCategory.HARM_CATEGORY_HARASSMENT: (
        HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: (
        HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: (
        HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
}
_DEFAULT_DIARIZATION_SYSTEM_SETTINGS: Final[str] = "diarization.txt"
_DEFAULT_TRANSLATION_SYSTEM_SETTINGS: Final[str] = "translation.txt"
_DEFAULT_EDIT_TRANSLATION_SYSTEM_SETTINGS: Final[str] = "edit_translation.txt"
_NUMBER_OF_STEPS: Final[int] = 6
_NUMBER_OF_STEPS_GENERATE_UTTERANCE_METADATA: Final[int] = 4
_NUMBER_OF_STEPS_DUB_AD_WITH_UTTERANCE_METADATA: Final[int] = 3
_NUMBER_OF_STEPS_DUB_AD_WITH_DIFFERENT_LANGUAGE: Final[int] = 4
_NUMBER_OF_STEPS_DUB_AD_FROM_SCRIPT: Final[int] = 3
_MAX_GEMINI_RETRIES: Final[int] = 5
_EDIT_TRANSLATION_PROMPT: Final[str] = (
    "You were hired by a company called: '{}'. The received script was: '{}'."
    " You translated it as: '{}'. The target language was: '{}'. The company"
    " asks you to modify this translation: '{}'"
)
_REQUIRED_KEYS: Final[Set[str]] = {
    "text",
    "start",
    "end",
    "speaker_id",
    "ssml_gender",
    "assigned_voice",
    "adjust_speed",
}
_REQUIRED_GOOGLE_TTS_PARAMETERS: Final[set] = {
    "pitch",
    "speed",
    "volume_gain_db",
}
_REQUIRED_ELEVENLABS_PARAMETERS: Final[set] = {
    "stability",
    "similarity_boost",
    "style",
    "use_speaker_boost",
}
_OUTPUT: Final[str] = "output"
_ALLOWED_BULK_EDIT_KEYS: Sequence[str] = (
    "for_dubbing",
    "speaker_id",
    "ssml_gender",
    "stability",
    "similarity_boost",
    "style",
    "use_speaker_boost",
    "pitch",
    "speed",
    "volume_gain_db",
    "adjust_speed",
)
_FLOAT_KEYS: Final[str] = (
    "start",
    "end",
    "stability",
    "similarity_boost",
    "style",
    "pitch",
    "speed",
    "volume_gain_db",
)
_BOOLEAN_KEYS: Final[str] = ("for_dubbing", "use_speaker_boost", "adjust_speed")
_LOCKED_KEYS: Final[str] = ("path", "dubbed_path", "vocals_path")
_AVAILABLE_LANGUAGES_PROMPT: Final[str] = """
                Arabic - ar-SA, Arabic - ar-EG, Bengali - bn-BD, Bengali - bn-IN, Bulgarian - bg-BG,
                Chinese (Simplified) - zh-CN, Chinese (Traditional) - zh-TW, Croatian - hr-HR, Czech - cs-CZ,
                Danish - da-DK, Dutch - nl-NL, English - en-US, English - en-GB, English - en-CA, English - en-AU,
                Estonian - et-EE, Finnish - fi-FI, French - fr-FR, French - fr-CA, German - de-DE, Greek - el-GR,
                Gujarati - gu-IN, Hebrew - he-IL, Hindi - hi-IN, Hungarian - hu-HU, Indonesian - id-ID, Italian - it-IT,
                Japanese - ja-JP, Kannada - kn-IN, Korean - ko-KR, Latvian - lv-LV, Lithuanian - lt-LT, Malayalam - ml-IN,
                Marathi - mr-IN, Norwegian - nb-NO, Norwegian - nn-NO, Polish - pl-PL, Portuguese - pt-PT, Portuguese - pt-BR,
                Romanian - ro-RO, Russian - ru-RU, Serbian - sr-RS, Slovak - sk-SK, Slovenian - sl-SI, Spanish - es-ES,
                Spanish - es-MX, Swahili - sw-KE, Swedish - sv-SE, Tamil - ta-IN, Tamil - ta-LK, Telugu - te-IN,
                Thai - th-TH, Turkish - tr-TR, Ukrainian - uk-UA, Vietnamese - vi-VN
                """
_SPECIAL_KEYS: Final[Sequence[str]] = (
    "speaker_id",
    "ssml_gender",
    "assigned_voice",
)


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


def read_system_settings(system_instructions: str) -> str:
  """Reads a .txt file with system instructions from the package.

  - If it's just a string, returns it as is.
  - If it's a .txt file, it assumes you use the defaut package system settings,
  reads them and returns the content.
  - If it has another extension, raises a ValueError.

  Args:
      system_instructions: The string to process.

  Returns:
      The content of the .txt file or the input string.

  Raises:
      ValueError: If the input has an unsupported extension.
      TypeError: If the input file doesn't exist.
      FileNotFoundError: If the .txt file doesn't exist.
  """
  _, extension = os.path.splitext(system_instructions)
  if extension == ".txt":
    try:
      with importlib.resources.path(
          "ariel", "system_settings"
      ) as assets_directory:
        file_path = os.path.join(assets_directory, system_instructions)
        with tf.io.gfile.GFile(file_path, "r") as file:
          result = []
          for line in file:
            if not line.lstrip().startswith("#"):
              result.append(line)
          return "".join(result)
    except Exception:
      raise ValueError(
          "You specified a .txt file that's not part of the Ariel package."
      )
  elif extension:
    raise ValueError(f"Unsupported file type: {extension}")
  else:
    return system_instructions


def create_output_directories(output_directory: str) -> None:
  """Creates the output directory and subdirectories.

  Args:
    output_directory: The path to the output directory.
  """
  if not tf.io.gfile.exists(output_directory):
    tf.io.gfile.makedirs(output_directory)
  subdirectories = [
      audio_processing.AUDIO_PROCESSING,
      video_processing.VIDEO_PROCESSING,
      text_to_speech.DUBBED_AUDIO_CHUNKS,
      _OUTPUT,
  ]
  for subdir in subdirectories:
    subdir_path = tf.io.gfile.join(output_directory, subdir)
    if not tf.io.gfile.exists(subdir_path):
      tf.io.gfile.makedirs(subdir_path)


@dataclasses.dataclass
class PreprocessingArtifacts:
  """Instance with preprocessing outputs.

  Attributes:
      video_file: A path to a video ad with no audio.
      audio_file: A path to an audio track from the ad.
      audio_vocals_file: A path to an audio track with vocals only.
      audio_background_file: A path to and audio track from the ad with removed
        vocals.
  """

  video_file: str | None
  audio_file: str
  audio_vocals_file: str | None = None
  audio_background_file: str | None = None


@dataclasses.dataclass
class PostprocessingArtifacts:
  """Instance with postprocessing outputs.

  Attributes:
      audio_file: A path to a dubbed audio file.
      video_file: A path to a dubbed video file. The video is optional.
      utterance_metadata: A JSON file with the complete speech chunk (utterance)
        metadata. It's useful when using the `dub_ad_with_utterance_metadata`
        method.
      subtitles: An SRT file with the subtitles.
  """

  audio_file: str
  video_file: str | None
  utterance_metadata: str | None = None
  subtitles: str | None = None


class PyAnnoteAccessError(Exception):
  """Error when establishing access to PyAnnore from Hugging Face."""

  pass


class GeminiAccessError(Exception):
  """Error when establishing access to Gemini."""

  pass


class GoogleTextToSpeechAccessError(Exception):
  """Error when establishing access to Google's Text-To-Speech API."""

  pass


class ElevenLabsAccessError(Exception):
  """Error when establishing access to ElevenLabs API."""

  pass


def _add_items_to_dictionaries(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    items: Sequence[str],
    key: str | None = None,
):
  """Adds items from a list to the utterance metadata.

  Args:
      utterance_metadata: The list of the source mappings.
      items: The list of items to add.
      key: The key to use for the new item in each dictionary if items are not
        dictionaries.

  Returns:
      An updated sequence with utterance metadata.

  Raises:
      ValueError: If the lengths of utterance metadata and items are not equal.
  """
  utterance_metadata_length = len(utterance_metadata)
  items_length = len(items)
  if utterance_metadata_length != items_length:
    raise ValueError(
        f"The number of dictionaries for the key '{key}' and items must be"
        f" equal. Received: {utterance_metadata_length} and"
        f" {items_length} respectively."
    )
  updated_utterance_metadata = []
  for dictionary, item in zip(utterance_metadata, items):
    dictionary_copy = dictionary.copy()
    if isinstance(item, dict):
      dictionary_copy.update(item)
    else:
      dictionary_copy[key] = item
    updated_utterance_metadata.append(dictionary_copy)
  return updated_utterance_metadata


def _verify_dictionary(
    *,
    dictionary_to_verify: Sequence[Mapping[str, str | float]],
    required_keys: set,
) -> None:
  """Verifies the completeness of a dictionary.

  Args:
      dictionary_to_verify: A sequence of dictionaries to verify.
      required_keys: A set of strings representing the mandatory keys expected
        in each parameter dictionary.

  Raises:
      KeyError: If any dictionary within `dictionary_to_verify` is missing one
      or more of the `required_keys`.
  """
  for dictionary in dictionary_to_verify:
    missing_keys = required_keys - set(dictionary.keys())
    if missing_keys:
      raise KeyError(
          f"Dictionary is missing keys: {missing_keys}. Problematic dictionary:"
          f" {dictionary}"
      )


def assemble_utterance_metadata_for_dubbing_from_script(
    *,
    script_with_timestamps: Sequence[Mapping[str, str | float]],
    use_elevenlabs: bool = False,
    google_text_to_speech_parameters: (
        Mapping[str, str | float] | Sequence[Mapping[str, str | float]] | None
    ) = {"pitch": -5.0, "speed": 1.0, "volume_gain_db": 16.0},
    elevenlabs_text_to_speech_parameters: (
        Mapping[str, str | float] | Sequence[Mapping[str, str | float]] | None
    ) = {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "use_speaker_boost": True,
    },
):
  """Assembles utterance metadata for dubbing based on a script with timestamps.

  This function takes a script with timestamps, voice assignments, and other
  parameters to create a structured metadata representation suitable for dubbing
  tasks. It validates the input data, adds necessary fields, and handles
  different text-to-speech (TTS) configurations.

  Args:
      script_with_timestamps: A sequence of dictionaries, each containing
        information about an utterance in the script.
      use_elevenlabs: If True, use ElevenLabs TTS parameters; otherwise, use
        Google TTS parameters.
      google_text_to_speech_parameters: A dictionary or list of dictionaries
        with Google TTS parameters (only used if `use_elevenlabs` is False).
      elevenlabs_text_to_speech_parameters: A dictionary or list of dictionaries
        with ElevenLabs TTS parameters (only used if `use_elevenlabs` is True).

  Returns:
      A sequence of dictionaries, each containing enriched metadata for an
      utterance.

  Raises:
      KeyError: If a dictionary in `script_with_timestamps` is missing "text",
      "start", or "end" keys.
      KeyError: If the specified TTS parameter dictionary is missing required
      keys.
  """
  _verify_dictionary(
      dictionary_to_verify=script_with_timestamps, required_keys=_REQUIRED_KEYS
  )
  number_of_utterances = len(script_with_timestamps)
  for_dubbing = [True] * number_of_utterances
  utterance_metadata_with_for_dubbing = _add_items_to_dictionaries(
      utterance_metadata=script_with_timestamps,
      items=for_dubbing,
      key="for_dubbing",
  )
  if use_elevenlabs:
    text_to_speech_parameters = elevenlabs_text_to_speech_parameters
    required_keys = _REQUIRED_ELEVENLABS_PARAMETERS
  else:
    text_to_speech_parameters = google_text_to_speech_parameters
    required_keys = _REQUIRED_GOOGLE_TTS_PARAMETERS
  if not isinstance(text_to_speech_parameters, list):
    text_to_speech_parameters = [
        text_to_speech_parameters
    ] * number_of_utterances
  _verify_dictionary(
      dictionary_to_verify=text_to_speech_parameters,
      required_keys=required_keys,
  )
  return _add_items_to_dictionaries(
      utterance_metadata=utterance_metadata_with_for_dubbing,
      items=text_to_speech_parameters,
  )


def get_safety_settings(
    level: str,
) -> Mapping[HarmCategory, HarmBlockThreshold]:
  """Returns safety settings based on the provided level.

  Args:
    level: The safety level. Can be 'Low', 'Medium', 'High', or 'None'.

  Returns:
    A dictionary mapping HarmCategory to HarmBlockThreshold.
  """

  if level == "Low":
    threshold = HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
  elif level == "Medium":
    threshold = HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
  elif level == "High":
    threshold = HarmBlockThreshold.BLOCK_ONLY_HIGH
  elif level == "None":
    threshold = HarmBlockThreshold.BLOCK_NONE
  else:
    raise ValueError(f"Invalid safety level: {level}")

  return {
      HarmCategory.HARM_CATEGORY_HATE_SPEECH: threshold,
      HarmCategory.HARM_CATEGORY_HARASSMENT: threshold,
      HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: threshold,
      HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: threshold,
  }


def rename_input_file(original_input_file: str) -> str:
  """Converts a filename to lowercase letters and numbers only, preserving the file extension.

  Args:
      original_filename: The filename to normalize.

  Returns:
      The normalized filename.
  """
  directory, filename = os.path.split(original_input_file)
  base_name, extension = os.path.splitext(filename)
  normalized_name = re.sub(r"[^a-z0-9]", "", base_name.lower())
  return os.path.join(directory, normalized_name + extension)


def overwrite_input_file(input_file: str, updated_input_file: str) -> None:
  """Renames a file in place to lowercase letters and numbers only, preserving the file extension.

  Args:
      input_file: The full path to the original input file.
      updated_input_file: The full path to the updated input file.

  Raises:
      FileNotFoundError: If the file to be overwritten is not found.
  """
  if not tf.io.gfile.exists(input_file):
    raise FileNotFoundError(f"File '{input_file}' not found.")
  tf.io.gfile.rename(input_file, updated_input_file, overwrite=True)


def check_directory_contents(output_directory: str) -> bool:
  """Checks if the output directory contains the expected files.

  Args:
    output_directory: The path to the directory to check.

  Returns:
    True if the directory contains the expected files, False otherwise.
  """

  audio_processing_path = os.path.join(
      output_directory, audio_processing.AUDIO_PROCESSING
  )
  video_processing_path = os.path.join(
      output_directory, video_processing.VIDEO_PROCESSING
  )
  if not tf.io.gfile.exists(audio_processing_path):
    logging.warning(
        f"'{audio_processing.AUDIO_PROCESSING}' directory not found in"
        f" '{output_directory}'"
    )
    return False
  audio_files = tf.io.gfile.listdir(audio_processing_path)
  has_vocals = "vocals.mp3" in audio_files
  has_no_vocals = "no_vocals.mp3" in audio_files
  has_chunks = any(
      tf.strings.regex_full_match(file, "chunk_.*\.mp3") for file in audio_files
  )
  if not (has_vocals and has_no_vocals and has_chunks):
    logging.warning(f"Missing required files in '{audio_processing_path}'")
    return False
  if not tf.io.gfile.exists(video_processing_path):
    logging.warning(
        f"'{video_processing.VIDEO_PROCESSING}' folder not found in"
        f" '{output_directory}'"
    )
    return False
  video_files = tf.io.gfile.listdir(video_processing_path)
  has_mp3 = any(
      tf.strings.regex_full_match(file, ".*\.mp3") for file in video_files
  )
  has_mp4 = any(
      tf.strings.regex_full_match(file, ".*\.mp4") for file in video_files
  )
  if not (has_mp3 and has_mp4):
    logging.warning(f"Missing required files in '{video_processing_path}'")
    return False
  return True


class Dubber:
  """A class to manage the entire ad dubbing process."""

  def __init__(
      self,
      *,
      input_file: str,
      output_directory: str,
      advertiser_name: str,
      original_language: str,
      target_language: str,
      gcp_project_id: str,
      gcp_region: str,
      number_of_speakers: int = 1,
      hugging_face_token: str | None = None,
      no_dubbing_phrases: Sequence[str] | None = None,
      diarization_instructions: str | None = None,
      translation_instructions: str | None = None,
      merge_utterances: bool = True,
      minimum_merge_threshold: float = 0.001,
      preferred_voices: Sequence[str] | None = None,
      assigned_voices_override: Mapping[str, str] | None = None,
      keep_voice_assignments: bool = True,
      adjust_speed: bool = False,
      vocals_volume_adjustment: float = 5.0,
      background_volume_adjustment: float = 0.0,
      voice_separation_rounds: int = 2,
      vocals_audio_file: str | None,
      background_audio_file: str | None,
      clean_up: bool = True,
      pyannote_model: str = _DEFAULT_PYANNOTE_MODEL,
      gemini_model_name: str = _DEFAULT_GEMINI_MODEL,
      temperature: float = _DEFAULT_GEMINI_TEMPERATURE,
      top_p: float = _DEFAULT_GEMINI_TOP_P,
      top_k: int = _DEFAULT_GEMINI_TOP_K,
      max_output_tokens: int = _DEFAULT_GEMINI_MAX_OUTPUT_TOKENS,
      response_mime_type: str = _DEFAULT_GEMINI_RESPONSE_MIME_TYPE,
      safety_settings: Mapping[
          HarmCategory, HarmBlockThreshold
      ] = _DEFAULT_GEMINI_SAFETY_SETTINGS,
      diarization_system_instructions: str = _DEFAULT_DIARIZATION_SYSTEM_SETTINGS,
      translation_system_instructions: str = _DEFAULT_TRANSLATION_SYSTEM_SETTINGS,
      use_elevenlabs: bool = False,
      elevenlabs_token: str | None = None,
      elevenlabs_clone_voices: bool = False,
      elevenlabs_model: str = _DEFAULT_ELEVENLABS_MODEL,
      elevenlabs_remove_cloned_voices: bool = False,
      number_of_steps: int = _NUMBER_OF_STEPS,
      with_verification: bool = True,
  ) -> None:
    """Initializes the Dubber class with various parameters for dubbing configuration.

    Args:
        input_file: The path to the input video or audio file.
        output_directory: The directory to save the dubbed output and
          intermediate files.
        advertiser_name: The name of the advertiser for context in
          transcription/translation.
        original_language: The language of the original audio. It must be ISO
          3166-1 alpha-2 country code, e.g. 'en-US'.
        target_language: The language to dub the ad into. It must be ISO 3166-1
          alpha-2 country code.
        gcp_project_id: Google Cloud Platform (GCP) project ID for Gemini model
          access and Google Text-To-Speech API (if this method is picked).
        gcp_region: GCP region to use when making API calls and where a
          temporary bucket will be created for Gemini to analyze the video /
          audio ad. The bucket with all its contents will be removed immediately
          afterwards.
        number_of_speakers: The exact number of speakers in the ad (including a
          lector if applicable).
        hugging_face_token: Hugging Face API token (can be set via
          'HUGGING_FACE_TOKEN' environment variable).
        no_dubbing_phrases: A sequence of strings representing the phrases that
          should not be dubbed. It is critical to provide these phrases in a
          format as close as possible to how they might appear in the utterance
          (e.g., include punctuation, capitalization if relevant).
        diarization_instructions: Specific instructions for speaker diarization.
        translation_instructions: Specific instructions for translation.
        merge_utterances: Whether to merge utterances when the the timestamps
          delta between them is below 'minimum_merge_threshold'.
        minimum_merge_threshold: Threshold for merging utterances in seconds.
        preferred_voices: Preferred voice names for text-to-speech. Use
          high-level names, e.g. 'Wavenet', 'Standard' etc. Do not use the full
          voice names, e.g. 'pl-PL-Wavenet-A' etc.
        assigned_voices_override: A mapping between unique speaker IDs and the
          full name of their assigned voices. E.g. {'speaker_01':
          'en-US-Casual-K'} or {'speaker_01': 'Charlie'}.
        keep_voice_assignments: Whether the voices assigned on the first run
          should be used again when utilizing the same class instance. It helps
          prevents repetitive voice assignment and cloning.
        adjust_speed: Whether to force speed up of utterances to match the
          duration of the utterances in the source language.
        vocals_volume_adjustment: By how much the vocals audio volume should be
          adjusted.
        background_volume_adjustment: By how much the background audio volume
          should be adjusted.
        voice_separation_rounds: The number of times the background audio file
          should be processed for voice detection and removal. It helps with the
          old voice artifacts being present in the dubbed ad.
        vocals_audio_file: An optional path to a file with the speaking part
          only. It will be used instead of AI splitting the entire audio track
          into vocals and background audio files. If this is provided then also
          `background_audio_file` is required. Must be an MP3 file.
        background_audio_file: An optional path to a file with the background
          part only. It will be used instead of AI splitting the entire audio
          track into vocals and background audio files. If this is provided then
          also `vocals_audio_file` is required. Must be an MP3 file.
        clean_up: Whether to delete intermediate files after dubbing. Only the
          final ouput and the utterance metadata will be kept.
        pyannote_model: Name of the PyAnnote diarization model.
        gemini_model_name: The name of the Gemini model to use.
        temperature: Controls randomness in generation.
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum number of tokens in the generated response.
        response_mime_type: Gemini output mime type.
        safety_settings: Gemini safety settings.
        diarization_system_instructions: System instructions for diarization.
        translation_system_instructions: System instructions for translation.
        use_elevenlabs: Whether to use ElevenLabs API for Text-To-Speech. If not
          Google's Text-To-Speech will be used.
        elevenlabs_token: ElevenLabs API token (can be set via
          'ELEVENLABS_TOKEN' environment variable).
        elevenlabs_clone_voices: Whether to clone source voices. It requires
          using ElevenLabs API.
        elevenlabs_model: The ElevenLabs model to use in the Text-To-Speech
          process.
        elevenlabs_remove_cloned_voices: Whether to remove all the voices that
          were cloned with ELevenLabs during the dubbing process.
        number_of_steps: The total number of steps in the dubbing process.
        with_verification: Whether a user wishes to verify, and optionally edit,
          the utterance metadata in the dubbing process.
    """
    self._input_file = input_file
    self.output_directory = output_directory
    self.advertiser_name = advertiser_name
    self.original_language = original_language
    self.target_language = target_language
    self.number_of_speakers = number_of_speakers
    self.no_dubbing_phrases = no_dubbing_phrases
    self.diarization_instructions = diarization_instructions
    self.translation_instructions = translation_instructions
    self.merge_utterances = merge_utterances
    self.minimum_merge_threshold = minimum_merge_threshold
    self.preferred_voices = preferred_voices
    self.adjust_speed = adjust_speed
    self.vocals_volume_adjustment = vocals_volume_adjustment
    self.background_volume_adjustment = background_volume_adjustment
    self.voice_separation_rounds = voice_separation_rounds
    self.vocals_audio_file = vocals_audio_file
    self.background_audio_file = background_audio_file
    self.clean_up = clean_up
    self.pyannote_model = pyannote_model
    self.hugging_face_token = hugging_face_token
    self.gcp_project_id = gcp_project_id
    self.gcp_region = gcp_region
    self.use_elevenlabs = use_elevenlabs
    self.elevenlabs_token = elevenlabs_token
    self._elevenlabs_clone_voices = elevenlabs_clone_voices
    self.elevenlabs_model = elevenlabs_model
    self.elevenlabs_remove_cloned_voices = elevenlabs_remove_cloned_voices
    self.diarization_system_instructions = diarization_system_instructions
    self.translation_system_instructions = translation_system_instructions
    self.gemini_model_name = gemini_model_name
    self.temperature = temperature
    self.top_p = top_p
    self.top_k = top_k
    self.max_output_tokens = max_output_tokens
    self.response_mime_type = response_mime_type
    self.safety_settings = safety_settings
    self.utterance_metadata = None
    self._number_of_steps = number_of_steps
    self.with_verification = with_verification
    self.text_to_speech = None
    self._voice_assigner = None
    self.assigned_voices_override = assigned_voices_override
    self.keep_voice_assignments = keep_voice_assignments
    self.voice_assignments = None
    self._run_from_script = False
    self._dubbing_from_utterance_metadata = False
    self._voice_allocation_needed = False
    self._voice_properties_added = False
    create_output_directories(output_directory)

  @functools.cached_property
  def input_file(self):
    renamed_input_file = rename_input_file(self._input_file)
    if renamed_input_file != self._input_file:
      logging.warning(
          "The input file was renamed because the original name contained"
          " spaces, hyphens, or other incompatible characters. The updated"
          f" input file is: {renamed_input_file}"
      )
      overwrite_input_file(
          input_file=self._input_file, updated_input_file=renamed_input_file
      )
    return renamed_input_file

  @functools.cached_property
  def device(self):
    return "cuda" if torch.cuda.is_available() else "cpu"

  @functools.cached_property
  def is_video(self) -> bool:
    """Checks if the input file is a video."""
    return is_video(input_file=self.input_file)

  def get_api_token(
      self, *, environmental_variable: str, provided_token: str | None = None
  ) -> str:
    """Helper to get API token, prioritizing provided argument over environment variable.

    Args:
        environmental_variable: The name of the environment variable storing the
          API token.
        provided_token: The API token provided directly as an argument.

    Returns:
        The API token (either the provided one or from the environment).

    Raises:
        ValueError: If neither the provided token nor the environment variable
        is set.
    """
    token = provided_token or os.getenv(environmental_variable)
    if not token:
      raise ValueError(
          f"You must either provide the '{environmental_variable}' argument or"
          f" set the '{environmental_variable.upper()}' environment variable."
      )
    return token

  @functools.cached_property
  def pyannote_pipeline(self) -> Pipeline:
    """Loads the PyAnnote diarization pipeline."""
    hugging_face_token = self.get_api_token(
        environmental_variable=_EXPECTED_HUGGING_FACE_ENVIRONMENTAL_VARIABLE_NAME,
        provided_token=self.hugging_face_token,
    )
    return Pipeline.from_pretrained(
        self.pyannote_model, use_auth_token=hugging_face_token
    )

  @functools.cached_property
  def speech_to_text_model(self) -> WhisperModel:
    """Initializes the Whisper speech-to-text model."""
    return WhisperModel(
        model_size_or_path=_DEFAULT_TRANSCRIPTION_MODEL,
        device=self.device,
        compute_type="float16" if self.device == "cuda" else "int8",
    )

  def configure_gemini_model(
      self, *, system_instructions: str
  ) -> GenerativeModel:
    """Configures the Gemini generative model.

    Args:
        system_instructions: The system instruction to guide the model's
          behavior.

    Returns:
        The configured Gemini model instance.
    """
    vertexai.init(project=self.gcp_project_id, location=self.gcp_region)
    gemini_configuration = dict(
        temperature=self.temperature,
        top_p=self.top_p,
        top_k=self.top_k,
        max_output_tokens=self.max_output_tokens,
        response_mime_type=self.response_mime_type,
    )
    return GenerativeModel(
        model_name=self.gemini_model_name,
        generation_config=gemini_configuration,
        system_instruction=system_instructions,
        safety_settings=self.safety_settings,
    )

  @functools.cached_property
  def text_to_speech_client(
      self,
  ) -> texttospeech.TextToSpeechClient | ElevenLabs:
    """Creates a Text-to-Speech client."""
    if not self.use_elevenlabs:
      return texttospeech.TextToSpeechClient()
    logging.warning(
        "You decided to use ElevenLabs API. It will generate extra cost. Check"
        " their pricing on the following website:"
        " https://elevenlabs.io/pricing. Use Google's Text-To-Speech to contain"
        " all the costs within your Google Cloud Platform (GCP) project."
    )
    elevenlabs_token = self.get_api_token(
        environmental_variable=_EXPECTED_ELEVENLABS_ENVIRONMENTAL_VARIABLE_NAME,
        provided_token=self.elevenlabs_token,
    )
    return ElevenLabs(api_key=elevenlabs_token)

  def _verify_api_access(self) -> None:
    """Verifies access to all the required APIs."""
    logging.info("Verifying access to PyAnnote from HuggingFace.")
    if not self.pyannote_pipeline:
      raise PyAnnoteAccessError(
          "No access to HuggingFace. Make sure you passed the correct API token"
          " either as 'hugging_face_token' or through the"
          " '{_EXPECTED_HUGGING_FACE_ENVIRONMENTAL_VARIABLE_NAME}'"
          " environmental variable. Also, please make sure you accepted the"
          " user agreement for the segmentation model"
          " (https://huggingface.co/pyannote/segmentation-3.0) and the speaker"
          " diarization model"
          " (https://huggingface.co/pyannote/speaker-diarization-3.1)."
      )
    logging.info("Access to PyAnnote from HuggingFace verified.")
    if not self.use_elevenlabs:
      logging.info("Verifying access to Google's Text-To-Speech.")
      try:
        self.text_to_speech_client.list_voices()
      except ServiceUnavailable:
        raise GoogleTextToSpeechAccessError(
            f"No access to Google's Text-To-Speech. Make sure to autorize"
            f" your access with 'gcloud auth application-default login' and"
            f" then 'gcloud auth login'."
        )
      logging.info("Access to Google's Text-To-Speech verified.")
    else:
      logging.info("Verifying access to ElevenLabs.")
      try:
        self.text_to_speech_client.user.get()
      except ApiError:
        raise ElevenLabsAccessError(
            "You specified to use ElevenLabs API for Text-To-Speech. No access"
            " to ElevenLabs. Make sure you passed the correct API token either"
            " as 'elevenlabs_token' or through the"
            f" '{_EXPECTED_ELEVENLABS_ENVIRONMENTAL_VARIABLE_NAME}'"
            " environmental variable."
        )
      logging.info("Access to ElevenLabs verified.")

  @functools.cached_property
  def processed_diarization_system_instructions(self) -> str:
    """Reads and caches diarization system instructions."""
    return read_system_settings(
        system_instructions=self.diarization_system_instructions
    )

  @functools.cached_property
  def processed_translation_system_instructions(self) -> str:
    """Reads and caches translation system instructions."""
    return read_system_settings(
        system_instructions=self.translation_system_instructions
    )

  @functools.cached_property
  def processed_edit_translation_system_instructions(self) -> str:
    """Reads and caches system instructions for the edit translation process."""
    return read_system_settings(
        system_instructions=_DEFAULT_EDIT_TRANSLATION_SYSTEM_SETTINGS
    )

  @functools.cached_property
  def elevenlabs_clone_voices(self) -> bool:
    """An indicator whether to use voice cloning during the dubbing process.

    Raises:
        ValueError: When 'clone_voices' is True and 'use_elevenlabs' is False.
    """
    if self._elevenlabs_clone_voices and not self.use_elevenlabs:
      raise ValueError("Voice cloning requires using ElevenLabs API.")
    if self._elevenlabs_clone_voices:
      logging.warning(
          "You decided to clone voices with ElevenLabs API. It might require a"
          " more expensive pricing tier. Check their pricing on the following"
          " website: https://elevenlabs.io/pricing. Use Google's Text-To-Speech"
          " to contain all the costs within your Google Cloud Platform (GCP)"
          " project."
      )
      logging.warning(
          "Each cloned voices is stored at ElevenLabs and there might be a"
          " limit to how many you can keep there. You might need to remove"
          " voices from ElevenLabs periodically to avoid errors."
      )
    return self._elevenlabs_clone_voices

  @functools.cached_property
  def _gcs_bucket_name(self) -> bool:
    """Returns a GCS bucket name where the video will be uploaded for Gemini temporarily."""
    now = datetime.datetime.now()
    return "dubbing-speakeridentification-" + now.strftime("%Y%m%d%H%M%S%f")

  def run_preprocessing(self) -> None:
    """Splits audio/video, applies DEMUCS, and segments audio into utterances with PyAnnote.

    Returns:
        A named tuple containing paths and metadata of the processed files.
    """
    if self.is_video:
      video_file, audio_file = video_processing.split_audio_video(
          video_file=self.input_file, output_directory=self.output_directory
      )
    else:
      video_file = None
      audio_file = self.input_file
    if not self.vocals_audio_file and not self.background_audio_file:
      audio_vocals_file, audio_background_file = (
          audio_processing.split_audio_track(
              audio_file=audio_file,
              output_directory=self.output_directory,
              device=self.device,
              voice_separation_rounds=self.voice_separation_rounds,
          )
      )
    else:
      audio_vocals_file, audio_background_file = (
          audio_processing.prepare_override_audio_files(
              vocals_audio_file=self.vocals_audio_file,
              background_audio_file=self.background_audio_file,
              output_directory=self.output_directory,
          )
      )
    if not self._dubbing_from_utterance_metadata:
      utterance_metadata = audio_processing.create_pyannote_timestamps(
          audio_file=audio_file,
          number_of_speakers=self.number_of_speakers,
          pipeline=self.pyannote_pipeline,
          device=self.device,
      )
      if self.merge_utterances:
        utterance_metadata = audio_processing.merge_utterances(
            utterance_metadata=utterance_metadata,
            minimum_merge_threshold=self.minimum_merge_threshold,
        )
      self.utterance_metadata = utterance_metadata
    utterance_metadata = audio_processing.run_cut_and_save_audio(
        utterance_metadata=self.utterance_metadata,
        audio_file=audio_file,
        output_directory=self.output_directory,
    )
    self.preprocessing_output = PreprocessingArtifacts(
        video_file=video_file,
        audio_file=audio_file,
        audio_vocals_file=audio_vocals_file,
        audio_background_file=audio_background_file,
    )
    self.utterance_metadata = utterance_metadata
    logging.info("Completed preprocessing.")
    self.progress_bar.update()

  def run_preprocessing_for_dubbing_from_script(self) -> None:
    """Splits audio/video.

    Returns:
        A named tuple containing paths and metadata of the processed files.
    """
    if self.is_video:
      video_file, audio_file = video_processing.split_audio_video(
          video_file=self.input_file, output_directory=self.output_directory
      )
    else:
      video_file = None
      audio_file = self.input_file
    self.preprocessing_output = PreprocessingArtifacts(
        video_file=video_file,
        audio_file=audio_file,
    )
    logging.info("Completed preprocessing.")
    self.progress_bar.update()

  def run_speech_to_text(self) -> None:
    """Transcribes audio, applies speaker diarization, and updates metadata with Gemini.

    Returns:
        Updated utterance metadata with speaker information and transcriptions.
    """
    media_file = (
        self.preprocessing_output.video_file
        if self.preprocessing_output.video_file
        else self.preprocessing_output.audio_file
    )
    utterance_metadata = speech_to_text.transcribe_audio_chunks(
        utterance_metadata=self.utterance_metadata,
        advertiser_name=self.advertiser_name,
        original_language=self.original_language,
        model=self.speech_to_text_model,
        no_dubbing_phrases=self.no_dubbing_phrases,
    )
    speaker_diarization_model = self.configure_gemini_model(
        system_instructions=self.processed_diarization_system_instructions
    )
    speech_to_text.create_gcs_bucket(
        gcp_project_id=self.gcp_project_id,
        gcs_bucket_name=self._gcs_bucket_name,
        gcp_region=self.gcp_region,
    )
    gcs_input_file_path = speech_to_text.upload_file_to_gcs(
        gcp_project_id=self.gcp_project_id,
        gcs_bucket_name=self._gcs_bucket_name,
        file_path=media_file,
    )
    attempt = 0
    success = False
    while attempt < _MAX_GEMINI_RETRIES and not success:
      try:
        speaker_info = speech_to_text.diarize_speakers(
            gcs_input_path=gcs_input_file_path,
            utterance_metadata=utterance_metadata,
            number_of_speakers=self.number_of_speakers,
            model=speaker_diarization_model,
            diarization_instructions=self.diarization_instructions,
        )
        self.utterance_metadata = speech_to_text.add_speaker_info(
            utterance_metadata=utterance_metadata, speaker_info=speaker_info
        )
        success = True
      except speech_to_text.GeminiDiarizationError:
        attempt += 1
        logging.warning(
            f"Diarization attempt {attempt} failed. Will try again."
        )
        if attempt == _MAX_GEMINI_RETRIES:
          raise RuntimeError("Can't diarize speakers. Try again.")
    speech_to_text.remove_gcs_bucket(
        gcp_project_id=self.gcp_project_id,
        gcs_bucket_name=self._gcs_bucket_name,
    )
    logging.info("Completed transcription.")
    self.progress_bar.update()

  def run_translation(self) -> None:
    """Translates transcribed text and potentially merges utterances with Gemini.

    Returns:
        Updated utterance metadata with translated text.
    """
    script = translation.generate_script(
        utterance_metadata=self.utterance_metadata
    )
    translation_model = self.configure_gemini_model(
        system_instructions=self.processed_translation_system_instructions
    )
    attempt = 0
    success = False
    while attempt < _MAX_GEMINI_RETRIES and not success:
      try:
        translated_script = translation.translate_script(
            script=script,
            advertiser_name=self.advertiser_name,
            translation_instructions=self.translation_instructions,
            target_language=self.target_language,
            model=translation_model,
        )
        self.utterance_metadata = translation.add_translations(
            utterance_metadata=self.utterance_metadata,
            translated_script=translated_script,
        )
        success = True
      except translation.GeminiTranslationError:
        attempt += 1
        logging.warning(
            f"Translation attempt {attempt} failed. Will try again."
        )
        if attempt == _MAX_GEMINI_RETRIES:
          raise RuntimeError("Can't translate script. Try again.")
    logging.info("Completed translation.")
    self.progress_bar.update()

  def _prompt_for_voice_reassignment(self):
    """Displays a prompt asking the user how they want to handle voice reassignment."""
    clear_output(wait=True)
    html = "<h3>Current voice assignment settings</h3>"
    html += "<ul>"
    html += "<li><b>assigned_voices_override:</b> {}</li>".format(
        self.assigned_voices_override
    )
    html += "<li><b>preferred_voices:</b> {}</li>".format(self.preferred_voices)
    html += "<li><b>voice_assignments:</b> {}</li>".format(
        self.voice_assignments
    )
    html += "</ul>"
    display(HTML(html))
    print(
        """\nSince you're dubbing to another language, there might be language compatibility issues with the previously assigned voices when using Google Text-To-Speech."""
    )
    while True:
      time.sleep(1)
      sys.stdout.flush()
      reassign_choice = input("""
              \nWould you like to:
                  1. Edit voice assignments manually (edit)?
                  2. Reassign voices automatically (continue)?
              Enter your choice ('edit' or 'continue'):
              """)
      if reassign_choice == "edit":
        self._run_verify_utterance_metadata()
        clear_output(wait=True)
        break
      elif reassign_choice == "continue":
        self.voice_assignments = None
        self.preferred_voices = None
        self.assigned_voices_override = None
        clear_output(wait=True)
        print("Voices will be automatically reassigned.")
        break
      else:
        print("Invalid choice.")

  def run_configure_text_to_speech(
      self,
      dubbing_to_another_language: bool = False,
      utterance_metadata_overrides: (
          Sequence[Mapping[str, str | float]] | None
      ) = None,
  ) -> None:
    """Configures the Text-To-Speech process.

    Args:
      dubbing_to_another_language: An indicator if the voice property
        reassignment should be run for a new language.
      utterance_metadata_overrides: Utterance metadata to ue in the process
        instead of `self.utterance_metadata`.

    Returns:
        Updated utterance metadata with assigned voices
        and Text-To-Speech settings.
    """
    if dubbing_to_another_language:
      self._prompt_for_voice_reassignment()
    if not utterance_metadata_overrides:
      utterance_metadata = self.utterance_metadata
      update_text_to_speech_properties = True
    else:
      utterance_metadata = utterance_metadata_overrides
      update_text_to_speech_properties = False
    self._voice_assigner = text_to_speech.VoiceAssigner(
        utterance_metadata=utterance_metadata,
        client=self.text_to_speech_client,
        target_language=self.target_language,
        preferred_voices=self.preferred_voices,
        assigned_voices_override=self.assigned_voices_override,
        keep_voice_assignments=self.keep_voice_assignments,
        voice_assignments=self.voice_assignments,
        elevenlabs_clone_voices=self.elevenlabs_clone_voices,
    )
    self.voice_assignments = self._voice_assigner.assigned_voices
    self.utterance_metadata = text_to_speech.update_utterance_metadata(
        utterance_metadata=utterance_metadata,
        assigned_voices=self.voice_assignments,
        use_elevenlabs=self.use_elevenlabs,
        elevenlabs_clone_voices=self.elevenlabs_clone_voices,
        adjust_speed=self.adjust_speed,
        update_text_to_speech_properties=update_text_to_speech_properties,
    )
    self._voice_properties_added = True

  def _run_speech_to_text_on_single_utterance(
      self, modified_utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Runs the equivalent 'speech_to_text' on a modified utterance.

    Args:
      modified_utterance: A mapping with "start", "end", "path", "for_dubbing"
        and optionally "vocals_path".

    Returns:
        Updated utterance metadata with speaker information and transcriptions
        for a single utterance.
    """
    utterance_metadata = [modified_utterance.copy()]
    return speech_to_text.transcribe_audio_chunks(
        utterance_metadata=utterance_metadata,
        advertiser_name=self.advertiser_name,
        original_language=self.original_language,
        model=self.speech_to_text_model,
        no_dubbing_phrases=self.no_dubbing_phrases,
    )[0]

  def _run_translation_on_single_utterance(
      self, modified_utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Runs the equivalent 'run_translation' on a modified utterance.

    Returns:
        Updated utterance metadata with translated text for a single utterance.
    """
    utterance_metadata = [modified_utterance.copy()]
    script = translation.generate_script(utterance_metadata=utterance_metadata)
    translation_model = self.configure_gemini_model(
        system_instructions=self.processed_translation_system_instructions
    )
    attempt = 0
    success = False
    while attempt < _MAX_GEMINI_RETRIES and not success:
      try:
        translated_script = translation.translate_script(
            script=script,
            advertiser_name=self.advertiser_name,
            translation_instructions=self.translation_instructions,
            target_language=self.target_language,
            model=translation_model,
        )
        translated_utterance = translation.add_translations(
            utterance_metadata=utterance_metadata,
            translated_script=translated_script,
        )
        success = True
      except translation.GeminiTranslationError:
        attempt += 1
        logging.warning(
            f"Translation attempt {attempt} failed. Will try again."
        )
        if attempt == _MAX_GEMINI_RETRIES:
          raise RuntimeError("Can't translate the added utterance. Try again.")
    return translated_utterance[0]

  def _repopulate_metadata(
      self, *, utterance: Mapping[str, str | float], modified: bool = True
  ) -> Mapping[str, str | float]:
    if not modified:
      print(
          "Populating the metadata fields for the added speech chunk"
          " (utterance). It might take a minute."
      )
      verified_utterance = audio_processing.verify_added_audio_chunk(
          audio_file=self.preprocessing_output.audio_file,
          utterance=utterance,
          output_directory=self.output_directory,
      )
      if self._voice_properties_added:
        verified_utterance = text_to_speech.add_text_to_speech_properties(
            utterance_metadata=verified_utterance,
            use_elevenlabs=self.use_elevenlabs,
        )
      logging.warning(
          "Updated the added utterance with the default Text-To-Speech"
          " properties."
      )
    else:
      print(
          "Updating the metadata fields for the modified speech chunk"
          " (utterance). It might take a minute."
      )
      verified_utterance = audio_processing.verify_modified_audio_chunk(
          audio_file=self.preprocessing_output.audio_file,
          utterance=utterance,
          output_directory=self.output_directory,
      )
    transcribed_utterance = self._run_speech_to_text_on_single_utterance(
        verified_utterance
    )
    return self._run_translation_on_single_utterance(transcribed_utterance)

  def _update_utterance_metadata(
      self,
      *,
      updated_utterance: Mapping[str, str | float],
      utterance_metadata: Sequence[Mapping[str, str | float]],
      edit_index: int | None = None,
  ) -> Sequence[Mapping[str, str | float]]:
    """Runs the update process of the added utterance."""
    utterance_metadata_copy = utterance_metadata.copy()
    if isinstance(edit_index, int):
      utterance_metadata_copy[edit_index] = updated_utterance
    else:
      utterance_metadata_copy.append(updated_utterance)
    utterance_metadata_copy.sort(key=lambda item: (item["start"], item["end"]))
    added_index = utterance_metadata_copy.index(updated_utterance) + 1
    print(f"Item added / modified at position {added_index}.")
    return utterance_metadata_copy

  def _display_utterance_metadata(
      self, utterance_metadata: Sequence[Mapping[str, str | float]]
  ) -> None:
    """Displays the current utterance metadata as formatted HTML.

    This method iterates through the provided utterance metadata,
    formats each utterance as an HTML snippet with headings and lists,
    and then renders the HTML using IPython.display.HTML for a more
    visually appealing presentation in the IPython environment.

    Args:
      utterance_metadata: A sequence of dictionaries, where each dictionary
        contains metadata for a single utterance.
    """
    for i, item in enumerate(utterance_metadata):
      item_copy = item.copy()
      for key in _LOCKED_KEYS:
        item_copy.pop(key, None)

      html = "<h3>Utterance {}</h3>".format(i + 1)
      html += "<ul>"
      for key, value in item_copy.items():
        formatted_value = str(value) if isinstance(value, float) else str(value)
        html += "<li><b>{}:</b> {}</li>".format(key, formatted_value)
      html += "</ul>"
      display(HTML(html))

  @functools.cached_property
  def _voice_properties_fields(self) -> Sequence[str]:
    """Provides a list of voice prperties depending on the client type."""
    voice_properties_fields = ["adjust_speed"]
    if isinstance(self.text_to_speech_client, texttospeech.TextToSpeechClient):
      return voice_properties_fields + ["pitch", "speed", "volume_gain_db"]
    else:
      return voice_properties_fields + [
          "stability",
          "similarity_boost",
          "style",
          "use_speaker_boost",
      ]

  def _add_utterance_metadata(self) -> Mapping[str, str | float]:
    """Allows adding a new utterance metadata entry, prompting for each field."""
    new_utterance = {}
    required_fields = ["start", "end", "ssml_gender"]
    if not self._voice_properties_added:
      if self._run_from_script:
        required_fields += [
            "assigned_voice",
            "text",
        ] + self._voice_properties_fields
    else:
      required_fields += ["assigned_voice"] + self._voice_properties_fields
      if self._run_from_script:
        required_fields += ["text"]
    while True:
      speaker_id = input("\nEnter value for 'speaker_id': ")
      new_utterance.update({"speaker_id": speaker_id})
      existing_metadata = next(
          (
              entry
              for entry in self.utterance_metadata
              if entry.get("speaker_id") == speaker_id
          ),
          None,
      )
      if existing_metadata:
        choice = (
            input(
                f"Speaker '{speaker_id}' found. Do you want to reuse existing"
                " metadata? (yes/no): "
            )
            .strip()
            .lower()
        )
        if choice == "yes":
          new_utterance.update({
              field: value
              for field, value in existing_metadata.items()
              if field not in ["start", "end"]
          })
          required_fields = ["start", "end"]
          break
      break
    for field in required_fields:
      while True:
        try:
          value = input(f"\nEnter value for '{field}': ")
          if field in [
              "start",
              "end",
              "pitch",
              "speed",
              "volume_gain_db",
              "stability",
              "similarity_boost",
              "style",
          ]:
            value = float(value)
            if (
                field == "end"
                and "start" in new_utterance
                and value <= new_utterance["start"]
            ):
              print("End time cannot be less than or equal to start time.")
              continue
          elif field == "use_speaker_boost":
            value = bool(value)
          new_utterance[field] = value
          if self._run_from_script and field == "text":
            new_utterance["translated_text"] = value
            new_utterance["for_dubbing"] = True
          break
        except ValueError:
          print(f"Invalid input for '{field}'. Please enter a valid value.")
    return new_utterance

  def _select_edit_number(
      self, utterance_metadata: Sequence[Mapping[str, str | float]]
  ) -> int:
    """Runs edit index selection process."""
    ask_for_index = True
    while ask_for_index:
      try:
        time.sleep(1)
        sys.stdout.flush()
        index = int(input("""\nEnter item number to edit: """)) - 1
        if not 0 <= index < len(utterance_metadata):
          print("Invalid item number.")
        else:
          ask_for_index = False
          return index
      except ValueError:
        print("Invalid input format. Please try again.")

  def _edit_utterance_metadata(
      self,
      utterance_metadata: Sequence[Mapping[str, str | float]],
      edit_index: int,
  ) -> Mapping[str, str | float]:
    """Lets you interactively edit the metadata of a single utterance.

    Prompts you to choose a key to modify, enter a new value, and
    validates your input. You can keep editing the same utterance until
    you choose to stop.

    Args:
        utterance_metadata: The list of all utterance metadata.
        edit_index: The index of the utterance to edit.

    Returns:
        The updated metadata for the edited utterance.
    """
    utterance = utterance_metadata[edit_index].copy()
    while True:
      while True:
        time.sleep(1)
        sys.stdout.flush()
        key_to_modify = input(
            f"""\nEnter the key you want to modify for utterance {edit_index + 1}: """
        )
        if key_to_modify in _LOCKED_KEYS:
          print(
              f"'{key_to_modify}' cannot be edited. Please choose another key."
          )
        if key_to_modify in utterance:
          break
        else:
          print(
              f"Invalid key: {key_to_modify}. Available keys are:"
              f" {', '.join(utterance.keys())}"
          )
      while True:
        try:
          time.sleep(1)
          sys.stdout.flush()
          new_value = input(
              f"""\nEnter the new value for '{key_to_modify}': """
          )
          if key_to_modify in _FLOAT_KEYS:
            new_value = float(new_value)
          elif key_to_modify in _BOOLEAN_KEYS:
            if new_value.lower() == "true" or new_value.lower() == "True":
              new_value = True
            elif new_value.lower() == "false" or new_value.lower() == "False":
              new_value = False
            else:
              raise ValueError
          else:
            new_value = str(new_value)
          break
        except ValueError:
          print(
              f"Invalid input for '{key_to_modify}'. Please enter a valid"
              " value. Make sure it matches the original type, a float (e.g."
              " 0.01), a string (e.g. 'example') or a boolean (e.g. 'True')."
          )
      utterance[key_to_modify] = new_value
      while True:
        time.sleep(1)
        sys.stdout.flush()
        modify_more = input(
            """\nDo you want to modify anything else? (yes/no): """
        ).lower()
        if modify_more in ("yes", "no"):
          break
        else:
          print("Invalid input. Please enter 'yes' or 'no'.")
      if modify_more != "yes":
        break
    return utterance

  def _remove_utterance_metadata(
      self, utterance_metadata: Sequence[Mapping[str, str | float]]
  ) -> None:
    """Allows hiding utterance metadata by marking 'for_dubbing' as False."""
    while True:
      try:
        time.sleep(1)
        sys.stdout.flush()
        index = (
            int(
                input(
                    """\nEnter item number to remove from the dubbing process: """
                )
            )
            - 1
        )
        if 0 <= index < len(utterance_metadata):
          utterance_metadata[index]["for_dubbing"] = False
          print(
              "Item hidden. It will not be included in the dubbing process. The"
              " orginal vocals will be used."
          )
          return
        else:
          print("Invalid item number.")
      except (ValueError, KeyError):
        print("Invalid input or item format. Please try again.")

  def _prompt_for_translation(self) -> str:
    """Prompts the user if they want to run translation."""
    while True:
      time.sleep(1)
      sys.stdout.flush()
      translate_choice = input("""
                              \nYou modified 'text' of the utterance. Do you want to run
                              \ntranslation (it's recommended after modifying the source utterance text)? (yes/no):
                               """).lower()
      if translate_choice in ("yes", "no"):
        return translate_choice
      else:
        print("Invalid choice.")

  def _verify_metadata_after_change(self):
    """Asks the user if they want to review the metadata again after changes."""
    while True:
      time.sleep(1)
      sys.stdout.flush()
      review_choice = input(
          """\nDo you want to review the metadata again? (yes/no): """
      ).lower()
      if review_choice in ("yes", "no"):
        return review_choice == "no"
      else:
        print("Invalid choice.")

  def _prompt_for_gemini_translation_chat(self) -> str:
    """Prompts the user if they want to chat with Gemini about a translation."""
    while True:
      time.sleep(1)
      sys.stdout.flush()
      gemini_translation_chat_choice = input(
          """\nWould you like to chat with Gemini about a translation? (yes/no): """
      ).lower()
      if gemini_translation_chat_choice in ("yes", "no"):
        return gemini_translation_chat_choice
      else:
        print("Invalid choice.")

  def _translate_utterance_with_gemini(
      self,
      *,
      utterance_metadata: Sequence[Mapping[str, str | float]],
      edit_index: int,
  ) -> Mapping[str, str | float]:
    """Fixes the translation incorporating user feedback received from the chat with Gemini"""
    script = translation.generate_script(utterance_metadata=utterance_metadata)
    translated_script = translation.generate_script(
        utterance_metadata=utterance_metadata, key="translated_text"
    )
    edited_utterance = utterance_metadata[edit_index].copy()
    source_text = edited_utterance["text"]
    discussed_translation = edited_utterance["translated_text"]
    edit_translation_model = self.configure_gemini_model(
        system_instructions=self.processed_edit_translation_system_instructions
    )
    background_prompt = _EDIT_TRANSLATION_PROMPT.format(
        self.advertiser_name,
        script,
        translated_script,
        self.target_language,
        discussed_translation,
    )
    edit_translation_chat_session = edit_translation_model.start_chat()
    turn = 0
    continue_chat = True
    updated_translation = discussed_translation
    print(f"The source text is: {source_text}")
    print(f"The initial translation is: {discussed_translation}")
    while continue_chat:
      time.sleep(1)
      sys.stdout.flush()
      user_message = input(
          """
                           \nType your message to Gemini about the translation.
                           \nOr type in 'exit' to approve it and exit the chat: """
      ).lower()
      if user_message != "exit":
        if turn == 0:
          prompt = background_prompt + " " + "User feedback: " + user_message
        else:
          prompt = user_message
        response = edit_translation_chat_session.send_message(prompt)
        updated_translation = response.text.replace("\n", "").strip()
        print(f"The updated translation is: '{updated_translation}'.")
        turn += 1
      else:
        continue_chat = False
    edited_utterance["translated_text"] = updated_translation
    return edited_utterance

  def _bulk_edit_utterance_metadata(
      self, utterance_metadata: Sequence[Mapping[str, str | float]]
  ) -> Sequence[Mapping[str, str | float]]:
    """Allows bulk editing of utterance metadata entries."""
    while True:
      try:
        time.sleep(1)
        sys.stdout.flush()
        indices_str = input(
            """\nEnter item numbers to edit (comma-separated): """
        )
        indices = [int(x.strip()) - 1 for x in indices_str.split(",")]
        for index in indices:
          if not 0 <= index < len(utterance_metadata):
            raise ValueError("Invalid item number.")
        break
      except ValueError:
        print("Invalid input format. Please try again.")
    while True:
      try:
        readline.set_startup_hook(lambda: readline.insert_text("{}"))
        time.sleep(1)
        sys.stdout.flush()
        updates_str = input("""\nEnter updates as a JSON dictionary: """)
        readline.set_startup_hook()
        updates = json.loads(updates_str)
        if not isinstance(updates, dict):
          raise ValueError("Updates must be a dictionary.")
        invalid_keys = set(updates.keys()) - set(_ALLOWED_BULK_EDIT_KEYS)
        if invalid_keys:
          print(
              f"Invalid keys found: {invalid_keys}. Allowed keys are:"
              f" {_ALLOWED_BULK_EDIT_KEYS}"
          )
          continue
        break
      except (json.JSONDecodeError, ValueError):
        print("Invalid JSON or input. Please try again.")
    updated_metadata = utterance_metadata.copy()
    for index in indices:
      updated_item = updated_metadata[index].copy()
      updated_item.update(updates)
      updated_metadata[index] = updated_item
    return updated_metadata

  def _prompt_for_verification_after_voice_configured(self) -> None:
    """Prompts the user to verify voice assignments and properties."""
    clear_output(wait=True)
    self._display_utterance_metadata(self.utterance_metadata)
    while True:
      time.sleep(1)
      sys.stdout.flush()
      verify_voices_choice = input(
          """
                                  \nVoices and voice properties were added to the utterance metadata above.
                                  \n Would you like to edit them before the process completes?(yes/no): """
      ).lower()
      if verify_voices_choice == "yes":
        if not self._run_from_script:
          self._run_verify_utterance_metadata()
        else:
          self._run_verify_utterance_metadata_script_workflow()
        clear_output(wait=True)
        break
      elif verify_voices_choice == "no":
        clear_output(wait=True)
        print("Please wait...")
        break
      else:
        print("Invalid choice.")

  def _verify_and_redub_utterances(self) -> None:
    """Verifies and allows re-dubbing of utterances."""
    original_metadata = self.utterance_metadata.copy()
    if not self._run_from_script:
      self._run_verify_utterance_metadata()
    else:
      self._run_verify_utterance_metadata_script_workflow()
    clear_output(wait=True)
    edited_utterances = self.text_to_speech.dub_edited_utterances(
        original_utterance_metadata=original_metadata,
        updated_utterance_metadata=self.utterance_metadata,
    )
    updated_utterance_metadata = self.utterance_metadata.copy()
    if not self._run_from_script:
      for edited_utterance in edited_utterances:
        for i, original_utterance in enumerate(updated_utterance_metadata):
          if (
              original_utterance["path"] == edited_utterance["path"]
              and original_utterance["dubbed_path"]
              != edited_utterance["dubbed_path"]
          ):
            updated_utterance_metadata[i] = edited_utterance
    self.utterance_metadata = updated_utterance_metadata

  def _prompt_for_dubbed_utterances_verification(self) -> None:
    """Prompts the user to verify dubbed utterances by listening to them."""
    while True:
      with_playback = False
      time.sleep(1)
      sys.stdout.flush()
      verify_dubbed_utterances_choice = input(
          """\nUtterances have been dubbed. Would you like to listen to them? (yes/no): """
      ).lower()
      if verify_dubbed_utterances_choice == "yes":
        clear_output(wait=True)
        for i, utterance in enumerate(self.utterance_metadata):
          if utterance.get("dubbed_path"):
            print(
                f"{i+1}. Playing speech chunk (utterance):"
                f" {utterance.get('translated_text')}"
            )
            display(Audio(utterance["dubbed_path"]))
        with_playback = True
        break
      elif verify_dubbed_utterances_choice == "no":
        clear_output(wait=True)
        print("Please wait...")
        break
      else:
        print("Invalid choice.")
    if with_playback:
      while True:
        time.sleep(1)
        sys.stdout.flush()
        verify_again_choice = input(
            """\nWould you like to edit and re-dub the edited speech chunks (utterances) again? (yes/no): """
        ).lower()
        if verify_again_choice == "yes":
          clear_output(wait=True)
          self._verify_and_redub_utterances()
          clear_output(wait=True)
          self._prompt_for_dubbed_utterances_verification()
          break
        elif verify_again_choice == "no":
          clear_output(wait=True)
          print("Please wait...")
          break
        else:
          print("Invalid choice.")

  def _prompt_for_output_preview(self) -> None:
    """Prompts the user to preview the output video/audio after postprocessing."""
    while True:
      with_preview = False
      time.sleep(1)
      sys.stdout.flush()
      preview_choice = input(
          """\nPostprocessing is complete. Would you like to preview the dubbed output? (yes/no): """
      ).lower()
      if preview_choice == "yes":
        print("Previewing the dubbed output:")
        if self.is_video:
          display(
              Video(
                  self.postprocessing_output.video_file,
                  embed=True,
                  width=640,
                  height=480,
              )
          )
        else:
          display(Audio(self.postprocessing_output.audio_file))
        with_preview = True
        break
      elif preview_choice == "no":
        break
      else:
        print("Invalid choice.")
    if with_preview:
      while True:
        time.sleep(1)
        sys.stdout.flush()
        change_choice = input(
            """\nDo you want to change anything in the dubbed output? (yes/no): """
        ).lower()
        if change_choice == "yes":
          clear_output(wait=True)
          if self.with_verification:
            self._verify_and_redub_utterances()
          print("Please wait...")
          self.run_postprocessing()
          if self.with_verification:
            self._prompt_for_dubbed_utterances_verification()
          self._prompt_for_output_preview()
          break
        elif change_choice == "no":
          clear_output(wait=True)
          break
        else:
          print("Invalid choice.")

  def _run_verify_utterance_metadata(self) -> None:
    """Displays, allows editing, adding and removing utterance metadata."""
    utterance_metadata = self.utterance_metadata
    clear_output(wait=True)
    while True:
      self._display_utterance_metadata(utterance_metadata)
      time.sleep(1)
      sys.stdout.flush()
      action_choice = input(
          """\nChoose action: (edit/bulk_edit/add/remove/continue): """
      ).lower()
      if action_choice in ("edit", "bulk_edit", "add", "remove"):
        if action_choice == "edit":
          edit_index = self._select_edit_number(
              utterance_metadata=utterance_metadata
          )
          unmodified_metadata = utterance_metadata[edit_index].copy()
          gemini_translation_chat_choice = (
              self._prompt_for_gemini_translation_chat()
          )
          if gemini_translation_chat_choice == "yes":
            edited_utterance = self._translate_utterance_with_gemini(
                utterance_metadata=utterance_metadata, edit_index=edit_index
            )
          else:
            edited_utterance = self._edit_utterance_metadata(
                utterance_metadata=utterance_metadata, edit_index=edit_index
            )
          if (unmodified_metadata["start"], unmodified_metadata["end"]) != (
              edited_utterance["start"],
              edited_utterance["end"],
          ):
            edited_utterance = self._repopulate_metadata(
                utterance=edited_utterance
            )
          if unmodified_metadata["text"] != edited_utterance["text"]:
            translate_choice = self._prompt_for_translation()
            if translate_choice == "yes":
              edited_utterance = self._run_translation_on_single_utterance(
                  edited_utterance
              )
          edited_utterance = self._handle_special_key_changes(
              unmodified_metadata, edited_utterance
          )
          utterance_metadata = self._update_utterance_metadata(
              updated_utterance=edited_utterance,
              utterance_metadata=utterance_metadata,
              edit_index=edit_index,
          )
          if self._voice_allocation_needed:
            logging.info(
                "Voice reassignment was requested. Resetting"
                " `self.voice_assignments`"
            )
            self.voice_assignments = None
            self.run_configure_text_to_speech(
                utterance_metadata_overrides=utterance_metadata
            )
            self._voice_allocation_needed = False
            utterance_metadata = self.utterance_metadata
        elif action_choice == "bulk_edit":
          utterance_metadata = self._bulk_edit_utterance_metadata(
              utterance_metadata
          )
        elif action_choice == "add":
          added_utterance = self._add_utterance_metadata()
          added_utterance = self._repopulate_metadata(
              utterance=added_utterance, modified=False
          )
          utterance_metadata = self._update_utterance_metadata(
              updated_utterance=added_utterance,
              utterance_metadata=utterance_metadata,
          )
        elif action_choice == "remove":
          self._remove_utterance_metadata(utterance_metadata)
        clear_output(wait=True)
      elif action_choice == "continue":
        self.utterance_metadata = utterance_metadata
        clear_output(wait=True)
        return
      else:
        clear_output(wait=True)
        print("Option unavailable or you had a typo. Try again.")

  def _handle_special_key_changes(
      self,
      unmodified_metadata: Mapping[str, str | float],
      edited_utterance: Mapping[str, str | float],
  ) -> Mapping[str, str | float]:
    """Handles changes to special metadata keys.

    This function checks for changes in the special metadata keys
    ('speaker_id', 'ssml_gender', 'assigned_voice') between the unmodified
    and edited utterance metadata. It then calls the appropriate handler
    function based on the key that was changed.

    Args:
      unmodified_metadata: The original metadata of the utterance.
      edited_utterance: The edited metadata of the utterance.

    Returns:
      The updated metadata after handling the special key changes.
    """
    changed_keys = [
        key
        for key in _SPECIAL_KEYS
        if unmodified_metadata.get(key) != edited_utterance.get(key)
    ]
    if not changed_keys or len(changed_keys) == 3:
      return edited_utterance
    if "speaker_id" in changed_keys:
      return self._handle_speaker_id_change(edited_utterance)
    elif "ssml_gender" in changed_keys:
      return self._handle_ssml_gender_change(edited_utterance)
    elif "assigned_voice" in changed_keys:
      return self._handle_assigned_voice_change(edited_utterance)

  def _handle_speaker_id_change(
      self, edited_utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Handles changes to the 'speaker_id' metadata key.

    This function is called when the 'speaker_id' of an utterance is changed.
    It attempts to find another utterance with the same 'speaker_id' and copy
    its 'ssml_gender' and 'assigned_voice' values. If no matching utterance
    is found, it prompts the user to input these values.

    Args:
      edited_utterance: The edited metadata of the utterance with the changed
        'speaker_id'.

    Returns:
      The updated metadata after handling the 'speaker_id' change.
    """
    new_speaker_id = edited_utterance["speaker_id"]
    matching_utterances = [
        utterance
        for utterance in self.utterance_metadata
        if utterance.get("speaker_id") == new_speaker_id
    ]
    if matching_utterances:
      matched_utterance = matching_utterances[0]
      edited_utterance["ssml_gender"] = matched_utterance["ssml_gender"]
      edited_utterance["assigned_voice"] = matched_utterance["assigned_voice"]
    else:
      edited_utterance["ssml_gender"] = input(
          """\nNo matching metadata found for 'speaker_id'. Please specify 'ssml_gender': """
      )
      assigned_voice = input(
          """
                               \nNo matching metadata found for 'speaker_id'.
                               \nPlease specify 'assigned_voice' (you can also type 'continue' and the voice will be assigned automatically): """
      ).lower()
      if assigned_voice == "continue":
        self._voice_allocation_needed = True
        print(
            "You selected 'continue'. Voices will be reassigned after editing"
            " is completed."
        )
      else:
        edited_utterance["assigned_voice"] = assigned_voice
    return edited_utterance

  def _handle_ssml_gender_change(
      self, edited_utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Handles changes to the 'ssml_gender' metadata key.

    This function is called when the 'ssml_gender' of an utterance is changed.
    It prompts the user to input a 'speaker_id' and attempts to find another
    utterance with the same 'speaker_id' to copy its 'assigned_voice' value.
    If no matching utterance is found, it prompts the user to input the
    'assigned_voice'.

    Args:
      edited_utterance: The edited metadata of the utterance with the changed
        'ssml_gender'.

    Returns:
      The updated metadata after handling the 'ssml_gender' change.
    """
    new_speaker_id = input(
        """\nPlease specify 'speaker_id' to find associated metadata: """
    )
    edited_utterance["speaker_id"] = new_speaker_id
    matching_utterances = [
        utterance
        for utterance in self.utterance_metadata
        if utterance.get("speaker_id") == new_speaker_id
    ]
    if matching_utterances:
      matched_utterance = matching_utterances[0]
      edited_utterance["assigned_voice"] = matched_utterance["assigned_voice"]
    else:
      assigned_voice = input(
          """
                               \nNo matching metadata found for 'speaker_id'.
                               \nPlease specify 'assigned_voice' (you can also type 'continue' and the voice will be assigned automatically): """
      ).lower()
      if assigned_voice == "continue":
        self._voice_allocation_needed = True
        print(
            "You selected 'continue'. Voices will be reassigned after editing"
            " is completed."
        )
      else:
        edited_utterance["assigned_voice"] = assigned_voice
    return edited_utterance

  def _handle_assigned_voice_change(
      self, edited_utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Handles changes to the 'assigned_voice' metadata key.

    This function is called when the 'assigned_voice' of an utterance is
    changed.
    It attempts to find another utterance with the same 'assigned_voice' and
    copy
    its 'speaker_id' and 'ssml_gender' values. If no matching utterance
    is found, it prompts the user to input these values.

    Args:
      edited_utterance: The edited metadata of the utterance with the changed
        'assigned_voice'.

    Returns:
      The updated metadata after handling the 'assigned_voice' change.
    """
    new_assigned_voice = edited_utterance["assigned_voice"]
    matching_utterances = [
        utterance
        for utterance in self.utterance_metadata
        if utterance.get("assigned_voice") == new_assigned_voice
    ]
    if matching_utterances:
      matched_utterance = matching_utterances[0]
      edited_utterance["speaker_id"] = matched_utterance["speaker_id"]
      edited_utterance["ssml_gender"] = matched_utterance["ssml_gender"]
    else:
      edited_utterance["speaker_id"] = input(
          """\nNo matching metadata found for 'assigned_voice'. Please specify 'speaker_id': """
      )
      edited_utterance["ssml_gender"] = input(
          """\nNo matching metadata found for 'assigned_voice'. Please specify 'ssml_gender': """
      )
    return edited_utterance

  def _run_verify_utterance_metadata_script_workflow(self) -> None:
    """Displays, allows editing, adding and removing utterance metadata."""
    utterance_metadata = self.utterance_metadata
    clear_output(wait=True)
    while True:
      self._display_utterance_metadata(utterance_metadata)
      time.sleep(1)
      sys.stdout.flush()
      action_choice = input(
          """\nChoose action: (edit/bulk_edit/add/continue): """
      ).lower()
      if action_choice in ("edit", "bulk_edit", "add"):
        if action_choice == "edit":
          edit_index = self._select_edit_number(
              utterance_metadata=utterance_metadata
          )
          unmodified_metadata = utterance_metadata[edit_index].copy()
          gemini_translation_chat_choice = (
              self._prompt_for_gemini_translation_chat()
          )
          if gemini_translation_chat_choice == "yes":
            edited_utterance = self._translate_utterance_with_gemini(
                utterance_metadata=utterance_metadata, edit_index=edit_index
            )
          else:
            edited_utterance = self._edit_utterance_metadata(
                utterance_metadata=utterance_metadata, edit_index=edit_index
            )
          edited_utterance = self._handle_special_key_changes(
              unmodified_metadata, edited_utterance
          )
          utterance_metadata = self._update_utterance_metadata(
              updated_utterance=edited_utterance,
              utterance_metadata=utterance_metadata,
              edit_index=edit_index,
          )
          if self._voice_allocation_needed:
            logging.info(
                "Voice reassignment was requested. Resetting"
                " `self.voice_assignments`"
            )
            self.voice_assignments = None
            self.run_configure_text_to_speech(
                utterance_metadata_overrides=utterance_metadata
            )
            self._voice_allocation_needed = False
            utterance_metadata = self.utterance_metadata
        elif action_choice == "bulk_edit":
          utterance_metadata = self._bulk_edit_utterance_metadata(
              utterance_metadata
          )
        elif action_choice == "add":
          added_utterance = self._add_utterance_metadata()
          utterance_metadata = self._update_utterance_metadata(
              updated_utterance=added_utterance,
              utterance_metadata=utterance_metadata,
          )
        clear_output(wait=True)
      elif action_choice == "continue":
        self.utterance_metadata = utterance_metadata
        clear_output(wait=True)
        return
      else:
        clear_output(wait=True)
        print("Option unavailable or you had a typo. Try again.")

  def _prompt_if_dub_to_another_language_from_script(self) -> None:
    """Asks the user if they want to dub the ad to another language from script."""
    while True:
      time.sleep(1)
      sys.stdout.flush()
      dub_to_another_language_choice = input(
          """\nWould you like to dub the ad to another language from script? (yes/no): """
      ).lower()
      if dub_to_another_language_choice == "yes":
        clear_output(wait=True)
        time.sleep(1)
        sys.stdout.flush()
        print("\nAvailable language formats (ISO 3166-1):")
        print(_AVAILABLE_LANGUAGES_PROMPT)
        while True:
          try:
            time.sleep(1)
            sys.stdout.flush()
            target_language = input(
                """\nEnter the target language in the ISO 3166-1 format (e.g. 'fr-FR'): """
            )
            self.target_language = target_language
            while True:
              time.sleep(1)
              sys.stdout.flush()
              spreadsheet_choice = input("""
                  \nDo you have a spreadsheet with the script? In the new
                  \n sheet ensure the `translated_text` column contains the text
                  \n already translated to the new target language. (yes/no):
                   """).lower()
              if spreadsheet_choice == "yes":
                time.sleep(1)
                sys.stdout.flush()
                google_sheet_link = input(
                    """\nPlease provide the Google Sheet link: """
                )
                # We assume a user already authenticated themselves with
                # `auth.authenticate_user() (`from google.colab import auth`)
                self.original_language = target_language
                script_with_voice_metadata_df = (
                    colab_utils.get_google_sheet_as_dataframe(google_sheet_link)
                )
                script_with_voice_metadata = (
                    colab_utils.create_script_metadata_from_dataframe(
                        script_with_voice_metadata_df
                    )
                )
                self.dub_ad_from_script(
                    script_with_timestamps=script_with_voice_metadata.script_with_timestamps,
                    assigned_voice=script_with_voice_metadata.assigned_voice,
                    google_text_to_speech_parameters=script_with_voice_metadata.google_text_to_speech_parameters,
                    elevenlabs_text_to_speech_parameters=script_with_voice_metadata.elevenlabs_text_to_speech_parameters,
                )
                break
              elif spreadsheet_choice == "no":
                self.dub_ad_with_different_language(target_language)
                break
              else:
                print("Invalid choice.")
            break
          except ValueError:
            print(
                "Invalid language format. Please use the ISO 3166-1 format"
                " (e.g., 'fr-FR')."
            )
        break
      elif dub_to_another_language_choice == "no":
        break
      else:
        print("Invalid choice.")

  def _prompt_if_dub_to_another_language_from_utterance_metadata(self) -> None:
    """Asks the user if they want to dub the ad to another language from utterance metadata."""
    while True:
      time.sleep(1)
      sys.stdout.flush()
      dub_to_another_language_choice = input("""
                                             \nWould you like to dub the ad to
                                             \n another language from utterance metadata? (yes/no):
                                              """).lower()
      if dub_to_another_language_choice == "yes":
        clear_output(wait=True)
        time.sleep(1)
        sys.stdout.flush()
        print("\nAvailable language formats (ISO 3166-1):")
        print(_AVAILABLE_LANGUAGES_PROMPT)
        while True:
          try:
            time.sleep(1)
            sys.stdout.flush()
            target_language = input(
                """\nEnter the target language in the ISO 3166-1 format (e.g. 'fr-FR'): """
            )
            self.target_language = target_language
            while True:
              time.sleep(1)
              sys.stdout.flush()
              spreadsheet_choice = input(
                  """\nDo you have a spreadsheet with the utterance metadata? (yes/no): """
              ).lower()
              if spreadsheet_choice == "yes":
                time.sleep(1)
                sys.stdout.flush()
                google_sheet_link = input(
                    """\nPlease provide the Google Sheet link: """
                )
                # We assume a user already authenticated themselves with
                # `auth.authenticate_user() (`from google.colab import auth`)
                self.original_language = target_language
                utterance_metadata_df = (
                    colab_utils.get_google_sheet_as_dataframe(google_sheet_link)
                )
                converted_utterance_metadata_df = (
                    colab_utils.convert_utterance_metadata(
                        utterance_metadata_df
                    )
                )
                utterance_metadata = converted_utterance_metadata_df.to_dict(
                    "records"
                )
                self.dub_ad_with_utterance_metadata(
                    utterance_metadata=utterance_metadata,
                )
                break
              elif spreadsheet_choice == "no":
                logging.warning(
                    "The script will be translated by Ariel. Typically"
                    " advertisers dub ads with utterance metadata where the"
                    " translations are verified by copywriters beforehand."
                )
                self.dub_ad_with_different_language(target_language)
                break
              else:
                print("Invalid choice.")
            break
          except ValueError:
            print(
                "Invalid language format. Please use the ISO 3166-1 format"
                " (e.g., 'fr-FR')."
            )
        break
      elif dub_to_another_language_choice == "no":
        break
      else:
        print("Invalid choice.")

  def run_text_to_speech(self) -> None:
    """Converts translated text to speech and dubs utterances with Google's Text-To-Speech.

    Returns:
        Updated utterance metadata with generated speech file paths.
    """
    self.text_to_speech = text_to_speech.TextToSpeech(
        client=self.text_to_speech_client,
        utterance_metadata=self.utterance_metadata,
        output_directory=self.output_directory,
        target_language=self.target_language,
        preprocessing_output=dataclasses.asdict(self.preprocessing_output),
        use_elevenlabs=self.use_elevenlabs,
        elevenlabs_model=self.elevenlabs_model,
        elevenlabs_clone_voices=self.elevenlabs_clone_voices,
        keep_voice_assignments=self.keep_voice_assignments,
        voice_assignments=self.voice_assignments,
    )
    self.utterance_metadata, cloned_voice_assignments = (
        self.text_to_speech.dub_all_utterances()
    )
    if self.elevenlabs_clone_voices and not self.voice_assignments:
      self.voice_assignments = cloned_voice_assignments
    logging.info("Completed converting text to speech.")
    self.progress_bar.update()

  def _prompt_if_dub_to_another_language(self) -> None:
    """Asks the user if they want to dub the ad to another language and runs the process if yes."""
    while True:
      time.sleep(1)
      sys.stdout.flush()
      dub_to_another_language_choice = input(
          """\nWould you like to dub the ad to another language? (yes/no): """
      ).lower()
      if dub_to_another_language_choice == "yes":
        clear_output(wait=True)
        time.sleep(1)
        sys.stdout.flush()
        print("\nAvailable language formats (ISO 3166-1):")
        print(_AVAILABLE_LANGUAGES_PROMPT)
        while True:
          try:
            time.sleep(1)
            sys.stdout.flush()
            target_language = input(
                """\nEnter the target language in the ISO 3166-1 format (e.g. 'fr-FR'): """
            )
            self.dub_ad_with_different_language(target_language=target_language)
            break
          except ValueError:
            print(
                "Invalid language format. Please use the ISO 3166-1 format"
                " (e.g., 'fr-FR')."
            )
        break
      elif dub_to_another_language_choice == "no":
        break
      else:
        print("Invalid choice.")

  def run_postprocessing(self) -> None:
    """Merges dubbed audio with the original background audio and video (if applicable).

    Returns:
        Path to the final dubbed output file (audio or video).
    """

    dubbed_audio_vocals_file = audio_processing.insert_audio_at_timestamps(
        utterance_metadata=self.utterance_metadata,
        background_audio_file=self.preprocessing_output.audio_background_file
        if self.preprocessing_output.audio_background_file
        else self.preprocessing_output.audio_file,
        output_directory=self.output_directory,
    )
    dubbed_audio_file = audio_processing.merge_background_and_vocals(
        background_audio_file=self.preprocessing_output.audio_background_file
        if self.preprocessing_output.audio_background_file
        else self.preprocessing_output.audio_file,
        dubbed_vocals_audio_file=dubbed_audio_vocals_file,
        output_directory=self.output_directory,
        target_language=self.target_language,
        vocals_volume_adjustment=self.vocals_volume_adjustment,
        background_volume_adjustment=self.background_volume_adjustment,
    )
    if self.is_video:
      if not self.preprocessing_output.video_file:
        raise ValueError(
            "A video file must be provided if the input file is a video."
        )
      dubbed_video_file = video_processing.combine_audio_video(
          video_file=self.preprocessing_output.video_file,
          dubbed_audio_file=dubbed_audio_file,
          output_directory=self.output_directory,
          target_language=self.target_language,
      )
    self.postprocessing_output = PostprocessingArtifacts(
        audio_file=dubbed_audio_file,
        video_file=dubbed_video_file if self.is_video else None,
    )
    logging.info("Completed postprocessing.")
    self.progress_bar.update()

  def run_save_utterance_metadata(self) -> None:
    """Saves a Python dictionary to a JSON file.

    Returns:
      A path to the saved uttterance metadata.
    """
    target_language_suffix = (
        "_" + self.target_language.replace("-", "_").lower()
    )
    utterance_metadata_file = os.path.join(
        self.output_directory,
        _OUTPUT,
        _UTTERNACE_METADATA_FILE_NAME + target_language_suffix + ".json",
    )
    try:
      with open(utterance_metadata_file, "w", encoding="utf-8") as json_file:
        json.dump(
            self.utterance_metadata, json_file, ensure_ascii=False, indent=4
        )
      logging.info(
          "Utterance metadata saved successfully to"
          f" '{utterance_metadata_file}'"
      )
    except Exception as e:
      logging.warning(f"Error saving utterance metadata: {e}")
    self.save_utterance_metadata_output = utterance_metadata_file

  def run_clean_directory(self) -> None:
    """Removes all files and directories from a directory, except for those listed in keep_files."""
    output_folder = os.path.join(self.output_directory, _OUTPUT)
    output_files = tf.io.gfile.listdir(output_folder)
    keep_files = [os.path.join(output_folder, file) for file in output_files]
    keep_files.append(output_folder)
    for item in tf.io.gfile.listdir(self.output_directory):
      item_path = os.path.join(self.output_directory, item)
      if item in keep_files:
        continue
      try:
        if tf.io.gfile.isdir(item_path):
          shutil.rmtree(item_path)
        else:
          tf.io.gfile.remove(item_path)
      except OSError as e:
        logging.error(f"Error deleting {item_path}: {e}")
    logging.info("Temporary artifacts are now removed.")

  def dub_ad(self) -> PostprocessingArtifacts:
    """Orchestrates the entire ad dubbing process."""
    self._verify_api_access()
    logging.info("Dubbing process starting...")
    self.progress_bar = tqdm(total=_NUMBER_OF_STEPS, initial=1)
    start_time = time.time()
    self.run_preprocessing()
    self.run_speech_to_text()
    self.run_translation()
    if self.with_verification:
      self._run_verify_utterance_metadata()
      clear_output(wait=True)
    self.run_configure_text_to_speech()
    if self.with_verification:
      self._prompt_for_verification_after_voice_configured()
    self.run_text_to_speech()
    if self.with_verification:
      self._prompt_for_dubbed_utterances_verification()
    self.run_postprocessing()
    if self.with_verification:
      self._prompt_for_output_preview()
    self.run_save_utterance_metadata()
    self.postprocessing_output.utterance_metadata = (
        self.save_utterance_metadata_output
    )
    subtitles_path = translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
        target_language=self.target_language,
    )
    self.postprocessing_output.subtitles = subtitles_path
    if self.clean_up:
      self.run_clean_directory()
    if self.elevenlabs_clone_voices and self.elevenlabs_remove_cloned_voices:
      self.text_to_speech.remove_cloned_elevenlabs_voices()
    self.progress_bar.close()
    logging.info("Dubbing process finished.")
    end_time = time.time()
    logging.info("Total execution time: %.2f seconds.", end_time - start_time)
    logging.info("Output files saved in: %s.", self.output_directory)
    self._prompt_if_dub_to_another_language()
    return self.postprocessing_output

  def generate_utterance_metadata(self) -> Sequence[Mapping[str, str | float]]:
    """Returns utterance metadata for a user to edit in the UI."""
    self._verify_api_access()
    logging.info("Generating utterance metadata starting...")
    self.progress_bar = tqdm(
        total=_NUMBER_OF_STEPS_GENERATE_UTTERANCE_METADATA, initial=1
    )
    self.run_preprocessing()
    self.run_speech_to_text()
    self.run_translation()
    self.run_configure_text_to_speech()
    self.run_save_utterance_metadata()
    self.progress_bar.close()
    logging.info("Generating utterance metadata finished.")
    return self.utterance_metadata

  def dub_ad_with_utterance_metadata(
      self,
      *,
      utterance_metadata: str | Sequence[Mapping[str, str | float]],
      preprocessing_artifacts: PreprocessingArtifacts | None = None,
      overwrite_utterance_metadata: bool = True,
  ) -> PostprocessingArtifacts:
    """Orchestrates the complete ad dubbing process using utterance metadata.

    Takes utterance metadata as input, performs the required dubbing steps, and
    returns the post-processed results.

    Args:
        utterance_metadata: A path to the JSON file with the utterance metadata
          from the previous run. Or a sequence of mappings detailing each
          utterance's metadata. If not provided, uses `self.utterance_metadata`.
          Each mapping should contain: * 'path': Audio file path (str). *
          'start', 'end': Utterance start/end times in seconds (float). *
          'text', 'translated_text': Original and translated text (str). *
          'for_dubbing': Whether to dub this utterance (bool). * 'speaker_id':
          Speaker identifier (str). * 'ssml_gender': Text-to-speech voice gender
          (str). * 'assigned_voice': Google/ElevenLabs voice name (str). *
          Google TTS-specific: 'pitch', 'speed', 'volume_gain_db' (float). *
          ElevenLabs TTS-specific: 'stability', 'similarity_boost', 'style'
          (float), 'use_speaker_boost' (bool).
        preprocessing_artifacts: Required only if dubbing ads from utterance
          metadata in a new class instance.
        overwrite_utterance_metadata: If the exisitng utterance metadata file
          should be reaplced with an updated one.

    Returns:
        PostprocessingArtifacts: Object containing the post-processed results.

    Raises:
      ValueError: When `preprocessing_artifacts` argument is not provided and
         the method is run using a new instance class.
    """
    self._verify_api_access()
    logging.info("Dubbing from utterance metadata process starting...")
    self._dubbing_from_utterance_metadata = True
    if isinstance(utterance_metadata, str):
      with open(utterance_metadata, "r", encoding="utf-8") as json_file:
        utterance_metadata = json.load(json_file)
    self.utterance_metadata = utterance_metadata
    logging.warning(
        "The class utterance metadata was overwritten with the provided input."
    )
    if not check_directory_contents(self.output_directory):
      logging.info("Dubbing from utterance metadata process starting...")
      self.progress_bar = tqdm(
          total=_NUMBER_OF_STEPS_DUB_AD_WITH_UTTERANCE_METADATA + 1, initial=1
      )
      self.run_preprocessing()
    else:
      if preprocessing_artifacts:
        self.preprocessing_output = preprocessing_artifacts
        self.progress_bar = tqdm(
            total=_NUMBER_OF_STEPS_DUB_AD_WITH_UTTERANCE_METADATA, initial=1
        )
      elif (
          not hasattr(self, "preprocessing_output")
          and not preprocessing_artifacts
      ):
        raise ValueError(
            "You need to provide 'preprocessing_artifacts' argument "
            "in a new class instance."
        )
    if self.with_verification:
      self._run_verify_utterance_metadata()
      clear_output(wait=True)
    self.run_text_to_speech()
    if self.with_verification:
      self._prompt_for_dubbed_utterances_verification()
    self.run_postprocessing()
    if self.with_verification:
      self._prompt_for_output_preview()
    if overwrite_utterance_metadata:
      self.run_save_utterance_metadata()
    self.postprocessing_output.utterance_metadata = (
        self.save_utterance_metadata_output
    )
    subtitles_path = translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
        target_language=self.target_language,
    )
    self.postprocessing_output.subtitles = subtitles_path
    if self.elevenlabs_clone_voices and self.elevenlabs_remove_cloned_voices:
      self.text_to_speech.remove_cloned_elevenlabs_voices()
    self.progress_bar.close()
    if self.with_verification:
      self._prompt_if_dub_to_another_language_from_utterance_metadata()
    self._dubbing_from_utterance_metadata = False
    logging.info("Dubbing process finished.")
    logging.info("Output files saved in: %s.", self.output_directory)
    return self.postprocessing_output

  def dub_ad_with_different_language(
      self, target_language: str
  ) -> PostprocessingArtifacts:
    """Orchestrates the complete ad dubbing process using a new target language.

    Args:
        target_language: The new language to dub the ad into. It must be ISO
          3166-1 alpha-2 country code, e.g. 'en-US'.

    Returns:
        PostprocessingArtifacts: Object containing the post-processed results.
    """

    logging.info("Re-run dubbing process starting...")
    if self.clean_up:
      logging.warning(
          "You are trying to run the dubbing process using utterance metadata."
          " But it looks like you have cleaned up all the process artifacts"
          " during the last run. They might not be available now and the"
          " process might not complete successfully."
      )
    self.target_language = target_language
    logging.warning(
        "The class target language was overwritten with the provided input."
    )
    self.progress_bar = tqdm(
        total=_NUMBER_OF_STEPS_DUB_AD_WITH_DIFFERENT_LANGUAGE, initial=1
    )
    self.run_translation()
    if self.with_verification:
      if not self._run_from_script:
        self._run_verify_utterance_metadata()
      else:
        self._run_verify_utterance_metadata_script_workflow()
      clear_output(wait=True)
    self.run_configure_text_to_speech(dubbing_to_another_language=True)
    if self.with_verification:
      self._prompt_for_verification_after_voice_configured()
    self.run_text_to_speech()
    if self.with_verification:
      self._prompt_for_dubbed_utterances_verification()
    self.run_postprocessing()
    if self.with_verification:
      self._prompt_for_output_preview()
    self.run_save_utterance_metadata()
    self.postprocessing_output.utterance_metadata = (
        self.save_utterance_metadata_output
    )
    subtitles_path = translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
        target_language=self.target_language,
    )
    self.postprocessing_output.subtitles = subtitles_path
    if self.elevenlabs_clone_voices and self.elevenlabs_remove_cloned_voices:
      self.text_to_speech.remove_cloned_elevenlabs_voices()
    self.progress_bar.close()
    if self._dubbing_from_utterance_metadata:
      self._prompt_if_dub_to_another_language_from_utterance_metadata()
    elif self._run_from_script:
      self._prompt_if_dub_to_another_language_from_script()
    else:
      self._prompt_if_dub_to_another_language()
    logging.info("Dubbing process finished.")
    logging.info("Output files saved in: %s.", self.output_directory)
    return self.postprocessing_output

  def dub_ad_from_script(
      self,
      *,
      script_with_timestamps: Sequence[Mapping[str, str | float]],
      google_text_to_speech_parameters: (
          Mapping[str, str | float] | Sequence[Mapping[str, str | float]]
      ) = {"pitch": -5.0, "speed": 1.0, "volume_gain_db": 16.0},
      elevenlabs_text_to_speech_parameters: (
          Mapping[str, str | float] | Sequence[Mapping[str, str | float]]
      ) = {
          "stability": 0.5,
          "similarity_boost": 0.75,
          "style": 0.0,
          "use_speaker_boost": True,
      },
  ) -> PostprocessingArtifacts:
    """Orchestrates the complete ad dubbing process from a script with timestamps.

    This method takes a script with timestamps, and performs the
    following steps:

    1. Prepares utterance metadata for dubbing based on the script.
    2. Runs preprocessing steps on the script.
    3. Performs translation of the script if necessary.
    4. Verifies utterance metadata (optional).
    5. Synthesizes speech using either Google Text-to-Speech or ElevenLabs.
    6. Executes post-processing tasks on the synthesized speech.

    Args:
        script_with_timestamps: A sequence of mappings detailing each
          utterance's metadata.
        google_text_to_speech_parameters: Parameters for Google Text-to-Speech
          synthesis.
        elevenlabs_text_to_speech_parameters: Parameters for ElevenLabs
          Text-to-Speech synthesis.

    Returns:
        PostprocessingArtifacts: An object containing the post-processed dubbing
        results.
    """

    logging.info("Dubbing process from script starting...")
    self._run_from_script = True
    self.progress_bar = tqdm(
        total=_NUMBER_OF_STEPS_DUB_AD_FROM_SCRIPT, initial=1
    )
    if self.use_elevenlabs and self.elevenlabs_clone_voices:
      logging.warning(
          "Voices won't be cloned when dubbing from script. You can only use"
          " off-the-shelf voices (e.g. 'Charlie') from ElevenLabs."
      )
      self.elevenlabs_clone_voices = False
    self.utterance_metadata = assemble_utterance_metadata_for_dubbing_from_script(
        script_with_timestamps=script_with_timestamps,
        use_elevenlabs=self.use_elevenlabs,
        google_text_to_speech_parameters=google_text_to_speech_parameters,
        elevenlabs_text_to_speech_parameters=elevenlabs_text_to_speech_parameters,
    )
    self.run_preprocessing_for_dubbing_from_script()
    updated_utterance_metadata = []
    for utterance in self.utterance_metadata:
      utterance_copy = utterance.copy()
      utterance_copy["translated_text"] = utterance_copy["text"]
      updated_utterance_metadata.append(utterance_copy)
      self.utterance_metadata = updated_utterance_metadata
    if self.with_verification:
      self._run_verify_utterance_metadata_script_workflow()
      clear_output(wait=True)
      print("Please wait...")
    self.run_text_to_speech()
    if self.with_verification:
      self._prompt_for_dubbed_utterances_verification()
    self.run_postprocessing()
    if self.with_verification:
      self._prompt_for_output_preview()
    self.run_save_utterance_metadata()
    self.postprocessing_output.utterance_metadata = (
        self.save_utterance_metadata_output
    )
    subtitles_path = translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
        target_language=self.target_language,
    )
    self.postprocessing_output.subtitles = subtitles_path
    if self.clean_up:
      self.run_clean_directory()
    self.progress_bar.close()
    logging.info("Dubbing process finished.")
    logging.info("Output files saved in: %s.", self.output_directory)
    if self.with_verification:
      self._prompt_if_dub_to_another_language_from_script()
    self._run_from_script = False
    return self.postprocessing_output

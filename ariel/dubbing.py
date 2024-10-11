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
import functools
import importlib.resources
import json
import os
import re
import readline
import shutil
import tempfile
import time
from typing import Final, Mapping, Sequence
from absl import logging
from ariel import audio_processing
from ariel import speech_to_text
from ariel import text_to_speech
from ariel import translation
from ariel import video_processing
from elevenlabs.client import ElevenLabs
from elevenlabs.core import ApiError
from faster_whisper import WhisperModel
from google.api_core.exceptions import BadRequest, ServiceUnavailable
from google.cloud import texttospeech
import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from IPython.display import Audio
from IPython.display import clear_output
from IPython.display import display
from IPython.display import HTML
from pyannote.audio import Pipeline
import tensorflow as tf
import torch
from tqdm import tqdm

_ACCEPTED_VIDEO_FORMATS: Final[tuple[str, ...]] = (".mp4",)
_ACCEPTED_AUDIO_FORMATS: Final[tuple[str, ...]] = (".wav", ".mp3", ".flac")
_UTTERNACE_METADATA_FILE_NAME: Final[str] = "utterance_metadata"
_EXPECTED_HUGGING_FACE_ENVIRONMENTAL_VARIABLE_NAME: Final[str] = (
    "HUGGING_FACE_TOKEN"
)
_EXPECTED_GEMINI_ENVIRONMENTAL_VARIABLE_NAME: Final[str] = "GEMINI_TOKEN"
_EXPECTED_ELEVENLABS_ENVIRONMENTAL_VARIABLE_NAME: Final[str] = (
    "ELEVENLABS_TOKEN"
)
_DEFAULT_PYANNOTE_MODEL: Final[str] = "pyannote/speaker-diarization-3.1"
_DEFAULT_ELEVENLABS_MODEL: Final[str] = "eleven_multilingual_v2"
_DEFAULT_TRANSCRIPTION_MODEL: Final[str] = "large-v3"
_DEFAULT_GEMINI_MODEL: Final[str] = "gemini-1.5-flash"
_DEFAULT_GEMINI_TEMPERATURE: Final[float] = 1.0
_DEFAULT_GEMINI_TOP_P: Final[float] = 0.95
_DEFAULT_GEMINI_TOP_K: Final[int] = 64
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
_NUMBER_OF_STEPS_DUB_AD_FROM_SCRIPT: Final[int] = 4
_MAX_GEMINI_RETRIES: Final[int] = 5
_EDIT_TRANSLATION_PROMPT: Final[str] = (
    "You were hired by a company called: '{}'. The received script was: '{}'."
    " You translated it as: '{}'. The target language was: '{}'. The company"
    " asks you to modify this translation: '{}'"
)
_REQUIRED_KEYS: Final[set] = {"text", "start", "end"}
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
_LOCKED_KEYS: Final[str] = ("path", "dubbed_path")


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
  """

  audio_file: str
  video_file: str | None


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
    assigned_voice: str | Sequence[str],
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
        information about an utterance in the script: - "text": The text of the
        utterance. - "start": The start time of the utterance (in seconds). -
        "end": The end time of the utterance (in seconds).
      assigned_voice: The name of the assigned voice (or a list of names if each
        utterance has a different voice).
      use_elevenlabs: If True, use ElevenLabs TTS parameters; otherwise, use
        Google TTS parameters.
      google_text_to_speech_parameters: A dictionary or list of dictionaries
        with Google TTS parameters (only used if `use_elevenlabs` is False).
      elevenlabs_text_to_speech_parameters: A dictionary or list of dictionaries
        with ElevenLabs TTS parameters (only used if `use_elevenlabs` is True).

  Returns:
      A sequence of dictionaries, each containing enriched metadata for an
      utterance:
          - All keys from the original `script_with_timestamps` dictionaries.
          - "for_dubbing": Always set to True.
          - "assigned_voice": The assigned voice name.
          - Additional TTS parameters based on the `use_elevenlabs` flag and the
          corresponding parameter dictionaries.

  Raises:
      KeyError: If a dictionary in `script_with_timestamps` is missing "text",
      "start", or "end" keys.
      KeyError: If the specified TTS parameter dictionary is missing required
      keys.

  Example:
      ```python
      script = [
          {"text": "Hello, world!", "start": 0.0, "end": 1.5},
          {"text": "This is a test.", "start": 2.0, "end": 3.8},
      ]
      metadata = assemble_utterance_metadata_for_dubbing_from_script(
          script_with_timestamps=script,
          assigned_voice=["Alice", "Bob"],
          use_elevenlabs=False,
          google_text_to_speech_parameters=[{"pitch": -2.0}, {"speed": 0.9}],
      )
      print(metadata)
      ```
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
  if not isinstance(assigned_voice, list):
    assigned_voice = [assigned_voice] * number_of_utterances
  utterance_metadata_with_assigned_voice = _add_items_to_dictionaries(
      utterance_metadata=utterance_metadata_with_for_dubbing,
      items=assigned_voice,
      key="assigned_voice",
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
      utterance_metadata=utterance_metadata_with_assigned_voice,
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
      number_of_speakers: int = 1,
      gemini_token: str | None = None,
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
        number_of_speakers: The exact number of speakers in the ad (including a
          lector if applicable).
        gemini_token: Gemini API token (can be set via 'GEMINI_TOKEN'
          environment variable).
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
    self.clean_up = clean_up
    self.pyannote_model = pyannote_model
    self.hugging_face_token = hugging_face_token
    self.gemini_token = gemini_token
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
  ) -> genai.GenerativeModel:
    """Configures the Gemini generative model.

    Args:
        system_instructions: The system instruction to guide the model's
          behavior.

    Returns:
        The configured Gemini model instance.
    """

    gemini_token = self.get_api_token(
        environmental_variable=_EXPECTED_GEMINI_ENVIRONMENTAL_VARIABLE_NAME,
        provided_token=self.gemini_token,
    )
    genai.configure(api_key=gemini_token)
    gemini_configuration = dict(
        temperature=self.temperature,
        top_p=self.top_p,
        top_k=self.top_k,
        max_output_tokens=self.max_output_tokens,
        response_mime_type=self.response_mime_type,
    )
    return genai.GenerativeModel(
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
    logging.info("Verifying access to Gemini.")
    try:
      gemini_token = self.get_api_token(
          environmental_variable=_EXPECTED_GEMINI_ENVIRONMENTAL_VARIABLE_NAME,
          provided_token=self.gemini_token,
      )
      genai.configure(api_key=gemini_token)
      genai.get_model(f"models/{_DEFAULT_GEMINI_MODEL}")
    except BadRequest:
      raise GeminiAccessError(
          "No access to Gemini. Make sure you passed the correct API token"
          " either as 'gemini_token' or through the"
          f" '{_EXPECTED_GEMINI_ENVIRONMENTAL_VARIABLE_NAME}' environmental"
          " variable."
      )
    logging.info("Access to Gemini verified.")
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
    demucs_command = audio_processing.build_demucs_command(
        audio_file=audio_file,
        output_directory=self.output_directory,
        device=self.device,
    )
    audio_vocals_file, audio_background_file = (
        audio_processing.assemble_split_audio_file_paths(command=demucs_command)
    )
    if tf.io.gfile.exists(audio_vocals_file) and tf.io.gfile.exists(
        audio_background_file
    ):
      logging.info(
          "The DEMUCS command will not be executed, because the expected files"
          f" {audio_vocals_file} and {audio_background_file} already exist."
      )
    else:
      audio_processing.execute_demucs_command(command=demucs_command)
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
    utterance_metadata = audio_processing.run_cut_and_save_audio(
        utterance_metadata=utterance_metadata,
        audio_file=audio_file,
        output_directory=self.output_directory,
    )
    self.utterance_metadata = utterance_metadata
    self.preprocessing_output = PreprocessingArtifacts(
        video_file=video_file,
        audio_file=audio_file,
        audio_vocals_file=audio_vocals_file,
        audio_background_file=audio_background_file,
    )
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
    attempt = 0
    success = False
    while attempt < _MAX_GEMINI_RETRIES and not success:
      try:
        speaker_info = speech_to_text.diarize_speakers(
            file=media_file,
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

  def run_configure_text_to_speech(self) -> None:
    """Configures the Text-To-Speech process.

    Returns:
        Updated utterance metadata with assigned voices
        and Text-To-Speech settings.
    """
    self._voice_assigner = text_to_speech.VoiceAssigner(
        utterance_metadata=self.utterance_metadata,
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
        utterance_metadata=self.utterance_metadata,
        assigned_voices=self.voice_assignments,
        use_elevenlabs=self.use_elevenlabs,
        elevenlabs_clone_voices=self.elevenlabs_clone_voices,
        adjust_speed=self.adjust_speed,
    )

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
    """Displays the current utterance metadata."""
    print("Current speech chunk (utterance) metadata:")
    for i, item in enumerate(utterance_metadata):
      print(f"{i+1}. {json.dumps(item, ensure_ascii=False, indent=2)}")

  def _add_utterance_metadata(self) -> Mapping[str, str | float]:
    """Allows adding a new utterance metadata entry, prompting for each field."""
    new_utterance = {}
    if self.elevenlabs_clone_voices:
      required_fields = ["start", "end", "speaker_id", "ssml_gender"]
    else:
      required_fields = [
          "start",
          "end",
          "speaker_id",
          "ssml_gender",
          "assigned_voice",
      ]
    for field in required_fields:
      while True:
        try:
          value = input(f"Enter value for '{field}': ")
          if field in ["start", "end"]:
            value = float(value)
            if (
                field == "end"
                and "start" in new_utterance
                and value <= new_utterance["start"]
            ):
              print("End time cannot be less than or equal to start time.")
              continue
          new_utterance[field] = value
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
        index = int(input("Enter item number to edit: ")) - 1
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
        key_to_modify = input(
            f"Enter the key you want to modify for utterance {edit_index + 1}: "
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
          new_value = input(f"Enter the new value for '{key_to_modify}': ")
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
              " value. Make sure it matches the orignal type, a float (e.g."
              " 0.01), a string (e.g. 'example') or a boolean (e.g. 'True')."
          )
      utterance[key_to_modify] = new_value
      while True:
        modify_more = input(
            "Do you want to modify anything else in this utterance? (yes/no): "
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
        index = (
            int(input("Enter item number to remove from the dubbing process: "))
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
      translate_choice = input(
          "\nYou modified 'text' of the utterance. Do you want to run"
          " translation (it's recommended after modifying the source utterance"
          " text)? (yes/no): "
      ).lower()
      if translate_choice in ("yes", "no"):
        return translate_choice
      else:
        print("Invalid choice.")

  def _verify_metadata_after_change(self):
    """Asks the user if they want to review the metadata again after changes."""
    while True:
      review_choice = input(
          "\nDo you want to review the metadata again? (yes/no): "
      ).lower()
      if review_choice in ("yes", "no"):
        return review_choice == "no"
      else:
        print("Invalid choice.")

  def _prompt_for_gemini_translation_chat(self) -> str:
    """Prompts the user if they want to chat with Gemini about a translation."""
    while True:
      gemini_translation_chat_choice = input(
          "\nWould you like to chat with Gemini about a translation? (yes/no): "
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
      user_message = input(
          "Type your message to Gemini about the translation. Or type in 'exit'"
          " to approve the translation and to exit the chat: "
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
    try:
      edit_translation_chat_session.rewind()
    except IndexError:
      pass
    edited_utterance["translated_text"] = updated_translation
    return edited_utterance

  def _bulk_edit_utterance_metadata(
      self, utterance_metadata: Sequence[Mapping[str, str | float]]
  ) -> Sequence[Mapping[str, str | float]]:
    """Allows bulk editing of utterance metadata entries."""
    while True:
      try:
        indices_str = input("Enter item numbers to edit (comma-separated): ")
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
        updates_str = input("Enter updates as a JSON dictionary: ")
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
    clear_output()
    self._display_utterance_metadata(self.utterance_metadata)
    while True:
      verify_voices_choice = input(
          "\nVoices and voice properties were added to the utterance metadata"
          " above. Would you like to edit them before the process completes?"
          " (yes/no): "
      ).lower()
      if verify_voices_choice == "yes":
        self._run_verify_utterance_metadata(with_verification=False)
        clear_output()
        break
      elif verify_voices_choice == "no":
        clear_output()
        print("Please wait...")
        break
      else:
        print("Invalid choice.")

  def _verify_and_redub_utterances(self) -> None:
    """Verifies and allows re-dubbing of utterances."""
    original_metadata = self.utterance_metadata.copy()
    self._run_verify_utterance_metadata(with_verification=False)
    clear_output()
    edited_utterances = self.text_to_speech.dub_edited_utterances(
        original_utterance_metadata=original_metadata,
        updated_utterance_metadata=self.utterance_metadata,
    )
    updated_utterance_metadata = self.utterance_metadata.copy()
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
      verify_dubbed_utterances_choice = input(
          "\nUtterances have been dubbed. Would you like to listen to "
          "them? (yes/no): "
      ).lower()
      if verify_dubbed_utterances_choice == "yes":
        clear_output()
        for i, utterance in enumerate(self.utterance_metadata):
          if utterance.get("dubbed_path"):
            print(
                f"{i+1}. Playing speech chunk (utterance):"
                f" {utterance.get('translated_text')}"
            )
            display(Audio(utterance["dubbed_path"]))
        break
      elif verify_dubbed_utterances_choice == "no":
        break
      else:
        print("Invalid choice.")
    while True:
      verify_again_choice = input(
          "\nWould you like to edit and re-dub the edited speech chunks"
          " (utterances) again? (yes/no): "
      ).lower()
      if verify_again_choice == "yes":
        self._verify_and_redub_utterances()
        self._prompt_for_dubbed_utterances_verification()
        break
      elif verify_again_choice == "no":
        clear_output()
        print("Please wait...")
        break
      else:
        print("Invalid choice.")

  def _prompt_for_output_preview(self) -> None:
    """Prompts the user to preview the output video/audio after postprocessing."""
    while True:
      preview_choice = input(
          "\nPostprocessing is complete. Would you like to preview the dubbed "
          "output? (yes/no): "
      ).lower()
      if preview_choice == "yes":
        print("Previewing the dubbed output:")
        if self.is_video:
          output_video_path = self.postprocessing_output.video_file
          video_html = f"""
          <video width="640" height="480" controls>
              <source src="{output_video_path}" type="video/mp4">
          </video>
          """
          display(HTML(video_html))
        else:
          output_audio_path = self.postprocessing_output.audio_file
          display(Audio(output_audio_path))
        break
      elif preview_choice == "no":
        break
      else:
        print("Invalid choice.")
    while True:
      change_choice = input(
          "\nDo you want to change anything in the dubbed output? (yes/no): "
      ).lower()
      if change_choice == "yes":
        clear_output()
        if self.with_verification:
          self._verify_and_redub_utterances()
        print("Please wait...")
        self.run_postprocessing()
        if self.with_verification:
          self._prompt_for_dubbed_utterances_verification()
        self._prompt_for_output_preview()
        break
      elif change_choice == "no":
        clear_output()
        break
      else:
        print("Invalid choice.")

  def _run_verify_utterance_metadata(
      self, with_verification: bool = True
  ) -> None:
    """Displays, allows editing, adding and removing utterance metadata.

    Args:
        with_verification: A boolean indicating whether to ask for the final
          verification.
    """
    utterance_metadata = self.utterance_metadata
    clear_output()
    while True:
      self._display_utterance_metadata(utterance_metadata)
      action_choice = input(
          "\nChoose action: (edit/bulk_edit/add/remove/continue): "
      ).lower()
      if action_choice in ("edit", "bulk_edit", "add", "remove"):
        if action_choice == "edit":
          edit_index = self._select_edit_number(
              utterance_metadata=utterance_metadata
          )
          unmodified_start_end = (
              utterance_metadata[edit_index]["start"],
              utterance_metadata[edit_index]["end"],
          )
          unmodified_text = utterance_metadata[edit_index]["text"]
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
          modified_start_end = (
              edited_utterance["start"],
              edited_utterance["end"],
          )
          modified_text = edited_utterance["text"]
          if unmodified_start_end != modified_start_end:
            edited_utterance = self._repopulate_metadata(
                utterance=edited_utterance
            )
          if unmodified_text != modified_text:
            translate_choice = self._prompt_for_translation()
            if translate_choice == "yes":
              edited_utterance = self._run_translation_on_single_utterance(
                  edited_utterance
              )
          utterance_metadata = self._update_utterance_metadata(
              updated_utterance=edited_utterance,
              utterance_metadata=utterance_metadata,
              edit_index=edit_index,
          )
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
        clear_output()
      elif action_choice == "continue":
        self.utterance_metadata = utterance_metadata
        clear_output()
        return
      else:
        clear_output()
        print("Option unavailable or you had a typo. Try again.")

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
        adjust_speed=self.adjust_speed,
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
      json_data = json.dumps(
          self.utterance_metadata, ensure_ascii=False, indent=4
      )
      with tempfile.NamedTemporaryFile(
          mode="w", delete=False, encoding="utf-8"
      ) as temporary_file:
        json.dump(json_data, temporary_file, ensure_ascii=False)
        temporary_file.flush()
        os.fsync(temporary_file.fileno())
      tf.io.gfile.copy(
          temporary_file.name, utterance_metadata_file, overwrite=True
      )
      os.remove(temporary_file.name)
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
      clear_output()
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
    translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
    )
    if self.clean_up:
      self.run_clean_directory()
    if self.elevenlabs_clone_voices and self.elevenlabs_remove_cloned_voices:
      self.text_to_speech.remove_cloned_elevenlabs_voices()
    self.progress_bar.close()
    logging.info("Dubbing process finished.")
    end_time = time.time()
    logging.info("Total execution time: %.2f seconds.", end_time - start_time)
    logging.info("Output files saved in: %s.", self.output_directory)
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
      utterance_metadata: Sequence[Mapping[str, str | float]],
      preprocessing_artifacts: PreprocessingArtifacts | None = None,
      overwrite_utterance_metadata: bool = False,
  ) -> PostprocessingArtifacts:
    """Orchestrates the complete ad dubbing process using utterance metadata.

    Takes utterance metadata as input, performs the required dubbing steps, and
    returns the post-processed results.

    Args:
        utterance_metadata: A sequence of mappings detailing each utterance's
          metadata. If not provided, uses `self.utterance_metadata`. Each
          mapping should contain: * 'path': Audio file path (str). * 'start',
          'end': Utterance start/end times in seconds (float). * 'text',
          'translated_text': Original and translated text (str). *
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

    logging.info("Re-run dubbing process starting...")
    if self.clean_up:
      logging.warning(
          "You are trying to run the dubbing process using utterance metadata."
          " But it looks like you have cleaned up all the process artifacts"
          " during the last run. They might not be available now and the"
          " process might not complete successfully."
      )
    if utterance_metadata:
      self.utterance_metadata = utterance_metadata
    logging.warning(
        "The class utterance metadata was overwritten with the provided input."
    )
    if not hasattr(self, "preprocessing_output") and preprocessing_artifacts:
      self.preprocessing_output = preprocessing_artifacts
    elif (
        not hasattr(self, "preprocessing_output")
        and not preprocessing_artifacts
    ):
      raise ValueError(
          "You need to provide 'preprocessing_artifacts' argument "
          "in a new class instance."
      )
    self.progress_bar = tqdm(
        total=_NUMBER_OF_STEPS_DUB_AD_WITH_UTTERANCE_METADATA, initial=1
    )
    if self.with_verification:
      self._run_verify_utterance_metadata()
      clear_output()
    self.run_text_to_speech()
    if self.with_verification:
      self._prompt_for_dubbed_utterances_verification()
    self.run_postprocessing()
    if self.with_verification:
      self._prompt_for_output_preview()
    if overwrite_utterance_metadata:
      self.run_save_utterance_metadata()
    translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
    )
    if self.elevenlabs_clone_voices and self.elevenlabs_remove_cloned_voices:
      self.text_to_speech.remove_cloned_elevenlabs_voices()
    self.progress_bar.close()
    logging.info("Dubbing process finished.")
    logging.info("Output files saved in: %s.", self.output_directory)
    return self.postprocessing_output

  def dub_ad_with_different_language(
      self, target_language: str, overwrite_utterance_metadata: bool = False
  ) -> PostprocessingArtifacts:
    """Orchestrates the complete ad dubbing process using a new target language.

    Args:
        target_language: The new language to dub the ad into. It must be ISO
          3166-1 alpha-2 country code, e.g. 'en-US'.
        overwrite_utterance_metadata: If the exisitng utterance metadata file
          should be reaplced with an updated one.

    Returns:
        PostprocessingArtifacts: Object containing the post-processed results.
    """

    logging.info("Re-run dubbing process starting...")
    self.target_language = target_language
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
      self._run_verify_utterance_metadata()
      clear_output()
    self.run_configure_text_to_speech()
    if self.with_verification:
      self._prompt_for_verification_after_voice_configured()
    self.run_text_to_speech()
    if self.with_verification:
      self._prompt_for_dubbed_utterances_verification()
    self.run_postprocessing()
    if self.with_verification:
      self._prompt_for_output_preview()
    if overwrite_utterance_metadata:
      self.run_save_utterance_metadata()
    translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
    )
    if self.elevenlabs_clone_voices and self.elevenlabs_remove_cloned_voices:
      self.text_to_speech.remove_cloned_elevenlabs_voices()
    self.progress_bar.close()
    logging.info("Dubbing process finished.")
    logging.info("Output files saved in: %s.", self.output_directory)
    return self.postprocessing_output

  def dub_ad_from_script(
      self,
      *,
      script_with_timestamps: Sequence[Mapping[str, str | float]],
      assigned_voice: str | Sequence[str],
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

    This method takes a script with timestamps, assigns voices, and performs the
    following steps:

    1. Prepares utterance metadata for dubbing based on the script.
    2. Runs preprocessing steps on the script.
    3. Performs translation of the script if necessary.
    4. Verifies utterance metadata (optional).
    5. Synthesizes speech using either Google Text-to-Speech or ElevenLabs.
    6. Executes post-processing tasks on the synthesized speech.

    Args:
        script_with_timestamps: A sequence of mappings detailing each
          utterance's metadata. Each mapping should contain: * 'start', 'end':
          Utterance start/end times in seconds (float). * 'text': The text
          content of the utterance.
        assigned_voice: The name of the assigned voice(s) for the utterances
          (either a single string or a sequence of strings).
        google_text_to_speech_parameters: Parameters for Google Text-to-Speech
          synthesis.
        elevenlabs_text_to_speech_parameters: Parameters for ElevenLabs
          Text-to-Speech synthesis.

    Returns:
        PostprocessingArtifacts: An object containing the post-processed dubbing
        results.
    """

    logging.info("Dubbing process from script starting...")
    if self.original_language != self.target_language:
      number_of_steps = _NUMBER_OF_STEPS_DUB_AD_FROM_SCRIPT
    else:
      number_of_steps = _NUMBER_OF_STEPS_DUB_AD_FROM_SCRIPT - 1
    self.progress_bar = tqdm(total=number_of_steps, initial=1)
    if self.use_elevenlabs and self.elevenlabs_clone_voices:
      logging.warning(
          "Voices won't be cloned when dubbing from script. You can only use"
          " off-the-shelf voices (e.g. 'Charlie') from ElevenLabs."
      )
      self.elevenlabs_clone_voices = False
    self.utterance_metadata = assemble_utterance_metadata_for_dubbing_from_script(
        script_with_timestamps=script_with_timestamps,
        assigned_voice=assigned_voice,
        use_elevenlabs=self.use_elevenlabs,
        google_text_to_speech_parameters=google_text_to_speech_parameters,
        elevenlabs_text_to_speech_parameters=elevenlabs_text_to_speech_parameters,
    )
    self.run_preprocessing_for_dubbing_from_script()
    if self.original_language != self.target_language:
      self.run_translation()
    else:
      updated_utterance_metadata = []
      for utterance in self.utterance_metadata:
        utterance_copy = utterance.copy()
        utterance_copy["translated_text"] = utterance_copy["text"]
        updated_utterance_metadata.append(utterance_copy)
        self.utterance_metadata = updated_utterance_metadata
    if self.with_verification:
      self._run_verify_utterance_metadata()
      clear_output()
    self.run_text_to_speech()
    if self.with_verification:
      self._prompt_for_dubbed_utterances_verification()
    self.run_postprocessing()
    if self.with_verification:
      self._prompt_for_output_preview()
    self.run_save_utterance_metadata()
    translation.save_srt_subtitles(
        utterance_metadata=self.utterance_metadata,
        output_directory=os.path.join(self.output_directory, _OUTPUT),
    )
    if self.clean_up:
      self.run_clean_directory()
    self.progress_bar.close()
    logging.info("Dubbing process finished.")
    logging.info("Output files saved in: %s.", self.output_directory)
    return self.postprocessing_output

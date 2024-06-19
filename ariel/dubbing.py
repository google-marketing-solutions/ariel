"""A dubbing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import dataclasses
import functools
import json
import os
import pathlib
import shutil
from typing import Final, Mapping, Sequence
from absl import logging
from ariel import audio_processing
from ariel import speech_to_text
from ariel import text_to_speech
from ariel import translation
from ariel import video_processing
from faster_whisper import WhisperModel
from google.cloud import texttospeech
import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from pyannote.audio import Pipeline
import torch


_ACCEPTED_VIDEO_FORMATS: Final[tuple[str, ...]] = (".mp4",)
_ACCEPTED_AUDIO_FORMATS: Final[tuple[str, ...]] = (".wav", ".mp3", ".flac")
_UTTERNACE_METADATA_FILE_NAME: Final[str] = "utterance_metadata.json"
_DEFAULT_PYANNOTE_MODEL: Final[str] = "pyannote/speaker-diarization-3.1"
_DEFAULT_TRANSCRIPTION_MODEL: Final[str] = "large-v3"
_DEVICE: Final[str] = "gpu" if torch.cuda.is_available() else "cpu"
_TRANSCRIPTION_COMPUTE_TYPE: Final[str] = (
    "float16" if _DEVICE == "gpu" else "int8"
)
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
        HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    ),
    HarmCategory.HARM_CATEGORY_HARASSMENT: (
        HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    ),
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: (
        HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    ),
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: (
        HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    ),
}
module_path = pathlib.Path(__file__).parent.resolve()
_DEFAULT_DIARIZATION_SYSTEM_SETTINGS: Final[str] = os.path.join(
    module_path.parent, "assets", "system_settings_diarization.txt"
)
_DEFAULT_TRANSLATION_SYSTEM_SETTINGS: Final[str] = os.path.join(
    module_path.parent, "assets", "system_settings_translation.txt"
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
      diarization_instructions: str | None = None,
      translation_instructions: str | None = None,
      merge_utterances: bool = True,
      minimum_merge_threshold: float = 0.001,
      preferred_voices: Sequence[str] | None = None,
      clean_up: bool = True,
      pyannote_model: str = _DEFAULT_PYANNOTE_MODEL,
      diarization_system_instructions: str = _DEFAULT_DIARIZATION_SYSTEM_SETTINGS,
      translation_system_instructions: str = _DEFAULT_TRANSLATION_SYSTEM_SETTINGS,
      hugging_face_token: str | None = None,
      gemini_token: str | None = None,
      model_name: str = _DEFAULT_GEMINI_MODEL,
      temperature: float = _DEFAULT_GEMINI_TEMPERATURE,
      top_p: float = _DEFAULT_GEMINI_TOP_P,
      top_k: int = _DEFAULT_GEMINI_TOP_K,
      max_output_tokens: int = _DEFAULT_GEMINI_MAX_OUTPUT_TOKENS,
      response_mime_type: str = _DEFAULT_GEMINI_RESPONSE_MIME_TYPE,
  ) -> None:
    """Initializes the Dubber class with various parameters for dubbing configuration.

    Args:
        input_file: The path to the input video or audio file.
        output_directory: The directory to save the dubbed output and
          intermediate files.
        advertiser_name: The name of the advertiser for context in
          transcription/translation.
        original_language: The language of the original audio. It must be ISO
          3166-1 alpha-2 country code.
        target_language: The language to dub the ad into. It must be ISO 3166-1
          alpha-2 country code.
        number_of_speakers: The exact number of speakers in the ad (including a
          lector if applicable).
        diarization_instructions: Specific instructions for speaker diarization.
        translation_instructions: Specific instructions for translation.
        merge_utterances: Whether to merge utterances when the the timestamps
          delta between them is below 'minimum_merge_threshold'.
        minimum_merge_threshold: Threshold for merging utterances in seconds.
        preferred_voices: Preferred voice names for text-to-speech. Use
          high-level names, e.g. 'Wavenet', 'Standard' etc. Do not use the full
          voice names, e.g. 'pl-PL-Wavenet-A' etc.
        clean_up: Whether to delete intermediate files after dubbing. Only the
          final ouput and the utterance metadata will be kept.
        pyannote_model: Name of the PyAnnote diarization model.
        diarization_system_instructions: System instructions for diarization.
        translation_system_instructions: System instructions for translation.
        hugging_face_token: Hugging Face API token (can be set via
          'HUGGING_FACE_TOKEN' environment variable).
        gemini_token: Gemini API token (can be set via 'GEMINI_TOKEN'
          environment variable).
        model_name: The name of the Gemini model to use.
        temperature: Controls randomness in generation.
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum number of tokens in the generated response.
    """
    self.input_file = input_file
    self.output_directory = output_directory
    self.advertiser_name = advertiser_name
    self.original_language = original_language
    self.target_language = target_language
    self.number_of_speakers = number_of_speakers
    self.diarization_instructions = diarization_instructions
    self.translation_instructions = translation_instructions
    self.merge_utterances = merge_utterances
    self.minimum_merge_threshold = minimum_merge_threshold
    self.preferred_voices = preferred_voices
    self.clean_up = clean_up
    self.pyannote_model = pyannote_model
    self.hugging_face_token = hugging_face_token
    self.gemini_token = gemini_token
    self.diarization_system_instructions = diarization_system_instructions
    self.translation_system_instructions = translation_system_instructions
    self.model_name = model_name
    self.temperature = temperature
    self.top_p = top_p
    self.top_k = top_k
    self.max_output_tokens = max_output_tokens
    self.response_mime_type = response_mime_type

  @functools.cached_property
  def is_video(self) -> bool:
    """Checks if the input file is a video."""
    return is_video(input_file=self.input_file)

  def get_api_token(self, provided_token: str | None, env_variable: str) -> str:
    """Helper to get API token, prioritizing provided argument over environment variable.

    Args:
        provided_token: The API token provided directly as an argument.
        env_variable: The name of the environment variable storing the API
          token.

    Returns:
        The API token (either the provided one or from the environment).

    Raises:
        ValueError: If neither the provided token nor the environment variable
        is set.
    """
    token = provided_token or os.getenv(env_variable)
    if not token:
      raise ValueError(
          f"You must either provide the '{env_variable}' argument or set the"
          f" '{env_variable.upper()}' environment variable."
      )
    return token

  @property
  def pyannote_pipeline(self) -> Pipeline:
    """Loads the PyAnnote diarization pipeline."""
    hugging_face_token = self.get_api_token(
        self.hugging_face_token, "HUGGING_FACE_TOKEN"
    )
    return Pipeline.from_pretrained(
        self.pyannote_model, use_auth_token=hugging_face_token
    )

  @property
  def speech_to_text_model(self) -> WhisperModel:
    """Initializes the Whisper speech-to-text model."""
    return WhisperModel(
        model_size_or_path=_DEFAULT_TRANSCRIPTION_MODEL,
        device=_DEVICE,
        compute_type=_TRANSCRIPTION_COMPUTE_TYPE,
    )

  def configure_gemini_model(
      self, *, system_instruction: str
  ) -> genai.GenerativeModel:
    """Configures the Gemini generative model.

    Args:
        system_instruction: The system instruction to guide the model's
          behavior.
        model_name: The name of the Gemini model to use.
        temperature: Controls randomness in generation.
        top_p: Nucleus sampling threshold.
        top_k: Top-k sampling parameter.
        max_output_tokens: Maximum number of tokens in the generated response.
        response_mime_type: MIME type of the generated response.

    Returns:
        The configured Gemini model instance.
    """

    gemini_token = self.get_api_token(self.gemini_token, "GEMINI_TOKEN")
    genai.configure(api_key=gemini_token)
    gemini_configuration = dict(
        temperature=self.temperature,
        top_p=self.top_p,
        top_k=self.top_k,
        max_output_tokens=self.max_output_tokens,
        response_mime_type=self.response_mime_type,
    )
    return genai.GenerativeModel(
        model_name=self.model_name,
        generation_config=gemini_configuration,
        system_instruction=system_instruction,
        safety_settings=_DEFAULT_GEMINI_SAFETY_SETTINGS,
    )

  @property
  def text_to_speech_client(self) -> texttospeech.TextToSpeechClient:
    """Creates a Text-to-Speech client."""
    return texttospeech.TextToSpeechClient()

  @functools.cached_property
  def diarization_system_instructions(self) -> str:
    """Reads and caches diarization system instructions."""
    return read_system_settings(
        input_string=self.diarization_system_instructions
    )

  @functools.cached_property
  def translation_system_instructions(self) -> str:
    """Reads and caches translation system instructions."""
    return read_system_settings(
        input_string=self.translation_system_instructions
    )

  def preprocessing(self, kwargs) -> PreprocessingArtifacts:
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
    )
    audio_processing.execute_demcus_command(command=demucs_command)
    _, audio_background_file = audio_processing.assemble_split_audio_file_paths(
        command=demucs_command
    )

    utterance_metadata = audio_processing.create_pyannote_timestamps(
        audio_file=audio_file,
        number_of_speakers=self.number_of_speakers,
        pipeline=self.pyannote_pipeline,
    )
    utterance_metadata = audio_processing.cut_and_save_audio(
        utterance_metadata=utterance_metadata,
        audio_file=audio_file,
        output_directory=self.output_directory,
    )
    return PreprocessingArtifacts(
        video_file=video_file,
        audio_file=audio_file,
        audio_background_file=audio_background_file,
        utterance_metadata=utterance_metadata,
    )

  def speech_to_text(
      self,
      *,
      media_file: str,
      utterance_metadata: Sequence[Mapping[str, str | float]],
  ) -> Sequence[Mapping[str, str | float]]:
    """Transcribes audio, applies speaker diarization, and updates metadata with Gemini.

    Args:
        media_file: Path to the media file (audio or video).
        utterance_metadata: A list of dictionaries containing utterance
          metadata.

    Returns:
        Updated utterance metadata with speaker information and transcriptions.
    """
    utterance_metadata = speech_to_text.transcribe_audio_chunks(
        utterance_metadata=utterance_metadata,
        advertiser_name=self.advertiser_name,
        original_language=self.original_language,
        model=self.speech_to_text_model,
    )

    speaker_diarization_model = self.configure_gemini_model(
        system_instructions=self.diarization_system_instructions
    )
    speaker_info = speech_to_text.diarize_speakers(
        file=media_file,
        utterance_metadata=utterance_metadata,
        model=speaker_diarization_model,
        diarization_instructions=self.diarization_instructions,
    )

    return speech_to_text.add_speaker_info(
        utterance_metadata=utterance_metadata, speaker_info=speaker_info
    )

  def translation(
      self, *, utterance_metadata: Sequence[Mapping[str, str | float]]
  ) -> Sequence[Mapping[str, str | float]]:
    """Translates transcribed text and potentially merges utterances with Gemini.

    Args:
        utterance_metadata: A list of dictionaries containing utterance
          metadata.

    Returns:
        Updated utterance metadata with translated text.
    """
    script = translation.generate_script(utterance_metadata=utterance_metadata)
    translation_model = self.configure_gemini_model(
        system_instructions=self.translation_system_instructions
    )
    translated_script = translation.translate_script(
        script=script,
        advertiser_name=self.advertiser_name,
        translation_instructions=self.translation_instructions,
        target_language=self.target_language,
        model=translation_model,
    )
    utterance_metadata = translation.add_translations(
        utterance_metadata=utterance_metadata,
        translated_script=translated_script,
    )
    if self.merge_utterances:
      utterance_metadata = translation.merge_utterances(
          utterance_metadata=utterance_metadata,
          minimum_merge_threshold=self.minimum_merge_threshold,
      )
    return utterance_metadata

  def text_to_speech(
      self, *, utterance_metadata: Sequence[Mapping[str, str | float]]
  ) -> Sequence[Mapping[str, str | float]]:
    """Converts translated text to speech and dubs utterances with Google's Text-To-Speech.

    Args:
        utterance_metadata: A list of dictionaries containing utterance
          metadata.

    Returns:
        Updated utterance metadata with generated speech file paths.
    """

    assigned_voices = text_to_speech.assign_voices(
        utterance_metadata=utterance_metadata,
        target_language=self.target_language,
        preferred_voices=self.preferred_voices,
    )
    utterance_metadata = text_to_speech.update_utterance_metadata(
        utterance_metadata=utterance_metadata, assigned_voices=assigned_voices
    )
    return text_to_speech.dub_utterances(
        client=self.text_to_speech_client,
        utterance_metadata=utterance_metadata,
        output_directory=self.output_directory,
        target_language=self.target_language,
    )

  def postprocessing(
      self,
      *,
      utterance_metadata: Sequence[Mapping[str, str | float]],
      audio_background_file: str,
      video_file: str | None = None,
  ) -> str:
    """Merges dubbed audio with the original background audio and video (if applicable).

    Args:
        utterance_metadata: A list of dictionaries containing utterance
          metadata.
        audio_background_file: Path to the original background audio file.
        video_file: Path to the original video file (optional, only if input was
          a video).

    Returns:
        Path to the final dubbed output file (audio or video).
    """

    dubbed_audio_vocals_file = audio_processing.insert_audio_at_timestamps(
        utterance_metadata=utterance_metadata,
        background_audio_file=audio_background_file,
        output_directory=self.output_directory,
    )
    dubbed_audio_file = audio_processing.merge_background_and_vocals(
        background_audio_file=audio_background_file,
        dubbed_vocals_audio_file=dubbed_audio_vocals_file,
        output_directory=self.output_directory,
    )
    if self.is_video:
      if not video_file:
        raise ValueError(
            "A video file must be provided if the input file is a video."
        )
      output_file = video_processing.combine_audio_video(
          video_file=video_file,
          dubbed_audio_file=dubbed_audio_file,
          output_directory=self.output_directory,
      )
    else:
      output_file = dubbed_audio_file
    return output_file

  def dub_ad(self):
    """Orchestrates the entire ad dubbing process."""
    preprocessing_artifacts = self.preprocessing()
    media_file = (
        preprocessing_artifacts.video_file
        if preprocessing_artifacts.video_file
        else preprocessing_artifacts.audio_file
    )
    utterance_metadata = self.speech_to_text(
        media_file=media_file,
        utterance_metadata=preprocessing_artifacts.utterance_metadata,
    )
    utterance_metadata = self.translation(utterance_metadata=utterance_metadata)
    utterance_metadata = self.text_to_speech(
        utterance_metadata=utterance_metadata
    )
    utterance_metadata_file = save_utterance_metadata(
        utterance_metadata=utterance_metadata,
        output_directory=self.output_directory,
    )
    output_file = self.postprocessing(
        utterance_metadata=utterance_metadata,
        audio_background_file=preprocessing_artifacts.audio_background_file,
        video_file=preprocessing_artifacts.video_file,
    )
    if self.clean_up:
      clean_directory(
          directory=self.output_directory,
          keep_file=[output_file, utterance_metadata_file],
      )
    return output_file

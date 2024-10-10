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

"""A text-to-speech module of Ariel package from the Google EMEA gTech Ads Data Science."""

import dataclasses
import functools
import io
import os
from typing import Final, Mapping, Sequence
from absl import logging
from ariel import audio_processing
from elevenlabs import VoiceSettings, save
from elevenlabs.client import ElevenLabs
from elevenlabs.client import is_voice_id
from elevenlabs.types.voice import Voice
from google.cloud import texttospeech
from pydub import AudioSegment
from pydub.effects import speedup
import tensorflow as tf

DUBBED_AUDIO_CHUNKS: Final[str] = "dubbed_audio_chunks"
_SSML_MALE: Final[str] = "Male"
_SSML_FEMALE: Final[str] = "Female"
_SSML_NEUTRAL: Final[str] = "Neutral"
_DEFAULT_PREFERRED_GOOGLE_VOICES: Final[Sequence[str]] = (
    "Journey",
    "Studio",
    "Wavenet",
    "Polyglot",
    "News",
    "Neural2",
    "Standard",
)
_EXCEPTION_VOICE: Final[str] = "Journey"
_DEFAULT_SSML_FEMALE_PITCH: Final[float] = -5.0
_DEFAULT_SSML_MALE_PITCH: Final[float] = -10.0
_DEFAULT_SPEED: Final[float] = 1.0
_DEFAULT_VOLUME_GAIN_DB: Final[float] = 16.0
_DEFAULT_STABILITY: Final[float] = 0.5
_DEFAULT_SIMILARITY_BOOST: Final[float] = 0.75
_DEFAULT_STYLE: Final[float] = 0.0
_DEFAULT_USE_SPEAKER_BOOST: Final[bool] = True
_DEFAULT_ELEVENLABS_MODEL: Final[str] = "eleven_multilingual_v2"
_ALTERNATIVE_ELEVENLABS_MODEL: Final[str] = "eleven_turbo_v2_5"
_DEFAULT_CHUNK_SIZE: Final[int] = 150


class VoiceAssigner:
  """Assigns voices to speakers based on preferred voices and available voices.

  from different providers (Google Cloud Text-to-Speech, ElevenLabs).

  This class handles voice assignment for both Google Cloud Text-to-Speech and
  ElevenLabs, allowing you to specify preferred voices and override automatic
  assignments. It ensures each speaker is assigned a unique voice that matches
  their specified gender (SSML gender tag) while prioritizing preferred voices.
  """

  def __init__(
      self,
      *,
      utterance_metadata: Sequence[Mapping[str, str | float]],
      client: texttospeech.TextToSpeechClient | ElevenLabs,
      target_language: str,
      preferred_voices: Sequence[str] | None = None,
      assigned_voices_override: Mapping[str, str] | None = None,
      elevenlabs_clone_voices: bool = False,
  ):
    """Initializes VoiceAssigner with necessary parameters.

    Args:
        utterance_metadata: A sequence of utterance metadata dictionaries. Each
          dictionary should contain keys like "speaker_id" and "ssml_gender".
        client: A client object for either Google Cloud Text-to-Speech
          (texttospeech.TextToSpeechClient) or ElevenLabs.
        target_language: The target language for voice selection (e.g.,
          "en-US").
        preferred_voices: An optional list of preferred voice names. These will
          be prioritized during voice assignment.
        assigned_voices_override: An optional dictionary mapping speaker IDs to
          specific voice names. This allows you to completely override the
          automatic voice assignment.
        elevenlabs_clone_voices: Whether voices are cloned with ElevenLabs.
    """
    self.utterance_metadata = utterance_metadata
    self.client = client
    self.target_language = target_language
    self._preferred_voices = preferred_voices
    self.assigned_voices_override = assigned_voices_override
    self.elevenlabs_clone_voices = elevenlabs_clone_voices

  @functools.cached_property
  def preferred_voices(self) -> Sequence[str]:
    """Returns the preferred voice names.

    Defaults to a set of common Google Cloud voices if not provided
    for Google TTS and all available voices for ElevenLabs.

    Returns:
        A sequence of preferred voice names.
    """
    if self._preferred_voices:
      return self._preferred_voices
    if isinstance(self.client, texttospeech.TextToSpeechClient):
      logging.info(
          "Preferred voices were None, defaulting to:"
          f" {','.join(_DEFAULT_PREFERRED_GOOGLE_VOICES)}"
      )
      return _DEFAULT_PREFERRED_GOOGLE_VOICES
    elif isinstance(self.client, ElevenLabs):
      logging.info(
          "Preferred voices were None, defaulting to all available ElevenLabs"
          " voices."
      )
      return [voice.name for voice in self.client.voices.get_all().voices]
    else:
      raise ValueError("Unsupported client type")

  @functools.cached_property
  def _unique_speaker_mapping(self) -> Mapping[str, str]:
    """Returns a mapping of unique speaker IDs to their corresponding genders.

    Returns:
        A dictionary mapping speaker IDs to SSML genders.
    """
    return {
        item["speaker_id"]: item["ssml_gender"]
        for item in self.utterance_metadata
    }

  @functools.cached_property
  def available_voices(self) -> Mapping[str, str]:
    """Retrieves the available voices from the provider.

    Returns:
        A dictionary mapping voice names to genders (Male, Female, Neutral).
    """
    if isinstance(self.client, texttospeech.TextToSpeechClient):
      request = texttospeech.ListVoicesRequest(
          language_code=self.target_language
      )
      response = self.client.list_voices(request=request)
      return {
          voice.name: (
              _SSML_MALE
              if voice.ssml_gender == texttospeech.SsmlVoiceGender.MALE
              else _SSML_FEMALE
              if voice.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE
              else _SSML_NEUTRAL
          )
          for voice in response.voices
      }
    elif isinstance(self.client, ElevenLabs):
      return {
          voice.name: voice.labels["gender"].capitalize()
          for voice in self.client.voices.get_all().voices
      }
    else:
      raise ValueError("Unsupported client type.")

  def _apply_overrides(self) -> Mapping[str, str]:
    """Applies the assigned_voices_override to the voice assignments.

    Validates that the override provides assignments for all unique speakers.

    Returns:
        A dictionary mapping speaker IDs to voice names based on the
        override.

    Raises:
        ValueError: If the override does not provide assignments for all
            unique speakers.
    """
    unique_speakers = set(self._unique_speaker_mapping.keys())
    override_speakers = set(self.assigned_voices_override.keys())
    missing_speakers = unique_speakers - override_speakers
    if missing_speakers:
      raise ValueError(
          "Missing voice assignments for the following speakers in "
          f"'assigned_voices_override': {', '.join(missing_speakers)}"
      )
    return self.assigned_voices_override

  def _can_assign_voice(
      self,
      *,
      voice_name: str,
      ssml_gender: str,
      already_assigned_voices: Mapping[str, Sequence[str]],
  ) -> bool:
    """Checks if a voice can be assigned to a speaker with the given gender.

    The voice must be available, match the speaker's gender, and not be
    already assigned to another speaker with the same gender.

    Args:
        voice_name: The name of the voice to check.
        ssml_gender: The SSML gender of the speaker.
        already_assigned_voices: A dictionary mapping genders to a list of
          already assigned voices for that gender.

    Returns:
        True if the voice can be assigned, False otherwise.
    """
    return (
        self.available_voices[voice_name].lower() == ssml_gender.lower()
        and voice_name not in already_assigned_voices[ssml_gender]
    )

  def _find_matching_voice(
      self,
      *,
      preferred_voice_name: str,
      ssml_gender: str,
      already_assigned_voices: Mapping[str, Sequence[str]],
  ) -> str | None:
    """Finds an available voice matching the preferred name and gender.

    Args:
        preferred_voice_name: The preferred voice name to search for.
        ssml_gender: The SSML gender of the speaker.
        already_assigned_voices: A dictionary mapping genders to a list of
          already assigned voices for that gender.

    Returns:
        The name of the matching voice if found, None otherwise.
    """
    for voice_name in self.available_voices:
      if preferred_voice_name in voice_name and self._can_assign_voice(
          voice_name=voice_name,
          ssml_gender=ssml_gender,
          already_assigned_voices=already_assigned_voices,
      ):
        return voice_name
    return None

  def _find_any_suitable_voice(
      self,
      *,
      speaker_id: str,
      ssml_gender: str,
      already_assigned_voices: Mapping[str, Sequence[str]],
  ) -> str:
    """Finds any available voice matching the gender.

    Args:
        speaker_id: A unique speaker ID.
        ssml_gender: The SSML gender of the speaker.
        already_assigned_voices: A dictionary mapping genders to a list of
          already assigned voices for that gender.

    Returns:
        The name of a suitable voice.

    Raises:
        ValueError: If no suitable voice is found for the given gender.
    """
    for voice_name in self.available_voices.keys():
      if self._can_assign_voice(
          voice_name=voice_name,
          ssml_gender=ssml_gender,
          already_assigned_voices=already_assigned_voices,
      ):
        return voice_name
    raise ValueError(
        f"Could not allocate a voice '{speaker_id}' with ssml_gender"
        f" '{ssml_gender}'."
    )

  def _find_voice_for_speaker(
      self,
      *,
      speaker_id: str,
      ssml_gender: str,
      already_assigned_voices: Mapping[str, Sequence[str]],
  ) -> str:
    """Finds a suitable voice for a speaker, prioritizing preferred voices.

    Args:
        speaker_id: A unique speaker ID.
        ssml_gender: The SSML gender of the speaker.
        already_assigned_voices: A dictionary mapping genders to a list of
          already assigned voices for that gender.

    Returns:
        The name of the assigned voice.
    """
    for preferred_voice_name in self.preferred_voices:
      voice_name = self._find_matching_voice(
          preferred_voice_name=preferred_voice_name,
          ssml_gender=ssml_gender,
          already_assigned_voices=already_assigned_voices,
      )
      if voice_name:
        return voice_name
    return self._find_any_suitable_voice(
        speaker_id=speaker_id,
        ssml_gender=ssml_gender,
        already_assigned_voices=already_assigned_voices,
    )

  def _assign_voices(self) -> Mapping[str, str]:
    """Assigns voices to speakers based on preferred and available voices.

    Prioritizes preferred voices and then assigns any suitable voice if
    no preferred voice is available or matches the speaker's gender.

    Returns:
        A dictionary mapping speaker IDs to assigned voice names.
    """
    already_assigned_voices = {_SSML_MALE: set(), _SSML_FEMALE: set()}
    voice_assignment = {}
    for speaker_id, ssml_gender in self._unique_speaker_mapping.items():
      selected_voice = self._find_voice_for_speaker(
          speaker_id=speaker_id,
          ssml_gender=ssml_gender,
          already_assigned_voices=already_assigned_voices,
      )
      voice_assignment[speaker_id] = selected_voice
      already_assigned_voices[ssml_gender].add(selected_voice)
    return voice_assignment

  @functools.cached_property
  def assigned_voices(self) -> Mapping[str, str] | None:
    """Returns the final voice assignments for each speaker.

    Uses assigned_voices_override if provided; otherwise, automatically
    assigns voices based on preferred voices and availability.

    Returns:
         A dictionary mapping speaker IDs to assigned voice names.
    """
    if self.elevenlabs_clone_voices:
      return None
    if self.assigned_voices_override:
      return self._apply_overrides()
    return self._assign_voices()


def add_text_to_speech_properties(
    *,
    utterance_metadata: Mapping[str, str | float],
    use_elevenlabs: bool = False,
) -> Mapping[str, str | float]:
  """Updates utterance metadata with Text-To-Speech properties.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "text", "start", "end", "speaker_id",
        "ssml_gender", "translated_text", "for_dubbing", "path" and optionally
        "vocals_path".
      use_elevenlabs: An indicator whether Eleven Labs API will be used in the
        Text-To-Speech proecess.

  Returns:
      Sequence of updated utterance metadata dictionaries.
  """
  utterance_metadata_copy = utterance_metadata.copy()
  if not use_elevenlabs:
    ssml_gender = utterance_metadata_copy.get("ssml_gender")
    pitch = (
        _DEFAULT_SSML_FEMALE_PITCH
        if ssml_gender == "Female"
        else _DEFAULT_SSML_MALE_PITCH
    )
    voice_properties = dict(
        pitch=pitch,
        speed=_DEFAULT_SPEED,
        volume_gain_db=_DEFAULT_VOLUME_GAIN_DB,
    )
  else:
    voice_properties = dict(
        stability=_DEFAULT_STABILITY,
        similarity_boost=_DEFAULT_SIMILARITY_BOOST,
        style=_DEFAULT_STYLE,
        use_speaker_boost=_DEFAULT_USE_SPEAKER_BOOST,
    )
  utterance_metadata_copy.update(voice_properties)
  return utterance_metadata_copy


def update_utterance_metadata(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    assigned_voices: Mapping[str, str] | None,
    use_elevenlabs: bool = False,
    elevenlabs_clone_voices: bool = False,
) -> Sequence[Mapping[str, str | float]]:
  """Updates utterance metadata with assigned voices.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "text", "start", "end", "speaker_id",
        "ssml_gender", "translated_text", "for_dubbing", "path" and optionally
        "vocals_path".
      assigned_voices: Mapping mapping speaker IDs to assigned Google voices.
      use_elevenlabs: An indicator whether Eleven Labs API will be used in the
        Text-To-Speech proecess.
      clone_voices: Whether to clone source voices. It requires using ElevenLabs
        API.

  Returns:
      Sequence of updated utterance metadata dictionaries.

  Raises:
      ValueError: When 'elevenlabs_clone_voices' is True and 'use_elevenlabs' is
      False.
  """
  if elevenlabs_clone_voices:
    if not use_elevenlabs:
      raise ValueError("Voice cloning requires using ElevenLabs API.")
  updated_utterance_metadata = []
  for metadata_item in utterance_metadata:
    new_utterance = metadata_item.copy()
    if not elevenlabs_clone_voices:
      speaker_id = new_utterance.get("speaker_id")
      new_utterance["assigned_voice"] = assigned_voices.get(speaker_id)
    new_utterance = add_text_to_speech_properties(
        utterance_metadata=new_utterance, use_elevenlabs=use_elevenlabs
    )
    updated_utterance_metadata.append(new_utterance)
  return updated_utterance_metadata


def convert_text_to_speech(
    *,
    client: texttospeech.TextToSpeechClient,
    assigned_google_voice: str,
    target_language: str,
    output_filename: str,
    text: str,
    pitch: float,
    speed: float,
    volume_gain_db: float,
) -> str:
  """Converts text to speech using Google Cloud Text-to-Speech API.

  Args:
      client: The TextToSpeechClient object to use.
      assigned_google_voice: The name of the Google Cloud voice to use.
      target_language: The target language (ISO 3166-1 alpha-2).
      output_filename: The name of the output MP3 file.
      text: The text to be converted to speech.
      pitch: The pitch of the synthesized speech.
      speed: The speaking rate of the synthesized speech.
      volume_gain_db: The volume gain of the synthesized speech.

  Returns:
      The name of the output file.
  """

  input_text = texttospeech.SynthesisInput(text=text)
  voice_selection = texttospeech.VoiceSelectionParams(
      name=assigned_google_voice,
      language_code=target_language,
  )
  audio_config = texttospeech.AudioConfig(
      audio_encoding=texttospeech.AudioEncoding.LINEAR16,
      volume_gain_db=volume_gain_db,
  )
  if not _EXCEPTION_VOICE in assigned_google_voice:
    audio_config.speaking_rate = speed
    audio_config.pitch = pitch
  else:
    logging.info(
        "%s voice was selected. Neither `pitch` nor `speaking_rate` can be"
        " controlled.",
        _EXCEPTION_VOICE,
    )
  response = client.synthesize_speech(
      input=input_text,
      voice=voice_selection,
      audio_config=audio_config,
  )
  converted_audio_content = AudioSegment(
      data=response.audio_content,
  )
  buffer = io.BytesIO()
  converted_audio_content.export(buffer, format="mp3", bitrate="320k")
  with tf.io.gfile.GFile(output_filename, "wb") as out:
    out.write(buffer.getvalue())
  return output_filename


def calculate_target_utterance_speed(
    *,
    reference_length: float,
    dubbed_file: str,
) -> float:
  """Returns the ratio between the reference and target duration.

  Args:
      reference_length: The reference length of an audio chunk.
      dubbed_file: The path to the dubbed MP3 file.
  """

  dubbed_audio = AudioSegment.from_file(dubbed_file)
  dubbed_duration = dubbed_audio.duration_seconds
  return dubbed_duration / reference_length


def _find_voice_id(
    *, client: ElevenLabs, assigned_elevenlabs_voice: str
) -> str:
  """Retrieves the ElevenLabs voice ID.

  The function uses the same logic as part of the `generate` method of the
  ElevenLabs
  class
  in version 1.9.0, specifically the lines: 177 - 184. It's to accommodate for
  the
  `text_to_speech.convert` method accepting the voice_id only. The link:

  https://github.com/elevenlabs/elevenlabs-python/blob/1.9.0/src/elevenlabs/client.py#L177

  Args:
    client: The ElevenLabs client object.
    assigned_elevenlabs_voice: The voice ID or voice name.

  Returns:
    The ElevenLabs voice ID.

  Raises:
    ValueError: If the voice is not found and can't be assigned any voice ID.
  """
  if isinstance(assigned_elevenlabs_voice, str) and is_voice_id(
      assigned_elevenlabs_voice
  ):
    return assigned_elevenlabs_voice
  all_available_voices = client.voices.get_all(show_legacy=True)
  voice_id = next(
      (
          voice.voice_id
          for voice in all_available_voices.voices
          if voice.name == assigned_elevenlabs_voice
      ),
      None,
  )
  if not voice_id:
    raise ValueError(
        f"No voice ID found for {assigned_elevenlabs_voice}. It is either"
        " unavailable or you provided an incorrect name"
    )
  return voice_id


def elevenlabs_convert_text_to_speech(
    *,
    client: ElevenLabs,
    model: str,
    assigned_elevenlabs_voice: str,
    output_filename: str,
    text: str,
    target_language: str,
    stability: float = _DEFAULT_STABILITY,
    similarity_boost: float = _DEFAULT_SIMILARITY_BOOST,
    style: float = _DEFAULT_STYLE,
    use_speaker_boost: bool = _DEFAULT_USE_SPEAKER_BOOST,
) -> str:
  """Converts text to speech using the ElevenLabs API and saves the audio to a file.

  This function leverages the ElevenLabs client to generate speech from the
  provided text, using the specified voice and optional customization settings.
  The resulting audio is then saved to the given output filename.

  Args:
      client: An authenticated ElevenLabs client object for API interaction.
      model: The name of the ElevenLabs speech model to use (e.g.,
        "eleven_multilingual_v2").
      assigned_elevenlabs_voice: The name of the ElevenLabs voice to use for
        generation.
      output_filename: The path and filename where the generated audio will be
        saved.
      text: The text content to convert to speech.
      target_language: The language to dub the ad into. It must be ISO 3166-1
        alpha-2 country code.
      stability: Controls the stability of the generated voice (0.0 to 1.0).
        Default is _DEFAULT_STABILITY.
      similarity_boost:  Enhances the voice's similarity to the original (0.0 to
        1.0). Default is _DEFAULT_SIMILARITY_BOOST.
      style: Adjusts the speaking style (0.0 to 1.0). Default is _DEFAULT_STYLE.
      use_speaker_boost:  Whether to use speaker boost to enhance clarity.
        Default is _DEFAULT_USE_SPEAKER_BOOST.

  Returns:
      The path and filename of the saved audio file (same as `output_filename`).
  """
  voice_id = _find_voice_id(
      client=client, assigned_elevenlabs_voice=assigned_elevenlabs_voice
  )
  elevenlabs_language_code = (
      target_language.split("-")[0]
      if model == _ALTERNATIVE_ELEVENLABS_MODEL
      else None
  )
  audio = client.text_to_speech.convert(
      model_id=model,
      voice_id=voice_id,
      text=text,
      voice_settings=VoiceSettings(
          stability=stability,
          similarity_boost=similarity_boost,
          style=style,
          use_speaker_boost=use_speaker_boost,
      ),
      language_code=elevenlabs_language_code,
  )
  save(audio, output_filename)
  return output_filename


@dataclasses.dataclass
class SpeakerData:
  """Instance with speaker data.

  Attributes:
      speaker_id: A unique speaker ID.
      ssml_gender: A speaker gender.
      paths: A sequence with paths to voice samples of the speaker.
  """

  speaker_id: str
  ssml_gender: str
  paths: Sequence[str]


def create_speaker_data_mapping(
    utterance_metadata: Sequence[Mapping[str, float | str]],
) -> Sequence[SpeakerData]:
  """Extracts speaker data from utterance metadata.

  Args:
      utterance_metadata: A list of dictionaries containing utterance metadata.

  Returns:
      A sequence of SpeakerData objects.
  """

  speaker_data = []
  for metadata in utterance_metadata:
    speaker_id = metadata["speaker_id"]
    ssml_gender = metadata["ssml_gender"]
    paths = [metadata["vocals_path"]]
    existing_speaker = next(
        (s for s in speaker_data if s.ssml_gender == ssml_gender), None
    )
    if existing_speaker:
      existing_speaker.paths.extend(paths)
    else:
      speaker_data.append(
          SpeakerData(
              speaker_id=speaker_id, ssml_gender=ssml_gender, paths=paths
          )
      )
  return speaker_data


def elevenlabs_run_clone_voices(
    *, client: ElevenLabs, speaker_data_mapping: Sequence[SpeakerData]
) -> Mapping[str, str]:
  """Clones voices for speakers using ElevenLabs based on utterance metadata and file paths.

  Args:
      client: An authenticated ElevenLabs client object for API interaction.
      speaker_data_mapping: A sequence with speaker_id, ssml_gender and a
        sequence with paths to voice_samples.

  Returns:
      A mapping between speaker IDs to their cloned voices.
  """
  speaker_to_voices_mapping = {}
  for speaker_data in speaker_data_mapping:
    voice = client.clone(
        name=f"{speaker_data.speaker_id}",
        description=f"Voice for {speaker_data.speaker_id}",
        files=speaker_data.paths,
        labels=dict(gender=speaker_data.ssml_gender.lower()),
    )
    speaker_to_voices_mapping[speaker_data.speaker_id] = voice.voice_id
  return speaker_to_voices_mapping


def adjust_audio_speed(
    *,
    speed: float,
    dubbed_path: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> None:
  """Adjusts the speed of an MP3 file to match the reference file duration.

  The speed will not be adjusted if the dubbed file has a duration that
  is the same or shorter than the duration of the reference file.

  Args:
      speed: The desired speed in seconds. If None it will be determined based
        on the duration of the reference_file and dubbed_file.
      dubbed_path: The path to the dubbed MP3 file.
      chunk_size: Duration of audio chunks (in ms) to preserve in the
        adjustement process.
  """

  dubbed_audio = AudioSegment.from_file(dubbed_path)
  if speed <= 1.0:
    return
  logging.warning(
      "Adjusting audio speed will prevent overlaps of utterances. However,"
      " it might change the voice sligthly."
  )
  crossfade = max(1, chunk_size // 2)
  output_audio = speedup(
      dubbed_audio, speed, chunk_size=chunk_size, crossfade=crossfade
  )
  output_audio.export(dubbed_path, format="mp3")


class TextToSpeech:
  """Manages the Text-To-Speech (TTS) process during dubbing.

  This class handles the conversion of translated text to speech using either
  Google Cloud Text-to-Speech or ElevenLabs API. It provides functionalities
  for voice cloning, assigning voices, running TTS, and adjusting speech speed
  to match the original audio.

  Attributes:
    client: The TTS client object (either Google Cloud's or ElevenLabs').
    utterance_metadata: A sequence of dictionaries, each containing metadata
      about an utterance (e.g., speaker, text, timestamps).
    output_directory: The directory to save the dubbed audio files.
    target_language: The target language for dubbing.
    preprocessing_output: A dictionary containing paths to preprocessed files.
    adjust_speed: Whether to adjust the speed of the dubbed audio.
    use_elevenlabs: Whether to use ElevenLabs API for TTS.
    elevenlabs_model: The ElevenLabs model to use for speech synthesis.
    elevenlabs_clone_voices: Whether to clone voices using ElevenLabs.
    cloned_voices: A dictionary mapping speaker IDs to cloned voices.
  """

  def __init__(
      self,
      *,
      client: texttospeech.TextToSpeechClient | ElevenLabs,
      utterance_metadata: Sequence[Mapping[str, str | float]],
      output_directory: str,
      target_language: str,
      preprocessing_output: Mapping[str, str],
      adjust_speed: bool = True,
      use_elevenlabs: bool = False,
      elevenlabs_model: str = _DEFAULT_ELEVENLABS_MODEL,
      elevenlabs_clone_voices: bool = False,
  ) -> None:
    """Initializes TextToSpeech with the provided parameters.

    Args:
      client: The TTS client object.
      utterance_metadata: Metadata for each utterance.
      output_directory: Directory to save dubbed audio.
      target_language: The target language.
      preprocessing_output: Paths to preprocessed files.
      adjust_speed: Whether to adjust dubbed audio speed.
      use_elevenlabs: Whether to use ElevenLabs API.
      elevenlabs_model: The ElevenLabs model to use.
      elevenlabs_clone_voices: Whether to clone voices.
    """
    self.client = client
    self.utterance_metadata = utterance_metadata
    self.output_directory = output_directory
    self.target_language = target_language
    self.adjust_speed = adjust_speed
    self.use_elevenlabs = use_elevenlabs
    self.elevenlabs_model = elevenlabs_model
    self.elevenlabs_clone_voices = elevenlabs_clone_voices
    self.preprocessing_output = preprocessing_output
    self.cloned_voices = None

  def _clone_voices(self) -> Mapping[str, Voice]:
    """Clones voices using ElevenLabs API.

    This method clones voices based on the `elevenlabs_clone_voices` flag.
    It extracts audio segments for each speaker, creates a mapping between
    speakers and their audio files, and then uses ElevenLabs to clone the
    voices.

    Returns:
      A dictionary mapping speaker IDs to their cloned voices.
    """
    if not self.elevenlabs_clone_voices:
      return
    if self.elevenlabs_clone_voices and not self.use_elevenlabs:
      raise ValueError("Voice cloning requires using ElevenLabs API.")
    self.utterance_metadata = audio_processing.run_cut_and_save_audio(
        utterance_metadata=self.utterance_metadata,
        audio_file=self.preprocessing_output["audio_vocals_file"],
        output_directory=self.output_directory,
        elevenlabs_clone_voices=self.elevenlabs_clone_voices,
    )
    speaker_data_mapping = create_speaker_data_mapping(self.utterance_metadata)
    return elevenlabs_run_clone_voices(
        client=self.client,
        speaker_data_mapping=speaker_data_mapping,
    )

  def _assign_output_path(self, utterance: Mapping[str, str | float]) -> str:
    """Assigns the output path for the dubbed audio file.

    Args:
      utterance: A dictionary containing utterance metadata.

    Returns:
      The path for the dubbed audio file.
    """
    path = utterance["path"]
    base_filename = os.path.splitext(os.path.basename(path))[0]
    return os.path.join(
        self.output_directory,
        DUBBED_AUDIO_CHUNKS,
        f"dubbed_{base_filename}.mp3",
    )

  def _find_voice(self, utterance: Mapping[str, str | float]) -> str | Voice:
    """Finds the appropriate voice for the given utterance.

    Args:
      utterance: A dictionary containing utterance metadata.

    Returns:
      The voice ID (for Google Cloud) or Voice object (for ElevenLabs) to use.
    """
    if self.elevenlabs_clone_voices:
      return self.cloned_voices[utterance["speaker_id"]]
    return utterance["assigned_voice"]

  def _assign_missing_voice(
      self, utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Assigns a cloned voice if missing in the utterance metadata.

    Args:
      utterance: A dictionary containing utterance metadata.

    Returns:
      The updated utterance metadata with the assigned voice.
    """
    if not self.elevenlabs_clone_voices:
      return utterance
    utterance.update(
        dict(assigned_voice=self.cloned_voices[utterance["speaker_id"]])
    )
    return utterance

  def _run_text_to_speech(
      self, utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Converts the translated text to speech using the chosen TTS engine.

    Args:
      utterance: A dictionary containing utterance metadata.

    Returns:
      The updated utterance metadata with the path to the dubbed audio.
    """
    if not utterance["for_dubbing"]:
      dubbed_path = utterance["path"]
    elif utterance["for_dubbing"] and not self.use_elevenlabs:
      dubbed_path = convert_text_to_speech(
          client=self.client,
          assigned_google_voice=self._find_voice(utterance),
          target_language=self.target_language,
          output_filename=self._assign_output_path(utterance),
          text=utterance["translated_text"],
          pitch=utterance["pitch"],
          speed=utterance["speed"],
          volume_gain_db=utterance["volume_gain_db"],
      )
    elif utterance["for_dubbing"] and self.use_elevenlabs:
      dubbed_path = elevenlabs_convert_text_to_speech(
          client=self.client,
          model=self.elevenlabs_model,
          assigned_elevenlabs_voice=self._find_voice(utterance),
          output_filename=self._assign_output_path(utterance),
          text=utterance["translated_text"],
          target_language=self.target_language,
          stability=utterance["stability"],
          similarity_boost=utterance["similarity_boost"],
          style=utterance["style"],
          use_speaker_boost=utterance["use_speaker_boost"],
      )
    utterance.update(dict(dubbed_path=dubbed_path))
    return utterance

  def _verify_run_adjust_speed_elevenlabs_google(
      self, utterance: Mapping[str, str | float]
  ) -> bool:
    """Verifies if audio speed adjustment is needed for ElevenLabs or specific Google voices.

    Args:
      utterance: A dictionary containing utterance metadata.

    Returns:
      True if adjustment is needed, False otherwise.
    """
    condition_one = self.adjust_speed and self.use_elevenlabs
    condition_two = (
        self.adjust_speed and _EXCEPTION_VOICE in utterance["assigned_voice"]
    )
    return condition_one or condition_two

  def _verify_run_adjust_speed_google(
      self, utterance: Mapping[str, str | float], speed: float
  ) -> bool:
    """Verifies if audio speed adjustment is needed for Google voices (excluding specific ones).

    Args:
      utterance: A dictionary containing utterance metadata.
      speed: The calculated speed for the utterance.

    Returns:
      True if adjustment is needed, False otherwise.
    """
    condition_one = (
        self.adjust_speed
        and _EXCEPTION_VOICE not in utterance["assigned_voice"]
    )
    return speed != 1.0 and not self.use_elevenlabs and condition_one

  def _run_adjust_speed(
      self, *, utterance: Mapping[str, str | float], speed: float
  ) -> Mapping[str, str | float]:
    """Adjusts the speed of the dubbed audio using the `adjust_audio_speed` function.

    Args:
      utterance: A dictionary containing utterance metadata.
      speed: The target speed for the audio.

    Returns:
      The updated utterance metadata with the adjusted audio.
    """
    chunk_size = utterance.get("chunk_size", _DEFAULT_CHUNK_SIZE)
    adjust_audio_speed(
        speed=speed,
        dubbed_path=utterance["dubbed_path"],
        chunk_size=chunk_size,
    )
    utterance.update(dict(chunk_size=chunk_size))
    return utterance

  def _adjust_speed(
      self, utterance: Mapping[str, str | float]
  ) -> Mapping[str, str | float]:
    """Adjusts the speed of the dubbed audio to match the original utterance length.

    This method calculates the required speed adjustment and applies it to the
    dubbed audio.
    It handles different scenarios based on the TTS engine used and whether
    specific voices require
    different treatment.

    Args:
      utterance: A dictionary containing utterance metadata.

    Returns:
      The updated utterance metadata with the speed-adjusted audio.
    """
    reference_length = utterance["end"] - utterance["start"]
    speed = calculate_target_utterance_speed(
        reference_length=reference_length, dubbed_file=utterance["dubbed_path"]
    )
    if self._verify_run_adjust_speed_elevenlabs_google(utterance):
      self._run_adjust_speed(utterance=utterance, speed=speed)
    if self._verify_run_adjust_speed_google(utterance, speed=speed):
      convert_text_to_speech(
          client=self.client,
          assigned_google_voice=self._find_voice(utterance),
          target_language=self.target_language,
          output_filename=self._assign_output_path(utterance),
          text=utterance["translated_text"],
          pitch=utterance["pitch"],
          speed=speed,
          volume_gain_db=utterance["volume_gain_db"],
      )
    utterance.update(dict(speed=speed))
    return utterance

  def dub_all_utterances(self) -> Sequence[Mapping[str, str | float]]:
    """Dubs all utterances in the `utterance_metadata`.

    This method iterates through the `utterance_metadata`, performs voice
    cloning if necessary,
    converts the translated text to speech, adjusts the speed of the dubbed
    audio, and returns
    the updated metadata with the paths to the dubbed audio files.

    Returns:
      A sequence of dictionaries containing the updated utterance metadata.
    """
    self.cloned_voices = self._clone_voices()
    utterance_metadata_copy = self.utterance_metadata.copy()
    updated_utterance_metadata = []
    for utterance in utterance_metadata_copy:
      utterance_with_voice_assignment = self._assign_missing_voice(utterance)
      dubbed_utterance = self._run_text_to_speech(
          utterance_with_voice_assignment
      )
      final_utterance = self._adjust_speed(dubbed_utterance)
      updated_utterance_metadata.append(final_utterance)
    return updated_utterance_metadata

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

import os
from typing import Final, Mapping, Sequence
from google.cloud import texttospeech
from pydub import AudioSegment
import tensorflow as tf
from absl import logging

_SSML_MALE: Final[str] = "Male"
_SSML_FEMALE: Final[str] = "Female"
_SSML_NEUTRAL: Final[str] = "Neutral"
_PREFERRED_VOICES: Final[Sequence[str]] = (
    "Journey",
    "Studio",
    "Wavenet",
    "Polyglot",
    "News",
    "Neural2",
    "Standard",
)
_DEFAULT_PITCH: Final[float] = -4.5
_DEFAULT_VOLUME_GAIN_DB: Final[float] = 16.0
_DEFAULT_SPEAKING_RATE: Final[float] = 1.0
_MINIMUM_DURATION: Final[float] = 1.0


def list_available_voices(
    language_code: str, client: texttospeech.TextToSpeechClient
) -> Mapping[str, str]:
  """Lists available voices for a given language code.

  Args:
      language_code: The language code to list voices for. It must be ISO 3166-1
        alpha-2 country code.
      client: A TextToSpeechClient object.

  Returns:
      A dictionary mapping voice names to their genders.
  """

  request = texttospeech.ListVoicesRequest(language_code=language_code)
  response = client.list_voices(request=request)
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


def assign_voices(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    target_language: str,
    client: texttospeech.TextToSpeechClient,
    preferred_voices: Sequence[str] = _PREFERRED_VOICES,
    fallback_no_preferred_category_match: bool = False,
) -> Mapping[str, str | None]:
  """Assigns voices to speakers based on preferred voices and available voices.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "text", "start", "end", "speaker_id",
        "ssml_gender", "translated_text", "for_dubbing" and "path".
      target_language: The target language (ISO 3166-1 alpha-2).
      client: A TextToSpeechClient object.
      preferred_voices: An optional list of preferred voice names.
      fallback_no_preferred_category_match: If True, assigns None if no voice
        matches preferred category.

  Returns:
      A mapping of unique speaker IDs to assigned voice names, or None if no
      preferred voice was available or fallback_no_preferred_category_match is
      True.
  """

  unique_speaker_mapping = {
      item["speaker_id"]: item["ssml_gender"] for item in utterance_metadata
  }
  if preferred_voices is None:
    return {speaker_id: None for speaker_id in unique_speaker_mapping}
  available_voices = list_available_voices(
      language_code=target_language, client=client
  )
  available_voices_names = list(available_voices.keys())
  grouped_available_preferred_voices = {}
  for preferred_voice in preferred_voices:
    available_preferred_voices = [
        voice for voice in available_voices_names if preferred_voice in voice
    ]
    grouped_available_preferred_voices.update(
        {preferred_voice: available_preferred_voices}
    )
  already_assigned_voices = {"Male": set(), "Female": set()}
  voice_assignment = {}
  for speaker_id, ssml_gender in unique_speaker_mapping.items():
    preferred_category_matched = False
    for (
        preferred_category_voices
    ) in grouped_available_preferred_voices.values():
      if not preferred_category_voices:
        continue
      for preferred_voice in preferred_category_voices:
        if (
            ssml_gender == available_voices[preferred_voice]
            and preferred_voice not in already_assigned_voices[ssml_gender]
        ):
          voice_assignment[speaker_id] = preferred_voice
          already_assigned_voices[ssml_gender].add(preferred_voice)
          preferred_category_matched = True
          break
      if speaker_id in voice_assignment:
        break
    if not preferred_category_matched and fallback_no_preferred_category_match:
      voice_assignment[speaker_id] = None
  for speaker_id in unique_speaker_mapping:
    if speaker_id not in voice_assignment:
      voice_assignment[speaker_id] = None
  return voice_assignment


def update_utterance_metadata(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    assigned_voices: Mapping[str, str],
) -> Sequence[Mapping[str, str | float]]:
  """Updates utterance metadata with assigned Google voices.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "text", "start", "end", "speaker_id",
        "ssml_gender", "translated_text", "for_dubbing" and "path".
      assigned_voices: Mapping mapping speaker IDs to assigned Google voices.

  Returns:
      Sequence of updated utterance metadata dictionaries.
  """
  updated_utterance_metadata = []
  for metadata_item in utterance_metadata:
    new_utterance = metadata_item.copy()
    speaker_id = new_utterance.get("speaker_id")
    new_utterance["assigned_google_voice"] = assigned_voices.get(speaker_id)
    updated_utterance_metadata.append(new_utterance)
  return updated_utterance_metadata


def convert_text_to_speech(
    client: texttospeech.TextToSpeechClient,
    assigned_google_voice: str,
    target_language: str,
    output_filename: str,
    text: str,
    pitch: float = _DEFAULT_PITCH,
    volume_gain_db: float = _DEFAULT_VOLUME_GAIN_DB,
    speaking_rate: float = _DEFAULT_SPEAKING_RATE,
) -> str:
  """Converts text to speech using Google Cloud Text-to-Speech API.

  Args:
      client: The TextToSpeechClient object to use.
      assigned_google_voice: The name of the Google Cloud voice to use.
      target_language: The target language (ISO 3166-1 alpha-2).
      output_filename: The name of the output MP3 file.
      text: The text to be converted to speech.
      pitch: The pitch of the synthesized speech.
      volume_gain_db: The volume gain of the synthesized speech.
      speaking_rate: The speaking rate of the synthesized speech.

  Returns:
      The name of the output file.
  """

  input_text = texttospeech.SynthesisInput(text=text)
  voice_selection = texttospeech.VoiceSelectionParams(
      name=assigned_google_voice,
      language_code=target_language,
  )
  audio_config = texttospeech.AudioConfig(
      audio_encoding=texttospeech.AudioEncoding.MP3,
      pitch=pitch,
      volume_gain_db=volume_gain_db,
      speaking_rate=speaking_rate,
  )

  response = client.synthesize_speech(
      input=input_text,
      voice=voice_selection,
      audio_config=audio_config,
  )

  with tf.io.gfile.GFile(output_filename, "wb") as out:
    out.write(response.audio_content)

  return output_filename


def adjust_audio_speed(
    *,
    input_mp3_path: str,
    target_duration: float,
    mininimum_duration: float = _MINIMUM_DURATION,
) -> None:
  """Adjusts the speed of an MP3 file to match the target duration.

  The input files where the target length is less than 1s, won't be modified.

  Args:
      input_mp3_path: The path to the input MP3 file.
      target_duration: The desired duration in seconds.
      mininimum_duration: The minimum target duration of either the input MP3 of
        the target duration for the adjustment process to take place. Otherwise,
        the input MP3 duration won't be modified.
  """

  if target_duration <= 0.0:
    raise ValueError(
        "The target duration must be more than 0.0 seconds. Got"
        f" {target_duration}."
    )
  audio = AudioSegment.from_mp3(input_mp3_path)
  if audio.duration_seconds <= 0.0:
    raise ValueError(
        "The input audio duration must be more than 0.0 seconds. It's"
        f" {audio.duration_seconds}."
    )
  if (
      target_duration <= mininimum_duration
      or audio.duration_seconds <= mininimum_duration
  ):
    return
  speed_factor = audio.duration_seconds / target_duration
  new_audio = audio.speedup(speed_factor)
  new_audio.export(input_mp3_path, format="mp3")


def dub_utterances(
    *,
    client: texttospeech.TextToSpeechClient,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    output_directory: str,
    target_language: str,
    adjust_speed: bool = True,
) -> Sequence[Mapping[str, str | float]]:
  """Processes a list of utterance metadata, generating dubbed audio files.

  Args:
      client: The TextToSpeechClient object to use.
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "text", "start", "end", "speaker_id",
        "ssml_gender", "translated_text", "assigned_google_voice", "for_dubbing"
        and "path".
      output_directory: Path to the directory for output files.
      target_language: The target language (ISO 3166-1 alpha-2).
      adjust_speed: Whether to either speed up or slow down utterances to match
        the duration of the utterances in the source language.

  Returns:
      List of processed utterance metadata with updated "dubbed_path".
  """

  updated_utterance_metadata = []
  for utterance in utterance_metadata:
    if not utterance["for_dubbing"]:
      dubbed_path = utterance["path"]
    else:
      path = utterance["path"]
      text = utterance["translated_text"]
      assigned_google_voice = utterance["assigned_google_voice"]
      duration = utterance["end"] - utterance["start"]
      base_filename = os.path.splitext(os.path.basename(path))[0]
      output_filename = os.path.join(
          output_directory, f"dubbed_{base_filename}.mp3"
      )
      dubbed_path = convert_text_to_speech(
          client=client,
          assigned_google_voice=assigned_google_voice,
          target_language=target_language,
          output_filename=output_filename,
          text=text,
      )
    if adjust_speed:
      adjust_audio_speed(input_mp3_path=dubbed_path, target_duration=duration)
    utterance_copy = utterance.copy()
    utterance_copy["dubbed_path"] = dubbed_path
    updated_utterance_metadata.append(utterance_copy)
  return updated_utterance_metadata

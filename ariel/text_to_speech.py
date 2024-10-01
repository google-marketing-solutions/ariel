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

import io
import os
from typing import Final, Mapping, Sequence
from absl import logging
from elevenlabs import VoiceSettings, save
from elevenlabs.client import ElevenLabs
from elevenlabs.types.voice import Voice
from google.cloud import texttospeech
from pydub import AudioSegment
from pydub.effects import speedup
import tensorflow as tf

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
_DEFAULT_CHUNK_SIZE: Final[int] = 150


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
    preferred_voices: Sequence[str] = _DEFAULT_PREFERRED_GOOGLE_VOICES,
) -> Mapping[str, str | None]:
  """Assigns voices to speakers based on preferred voices and available voices.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "text", "start", "end", "speaker_id",
        "ssml_gender", "translated_text", "for_dubbing", "path" and optionally
        "vocals_path"
      target_language: The target language (ISO 3166-1 alpha-2).
      client: A TextToSpeechClient object.
      preferred_voices: An optional list of preferred voice names. Defaults to
        _DEFAULT_PREFERRED_GOOGLE_VOICES.

  Returns:
      A mapping of unique speaker IDs to assigned voice names, or raises an
      error if no voice
      could be assigned.

  Raises:
      A value error when no voice can be allocated to any of the speakers.
  """

  if not preferred_voices:
    preferred_voices = _DEFAULT_PREFERRED_GOOGLE_VOICES
    logging.info(
        "Preferred voices were None, defaulting to:"
        f" {','.join(preferred_voices)}"
    )
  unique_speaker_mapping = {
      item["speaker_id"]: item["ssml_gender"] for item in utterance_metadata
  }
  available_voices = list_available_voices(
      language_code=target_language, client=client
  )
  available_voices_names = list(available_voices.keys())
  grouped_available_preferred_voices = {}
  for preferred_voice in preferred_voices:
    available_preferred_voices = [
        voice for voice in available_voices_names if preferred_voice in voice
    ]
    grouped_available_preferred_voices[preferred_voice] = (
        available_preferred_voices
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
    if not preferred_category_matched:
      raise ValueError(
          f"Could not allocate a voice for speaker_id {speaker_id} with"
          f" ssml_gender {ssml_gender}"
      )
  return voice_assignment


def elevenlabs_assign_voices(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    client: ElevenLabs,
    preferred_voices: Sequence[str] = None,
) -> Mapping[str, str | None]:
  """Assigns voices to speakers based on preferred voices and available voices.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "start", "end", "chunk_path", "translated_text",
        "speaker_id", "ssml_gender".
      client: An ElevenLabs object.
      preferred_voices: Optional; A list of preferred voice names (e.g.,
        "Rachel").

  Returns:
      A mapping of unique speaker IDs to assigned voice names.

  Raises:
      ValueError: If no suitable voice is available for a speaker.
  """
  unique_speaker_mapping = {
      item["speaker_id"]: item["ssml_gender"] for item in utterance_metadata
  }

  available_voices = client.voices.get_all().voices

  if not preferred_voices:
    preferred_voices = [voice.name for voice in available_voices]
    logging.info("No preferred voices provided. Using all available voices.")

  voice_assignment = {}
  already_assigned_voices = {"Male": set(), "Female": set()}

  for speaker_id, ssml_gender in unique_speaker_mapping.items():
    preferred_category_matched = False

    for preferred_voice in preferred_voices:
      voice_info = next(
          (
              voice
              for voice in available_voices
              if voice.name == preferred_voice
          ),
          None,
      )

      if (
          voice_info
          and voice_info.labels["gender"] == ssml_gender.lower()
          and preferred_voice not in already_assigned_voices[ssml_gender]
      ):
        voice_assignment[speaker_id] = preferred_voice
        already_assigned_voices[ssml_gender].add(preferred_voice)
        preferred_category_matched = True
        break

    if not preferred_category_matched:
      for voice_info in available_voices:
        if (
            voice_info.labels["gender"] == ssml_gender.lower()
            and voice_info.name not in already_assigned_voices[ssml_gender]
        ):
          voice_assignment[speaker_id] = voice_info.name
          already_assigned_voices[ssml_gender].add(voice_info.name)
          preferred_category_matched = True
          break

    if not preferred_category_matched:
      raise ValueError(
          f"No suitable voice found for speaker_id {speaker_id} with gender"
          f" {ssml_gender}"
      )

  return voice_assignment


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


def elevenlabs_convert_text_to_speech(
    *,
    client: ElevenLabs,
    model: str,
    assigned_elevenlabs_voice: str,
    output_filename: str,
    text: str,
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
  audio = client.generate(
      model=model,
      voice=assigned_elevenlabs_voice,
      text=text,
      voice_settings=VoiceSettings(
          stability=stability,
          similarity_boost=similarity_boost,
          style=style,
          use_speaker_boost=use_speaker_boost,
      ),
  )
  save(audio, output_filename)
  return output_filename


def create_speaker_to_paths_mapping(
    utterance_metadata: Sequence[Mapping[str, float | str]],
) -> Mapping[str, Sequence[str]]:
  """Organizes a list of utterance metadata dictionaries into a speaker-to-paths mapping.

  Args:
      utterance_metadata: A list of dictionaries with 'speaker_id' and
        'voice_path' keys.

  Returns:
      A mapping between speaker IDs to lists of file paths.
  """

  speaker_to_paths_mapping = {}
  for utterance in utterance_metadata:
    speaker_id = utterance["speaker_id"]
    if speaker_id not in speaker_to_paths_mapping:
      speaker_to_paths_mapping[speaker_id] = []
    speaker_to_paths_mapping[speaker_id].append(utterance["vocals_path"])
  return speaker_to_paths_mapping


def elevenlabs_run_clone_voices(
    *, client: ElevenLabs, speaker_to_paths_mapping: Mapping[str, Sequence[str]]
) -> Mapping[str, Voice]:
  """Clones voices for speakers using ElevenLabs based on utterance metadata and file paths.

  Args:
      client: An authenticated ElevenLabs client object for API interaction.
      speaker_to_paths_mapping: A mapping between speaker IDs to the sequnces
        with file paths of the source utterances.

  Returns:
      A mapping between speaker IDs to their cloned voices.
  """
  speaker_to_voices_mapping = {}
  for speaker_id, paths in speaker_to_paths_mapping.items():
    voice = client.clone(
        name=f"{speaker_id}",
        description=f"Voice for {speaker_id}",
        files=paths,
    )
    speaker_to_voices_mapping[speaker_id] = voice
  return speaker_to_voices_mapping


def adjust_audio_speed(
    *,
    reference_length: float,
    dubbed_file: str,
    speed: float | None = None,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
) -> None:
  """Adjusts the speed of an MP3 file to match the reference file duration.

  The speed will not be adjusted if the dubbed file has a duration that
  is the same or shorter than the duration of the reference file.

  Args:
      reference_length: The reference length of an audio chunk.
      dubbed_file: The path to the dubbed MP3 file.
      speed: The desired speed in seconds. If None it will be determined based
        on the duration of the reference_file and dubbed_file.
      chunk_size: Duration of audio chunks (in ms) to preserve in the
        adjustement process.
  """

  dubbed_audio = AudioSegment.from_file(dubbed_file)
  if not speed:
    speed = calculate_target_utterance_speed(
        reference_length=reference_length, dubbed_file=dubbed_file
    )
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
  output_audio.export(dubbed_file, format="mp3")


def dub_utterances(
    *,
    client: texttospeech.TextToSpeechClient | ElevenLabs,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    output_directory: str,
    target_language: str,
    adjust_speed: bool = True,
    use_elevenlabs: bool = False,
    elevenlabs_model: str = _DEFAULT_ELEVENLABS_MODEL,
    elevenlabs_clone_voices: bool = False,
) -> Sequence[Mapping[str, str | float]]:
  """Processes a list of utterance metadata, generating dubbed audio files.

  Args:
      client: The TextToSpeechClient or ElevenLabs object to use.
      utterance_metadata: A sequence of utterance metadata, each represented as
        a dictionary with keys: "text", "start", "end", "speaker_id",
        "ssml_gender", "translated_text", "assigned_google_voice",
        "for_dubbing", "path", "google_voice_pitch", "google_voice_speed",
        "google_voice_volume_gain_db" and optionally "vocals_path".
      output_directory: Path to the directory for output files.
      target_language: The target language (ISO 3166-1 alpha-2).
      adjust_speed: Whether to force speed up of utterances to match the
        duration of the utterances in the source language. Recommended when
        using ElevenLabs and Google's 'Journey' voices.
      use_elevenlabs: Whether to use ElevenLabs API for Text-To-Speech. If not
        Google's Text-To-Speech will be used.
      elevenlabs_model: The ElevenLabs model to use in the Text-To-Speech
        process.
      elevenlabs_clone_voices: Whether to clone source voices. It requires using
        ElevenLabs API.

  Returns:
      List of processed utterance metadata with updated "dubbed_path".

  Raises:
      ValueError: When 'elevenlabs_clone_voices' is True and 'use_elevenlabs' is
      False.
  """

  if elevenlabs_clone_voices:
    if not use_elevenlabs:
      raise ValueError("Voice cloning requires using ElevenLabs API.")
    speaker_to_paths_mapping = create_speaker_to_paths_mapping(
        utterance_metadata
    )
    speaker_to_voices_mapping = elevenlabs_run_clone_voices(
        client=client, speaker_to_paths_mapping=speaker_to_paths_mapping
    )
  updated_utterance_metadata = []
  for utterance in utterance_metadata:
    utterance_copy = utterance.copy()
    if not utterance_copy["for_dubbing"]:
      try:
        dubbed_path = utterance_copy["path"]
      except KeyError:
        dubbed_path = f"chunk_{utterance['start']}_{utterance['end']}.mp3"
    else:
      if elevenlabs_clone_voices:
        assigned_voice = speaker_to_voices_mapping[utterance_copy["speaker_id"]]
      else:
        assigned_voice = utterance_copy["assigned_voice"]
      reference_length = utterance_copy["end"] - utterance_copy["start"]
      text = utterance_copy["translated_text"]
      try:
        path = utterance_copy["path"]
        base_filename = os.path.splitext(os.path.basename(path))[0]
        output_filename = os.path.join(
            output_directory, f"dubbed_{base_filename}.mp3"
        )
      except KeyError:
        output_filename = os.path.join(
            output_directory,
            f"dubbed_chunk_{utterance['start']}_{utterance['end']}.mp3",
        )
      if use_elevenlabs:
        dubbed_path = elevenlabs_convert_text_to_speech(
            client=client,
            model=elevenlabs_model,
            assigned_elevenlabs_voice=assigned_voice,
            output_filename=output_filename,
            text=text,
            stability=utterance_copy["stability"],
            similarity_boost=utterance_copy["similarity_boost"],
            style=utterance_copy["style"],
            use_speaker_boost=utterance_copy["use_speaker_boost"],
        )
      else:
        dubbed_path = convert_text_to_speech(
            client=client,
            assigned_google_voice=assigned_voice,
            target_language=target_language,
            output_filename=output_filename,
            text=text,
            pitch=utterance_copy["pitch"],
            speed=utterance_copy["speed"],
            volume_gain_db=utterance_copy["volume_gain_db"],
        )
      condition_one = adjust_speed and use_elevenlabs
      assigned_voice = utterance_copy.get("assigned_voice", None)
      assigned_voice = assigned_voice if assigned_voice else ""
      condition_two = adjust_speed and _EXCEPTION_VOICE in assigned_voice
      speed = calculate_target_utterance_speed(
          reference_length=reference_length, dubbed_file=dubbed_path
      )
      if condition_one or condition_two:
        chunk_size = utterance_copy.get("chunk_size", _DEFAULT_CHUNK_SIZE)
        adjust_audio_speed(
            reference_length=reference_length,
            dubbed_file=dubbed_path,
            chunk_size=chunk_size,
        )
        utterance_copy["chunk_size"] = chunk_size
      condition_three = adjust_speed and _EXCEPTION_VOICE not in assigned_voice
      if speed != 1.0 and not use_elevenlabs and condition_three:
        utterance_copy["speed"] = speed
        dubbed_path = convert_text_to_speech(
            client=client,
            assigned_google_voice=assigned_voice,
            target_language=target_language,
            output_filename=output_filename,
            text=text,
            pitch=utterance_copy["pitch"],
            speed=speed,
            volume_gain_db=utterance_copy["volume_gain_db"],
        )
    utterance_copy["dubbed_path"] = dubbed_path
    updated_utterance_metadata.append(utterance_copy)
  return updated_utterance_metadata

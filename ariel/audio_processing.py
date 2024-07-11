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

"""An audio processing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import os
import re
import subprocess
from typing import Final
from typing import Final, Mapping, Sequence
from typing import Mapping, Sequence
from absl import logging
from pyannote.audio import Pipeline
from pydub import AudioSegment
import torch

_BACKGROUND_VOLUME_ADJUSTMENT: Final[float] = 5.0
_VOCALS_VOLUME_ADJUSTMENT: Final[float] = 0.0
_DEFAULT_DUBBED_VOCALS_AUDIO_FILE: Final[str] = "dubbed_vocals.mp3"
_DEFAULT_DUBBED_AUDIO_FILE: Final[str] = "dubbed_audio"
_DEFAULT_OUTPUT_FORMAT: Final[str] = ".mp3"
_SUPPORTED_DEVICES: Final[tuple[str, str]] = ("cpu", "cuda")
_TIMESTAMP_THRESHOLD: Final[float] = 0.001


def build_demucs_command(
    *,
    audio_file: str,
    output_directory: str,
    device: str = "cpu",
    shifts: int = 10,
    overlap: float = 0.25,
    mp3_bitrate: int = 320,
    mp3_preset: int = 2,
    jobs: int = 0,
    split: bool = True,
    segment: int | None = None,
    int24: bool = False,
    float32: bool = False,
    flac: bool = False,
    mp3: bool = True,
) -> str:
  """Builds the Demucs audio separation command.

  Args:
      audio_file: The path to the audio file to process.
      output_directory: The output directory for separated tracks.
      device: The device to use ("cuda" or "cpu").
      shifts: The number of random shifts for equivariant stabilization.
      overlap: The overlap between splits.
      mp3_bitrate: The bitrate of converted MP3 files.
      mp3_preset: The encoder preset for MP3 conversion.
      jobs: The number of jobs to run in parallel.
      split: Whether to split audio into chunks.
      segment: The split size for chunks (None for no splitting).
      int24: Save WAV output as 24 bits.
      float32: Save WAV output as float32.
      flac: Convert output to FLAC.
      mp3: Convert output to MP3.

  Returns:
      A string representing the constructed command.

  Raises:
      ValueError: If both int24 and float32 are set to True.
  """

  if int24 and float32:
    raise ValueError("Cannot set both int24 and float32 to True.")
  command_parts = [
      "python",
      "-m",
      "demucs.separate",
      "-o",
      f"'{output_directory}'",
      "--device",
      device,
      "--shifts",
      str(shifts),
      "--overlap",
      str(overlap),
      "-j",
      str(jobs),
      "--two-stems vocals",
  ]
  if not split:
    command_parts.append("--no-split")
  elif segment is not None:
    command_parts.extend(["--segment", str(segment)])
  if flac:
    command_parts.append("--flac")
  if mp3:
    command_parts.extend([
        "--mp3",
        "--mp3-bitrate",
        str(mp3_bitrate),
        "--mp3-preset",
        str(mp3_preset),
    ])
  if int24:
    command_parts.append("--int24")
  if float32:
    command_parts.append("--float32")
  command_parts.append(f"'{audio_file}'")
  return " ".join(command_parts)


class DemcusCommandError(Exception):
  pass


def execute_demcus_command(command: str) -> None:
  """Executes a Demucs command using subprocess.

  Demucs is a model using AI/ML to detach dialogues
  from the rest of the audio file.

  Args:
      command: The string representing the command to execute.
  """
  try:
    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, check=True
    )
    logging.info(result.stdout)
  except subprocess.CalledProcessError as e:
    raise DemcusCommandError(f"Error separating audio: {e}\n{e.stderr}")


def extract_command_info(command: str) -> tuple[str, str, str]:
  """Extracts folder name, output file extension, and input file name (without path) from a Demucs command.

  Args:
      command: The Demucs command string.

  Returns:
      tuple: A tuple containing (folder_name, output_file_extension,
      input_file_name).
  """
  folder_pattern = r"-o\s+(['\"]?)(.+?)\1"
  flac_pattern = r"--flac"
  mp3_pattern = r"--mp3"
  int24_or_float32_pattern = r"--(int24|float32)"
  input_file_pattern = r"['\"]?(\w+\.\w+)['\"]?$|\s(\w+\.\w+)$"
  folder_match = re.search(folder_pattern, command)
  flac_match = re.search(flac_pattern, command)
  mp3_match = re.search(mp3_pattern, command)
  int24_or_float32_match = re.search(int24_or_float32_pattern, command)
  input_file_match = re.search(input_file_pattern, command)
  output_directory = folder_match.group(2) if folder_match else ""
  input_file_name_with_ext = (
      (input_file_match.group(1) or input_file_match.group(2))
      if input_file_match
      else ""
  )
  input_file_name_no_ext = (
      os.path.splitext(input_file_name_with_ext)[0] if input_file_match else ""
  )
  if flac_match:
    output_file_extension = ".flac"
  elif mp3_match:
    output_file_extension = ".mp3"
  elif int24_or_float32_match:
    output_file_extension = ".wav"
  else:
    output_file_extension = ".wav"
  return output_directory, output_file_extension, input_file_name_no_ext


def assemble_split_audio_file_paths(command: str) -> tuple[str, str]:
  """Returns paths to the audio files with vocals and no vocals.

    Args:
        command: The Demucs command string.

  Returns:
      A tuple with a path to the file with the audio with vocals only
      and the other with the background sound only.
  """
  output_directory, output_file_extension, input_file_name = (
      extract_command_info(command)
  )
  audio_vocals_file = f"{output_directory}/htdemucs/{input_file_name}/vocals{output_file_extension}"
  audio_background_file = f"{output_directory}/htdemucs/{input_file_name}/no_vocals{output_file_extension}"
  return audio_vocals_file, audio_background_file


def create_pyannote_timestamps(
    *,
    audio_file: str,
    number_of_speakers: int,
    pipeline: Pipeline,
    device: str = "cpu",
) -> Sequence[Mapping[str, float]]:
  """Creates timestamps from a vocals file using Pyannote speaker diarization.

  Args:
      audio_file: The path to the audio file with vocals.
      number_of_speakers: The number of speakers in the vocal audio file.
      pipeline: Pre-loaded Pyannote Pipeline object.
      device: The device to use during the process.

  Returns:
      A list of dictionaries containing start and end timestamps for each
      speaker segment.
  """
  if device not in _SUPPORTED_DEVICES:
    raise ValueError(
        "The device must be either (' or ').join(_SUPPORTED_DEVICES). Got:"
        f" {device}"
    )
  if device == "cuda":
    pipeline.to(torch.device("cuda"))
  diarization = pipeline(audio_file, num_speakers=number_of_speakers)
  utterance_metadata = [
      {"start": segment.start, "end": segment.end}
      for segment, _, _ in diarization.itertracks(yield_label=True)
  ]
  return utterance_metadata


def merge_utterances(
    *,
    utterance_metadata: Sequence[Mapping[str, float]],
    minimum_merge_threshold: float = _TIMESTAMP_THRESHOLD,
) -> Sequence[Mapping[str, str | float]]:
  """Merges utterances that are within the specified timestamp threshold.

  Args:
    utterance_metadata: A sequence of utterance metadata, each represented as a
      dictionary with keys: "start" and "end".
    minimum_merge_threshold: The maximum time difference between the end of one
      utterance and the start of the next for them to be considered mergeable.

  Returns:
    A list of merged utterance metadata.
  """

  merged_utterances = []
  index = 0
  while index < len(utterance_metadata):
    current_utterance = utterance_metadata[index]
    merged_utterance = current_utterance.copy()
    next_index = index + 1
    while (
        next_index < len(utterance_metadata)
        and utterance_metadata[next_index]["start"] - current_utterance["end"]
        < minimum_merge_threshold
    ):
      merged_utterance["end"] = utterance_metadata[next_index]["end"]
      next_index += 1
    merged_utterances.append(merged_utterance)
    index = next_index
  return merged_utterances


def cut_and_save_audio(
    *,
    utterance_metadata: Sequence[Mapping[str, float]],
    audio_file: str,
    output_directory: str,
    elevenlabs_clone_voices: bool = False,
) -> Sequence[Mapping[str, float]]:
  """Cuts an audio file into chunks based on provided time ranges and saves each chunk to a file.

  Args:
      utterance_metadata: The list of dictionaries, each containing 'start' and
        'end' times in seconds.
      audio_file: The path to the audio file to be cut.
      output_directory: The path to the folder where the audio chunks will be
        saved.
      elevenlabs_clone_voices: Whether to clone source voices. It requires using
        ElevenLabs API.

  Returns:
      A list of dictionaries, each containing the path to the saved chunk, and
      the original start and end times.
  """

  audio = AudioSegment.from_file(audio_file)
  key = "vocals_path" if elevenlabs_clone_voices else "path"
  prefix = "vocals_chunk" if elevenlabs_clone_voices else "chunk"
  updated_utterance_metadata = []
  for utterance in utterance_metadata:
    start_time_ms = int(utterance["start"] * 1000)
    end_time_ms = int(utterance["end"] * 1000)
    chunk = audio[start_time_ms:end_time_ms]
    chunk_filename = f"{prefix}_{utterance['start']}_{utterance['end']}.mp3"
    chunk_path = f"{output_directory}/{chunk_filename}"
    chunk.export(chunk_path, format="mp3")
    utterance_copy = utterance.copy()
    utterance_copy[key] = chunk_path
    updated_utterance_metadata.append(utterance_copy)
  return updated_utterance_metadata


def insert_audio_at_timestamps(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    background_audio_file: str,
    output_directory: str,
) -> str:
  """Inserts audio chunks into a background audio track at specified timestamps.

  Args:
    utterance_metadata: A sequence of utterance metadata, each represented as a
      dictionary with keys: "text", "start", "stop", "speaker_id",
      "ssml_gender", "translated_text", "assigned_google_voice", "for_dubbing",
      "path" and optionally "vocals_path".
    background_audio_file: Path to the background audio file.
    output_directory: Path to save the output audio file.

  Returns:
    The path to the output audio file.
  """

  background_audio = AudioSegment.from_mp3(background_audio_file)
  total_duration = background_audio.duration_seconds
  output_audio = AudioSegment.silent(duration=total_duration * 1000)
  for item in utterance_metadata:
    audio_chunk = AudioSegment.from_mp3(item["dubbed_path"])
    start_time = int(item["start"] * 1000)
    output_audio = output_audio.overlay(
        audio_chunk, position=start_time, loop=False
    )
  dubbed_vocals_audio_file = os.path.join(
      output_directory, _DEFAULT_DUBBED_VOCALS_AUDIO_FILE
  )
  output_audio.export(dubbed_vocals_audio_file, format="mp3")
  return dubbed_vocals_audio_file


def merge_background_and_vocals(
    *,
    background_audio_file: str,
    dubbed_vocals_audio_file: str,
    output_directory: str,
    target_language: str,
) -> str:
  """Mixes background music and vocals tracks, normalizes the volume, and exports the result.

  Args:
      background_audio_file: Path to the background music MP3 file.
      dubbed_vocals_audio_file: Path to the vocals MP3 file.
      output_directory: Path to save the mixed MP3 file.
      target_language: The language to dub the ad into. It must be ISO 3166-1
        alpha-2 country code.

  Returns:
    The path to the output audio file with merged dubbed vocals and original
    background audio.
  """

  background = AudioSegment.from_mp3(background_audio_file)
  vocals = AudioSegment.from_mp3(dubbed_vocals_audio_file)
  background = background.normalize()
  vocals = vocals.normalize()
  background = background - _BACKGROUND_VOLUME_ADJUSTMENT
  vocals = vocals - _VOCALS_VOLUME_ADJUSTMENT
  shortest_length = min(len(background), len(vocals))
  background = background[:shortest_length]
  vocals = vocals[:shortest_length]
  mixed_audio = background.overlay(vocals)
  target_language_suffix = "_" + target_language.replace("-", "_").lower()
  dubbed_audio_file = os.path.join(
      output_directory,
      _DEFAULT_DUBBED_AUDIO_FILE
      + target_language_suffix
      + _DEFAULT_OUTPUT_FORMAT,
  )
  mixed_audio.export(dubbed_audio_file, format="mp3")
  return dubbed_audio_file

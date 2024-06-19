"""An audio processing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import subprocess
from typing import Final, Mapping, Sequence
from absl import logging
from typing import Final
from typing import Mapping, Sequence
from pyannote.audio import Pipeline
from pydub import AudioSegment
import torch
import os
import re

_BACKGROUND_VOLUME_ADJUSTMENT: Final[float] = 5.0
_VOCALS_VOLUME_ADJUSTMENT: Final[float] = 0.0
_DEFAULT_DUBBED_VOCALS_AUDIO_FILE: Final[str] = "dubbed_vocals.mp3"
_DEFAULT_DUBBED_AUDIO_FILE: Final[str] = "dubbed_audio.mp3"



def build_demucs_command(
    audio_file: str,
    output_directory: str,
    device: str = "cpu",
    shifts: int = 10,
    overlap: float = 0.25,
    clip_mode: str = "rescale",
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
      clip_mode: The clipping strategy ("rescale", "clamp", or "none").
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
      "python3",
      "-m",
      "demucs.separate",
      "-o",
      output_directory,
      "--device",
      device,
      "--shifts",
      str(shifts),
      "--overlap",
      str(overlap),
      "--clip_mode",
      clip_mode,
      "-j",
      str(jobs),
      "--two-stems",
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
  command_parts.append(audio_file)
  return " ".join(command_parts)


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
    logging.error(f"Error separating audio: {e}\n{e.stderr}")


def extract_command_info(command: str) -> tuple[str, str, str]:
  """Extracts folder name, output file extension, and input file name from a Demucs command.

  Args:
      command: The Demucs command string.

  Returns:
      tuple: A tuple containing (folder_name, output_file_extension,
      input_file_name).
  """

  folder_pattern = r"-o\s+(\S+)"
  flac_pattern = r"--flac"
  mp3_pattern = r"--mp3"
  int24_or_float32_pattern = r"--(int24|float32)"
  input_file_pattern = r"(\S+)$"
  folder_match = re.search(folder_pattern, command)
  flac_match = re.search(flac_pattern, command)
  mp3_match = re.search(mp3_pattern, command)
  int24_or_float32_match = re.search(int24_or_float32_pattern, command)
  input_file_match = re.search(input_file_pattern, command)

  outout_directory = folder_match.group(1)
  input_file_name_with_ext = input_file_match.group(1)
  input_file_name_no_ext = os.path.splitext(input_file_name_with_ext)[0]
  if flac_match:
    output_file_extension = ".flac"
  elif mp3_match:
    output_file_extension = ".mp3"
  elif int24_or_float32_match:
    output_file_extension = ".wav"
  else:
    output_file_extension = ".wav"
  return outout_directory, output_file_extension, input_file_name_no_ext


def assemble_split_audio_file_paths(command: str) -> tuple[str, str]:
  """Returns paths to the audio files with vocals and no vocals.

    Args:
        command: The Demucs command string.

  Returns:
      A tuple with a path to the file with the audio with vocals only
      and the other with the background sound only.
  """
  outout_directory, output_file_extension, input_file_name = (
      extract_command_info(command)
  )
  audio_vocals_file = f"{outout_directory}/htdemucs/{input_file_name}_audio/vocals{output_file_extension}"
  audio_background_file = f"{outout_directory}/htdemucs/{input_file_name}_audio/no_vocals{output_file_extension}"
  return audio_vocals_file, audio_background_file


def create_pyannote_timestamps(
    *,
    audio_file: str,
    number_of_speakers: int,
    pipeline: Pipeline,
) -> Sequence[Mapping[str, float]]:
  """Creates timestamps from a vocals file using Pyannote speaker diarization.

  Args:
      audio_file: The path to the audio file with vocals.
      number_of_speakers: The number of speakers in the vocal audio file.
      pipeline: Pre-loaded Pyannote Pipeline object.

  Returns:
      A list of dictionaries containing start and end timestamps for each
      speaker segment.
  """
  if torch.cuda.is_available():
    pipeline.to(torch.device("cuda"))
  diarization = pipeline(audio_file, num_speakers=number_of_speakers)
  utterance_metadata = [
      {"start": segment.start, "end": segment.end}
      for segment, _, _ in diarization.itertracks(yield_label=True)
  ]
  return utterance_metadata


def cut_and_save_audio(
    *,
    utterance_metadata: Sequence[Mapping[str, float]],
    audio_file: str,
    output_directory: str,
) -> Sequence[Mapping[str, float]]:
  """Cuts an audio file into chunks based on provided time ranges and saves each chunk to a file.

  Args:
      utterance_metadata: The list of dictionaries, each containing 'start' and
        'end' times in seconds.
      audio_file: The path to the audio file to be cut.
      output_directory: The path to the folder where the audio chunks will be
        saved.

  Returns:
      A list of dictionaries, each containing the path to the saved chunk, and
      the original start and end times.
  """

  audio = AudioSegment.from_file(audio_file)
  updated_utterance_metadata = []

  for item in utterance_metadata:
    start_time_ms = int(item["start"] * 1000)
    end_time_ms = int(item["end"] * 1000)
    chunk = audio[start_time_ms:end_time_ms]

    chunk_filename = f"chunk_{item['start']}_{item['end']}.mp3"
    chunk_path = f"{output_directory}/{chunk_filename}"

    chunk.export(chunk_path, format="mp3")
    updated_utterance_metadata.append({
        "path": chunk_path,
        "start": item["start"],
        "end": item["end"],
    })

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
      "ssml_gender", "translated_text", "assigned_google_voice" and "path".
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
) -> str:
  """Mixes background music and vocals tracks, normalizes the volume, and exports the result.

  Args:
      background_audio_file: Path to the background music MP3 file.
      dubbed_vocals_audio_file: Path to the vocals MP3 file.
      output_directory: Path to save the mixed MP3 file.

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
  dubbed_audio_file = os.path.join(output_directory, _DEFAULT_DUBBED_AUDIO_FILE)
  mixed_audio.export(dubbed_audio_file, format="mp3")
  return dubbed_audio_file

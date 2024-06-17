"""An audio processing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import subprocess
from absl import logging
from typing import Mapping, Sequence
from pyannote.audio import Pipeline
from pydub import AudioSegment
import torch


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
    mp3: bool = False,
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
  elif mp3:
    command_parts.extend([
        "--mp3",
        "--mp3-bitrate",
        str(mp3_bitrate),
        "--mp3-preset",
        str(mp3_preset),
    ])
  elif int24:
    command_parts.append("--int24")
  elif float32:
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
    logging.warning(f"Error separating audio: {e}\n{e.stderr}")


def create_pyannote_timestamps(
    *,
    vocals_filepath: str,
    number_of_speakers: int,
    pipeline: Pipeline,
) -> Sequence[Mapping[str, float]]:
  """Creates timestamps from a vocals file using Pyannote speaker diarization.

  Args:
      vocals_filepath: The path to the vocals file.
      number_of_speakers: The number of speakers in the vocal audio file.
      pipeline: Pre-loaded Pyannote Pipeline object.

  Returns:
      A list of dictionaries containing start and end timestamps for each
      speaker segment.
  """
  if torch.cuda.is_available():
    pipeline.to(torch.device("cuda"))
  diarization = pipeline(vocals_filepath, num_speakers=number_of_speakers)
  timestamps = [
      {"start": segment.start, "end": segment.end}
      for segment, _, _ in diarization.itertracks(yield_label=True)
  ]
  return timestamps


def cut_and_save_audio(
    *,
    input_data: Sequence[Mapping[str, float]],
    music_file_path: str,
    output_folder: str,
) -> Sequence[Mapping[str, float]]:
  """Cuts an audio file into chunks based on provided time ranges and saves each chunk to a file.

  Args:
      input_data: The list of dictionaries, each containing 'start' and 'end'
        times in seconds.
      music_file_path: The path to the audio file to be cut.
      output_folder: The path to the folder where the audio chunks will be
        saved.

  Returns:
      A list of dictionaries, each containing the path to the saved chunk, and
      the original start and end times.
  """

  audio = AudioSegment.from_file(music_file_path)
  chunk_results = []

  for item in input_data:
    start_time_ms = int(item["start"] * 1000)
    end_time_ms = int(item["end"] * 1000)
    chunk = audio[start_time_ms:end_time_ms]

    chunk_filename = f"chunk_{item['start']}_{item['end']}.mp3"
    chunk_path = f"{output_folder}/{chunk_filename}"

    chunk.export(chunk_path, format="mp3")
    chunk_results.append({
        "path": chunk_path,
        "start": item["start"],
        "end": item["end"],
    })

  return chunk_results

import os
import subprocess
from typing import Final
from moviepy.editor import VideoFileClip
import torch

_DEFAULT_FPS: Final[int] = 30


def split_audio_video(*, video_file: str, output_directory: str) -> None:
  """Splits an audio/video file into separate audio and video files.

  No audio file is written if the video doesn't have audio.

  Args:
      video_file: The full path to the input video file.
      output_directory: The full path to the output directory.
  """

  with VideoFileClip(video_file) as video_clip:
    if video_clip.audio:
      audio_clip = video_clip.audio
      audio_output_file = os.path.join(
          output_directory, os.path.splitext(video_file)[0] + "_audio.mp3"
      )
      audio_clip.write_audiofile(audio_output_file, verbose=False, logger=None)

    video_clip_without_audio = video_clip.set_audio(None)
    fps = video_clip.fps or _DEFAULT_FPS
    video_output_file = os.path.join(
        output_directory, os.path.splitext(video_file)[0] + "_video.mp4"
    )
    video_clip_without_audio.write_videofile(
        video_output_file, codec="libx264", fps=fps, verbose=False, logger=None
    )


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
    print(result.stdout)
  except subprocess.CalledProcessError as e:
    print(f"Error separating audio: {e}\n{e.stderr}")

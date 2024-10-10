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

"""An video processing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import os
from typing import Final
from absl import logging
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips
import tensorflow as tf

VIDEO_PROCESSING: Final[str] = "video_processing"
_OUTPUT: Final[str] = "output"
_DEFAULT_FPS: Final[int] = 30
_DEFAULT_DUBBED_VIDEO_FILE: Final[str] = "dubbed_video"
_DEFAULT_OUTPUT_FORMAT: Final[str] = ".mp4"


def split_audio_video(
    *, video_file: str, output_directory: str
) -> tuple[str, str]:
  """Splits an audio/video file into separate audio and video files.

  Args:
      video_file: The full path to the input video file.
      output_directory: The full path to the output directory.

  Returns:
    A tuple with a path to a video ad file with no audio and the second path to
    its audio file.
  """

  base_filename = os.path.basename(video_file)
  filename, _ = os.path.splitext(base_filename)
  video_output_file = os.path.join(
      output_directory, VIDEO_PROCESSING, filename + "_video.mp4"
  )
  audio_output_file = os.path.join(
      output_directory, VIDEO_PROCESSING, filename + "_audio.mp3"
  )
  if tf.io.gfile.exists(video_output_file) and tf.io.gfile.exists(
      audio_output_file
  ):
    logging.info(
        "The video / audio split will not be executed, because the expected"
        f" files {video_output_file} and {audio_output_file} already exist."
    )
    return video_output_file, audio_output_file
  with VideoFileClip(video_file) as video_clip:
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(audio_output_file, verbose=False, logger=None)
    video_clip_without_audio = video_clip.set_audio(None)
    fps = video_clip.fps or _DEFAULT_FPS
    video_clip_without_audio.write_videofile(
        video_output_file, codec="libx264", fps=fps, verbose=False, logger=None
    )
  return video_output_file, audio_output_file


def combine_audio_video(
    *,
    video_file: str,
    dubbed_audio_file: str,
    output_directory: str,
    target_language: str,
) -> str:
  """Combines an audio file with a video file, ensuring they have the same duration.

  Args:
    video_file: Path to the video file.
    dubbed_audio_file: Path to the audio file.
    output_directory: Path to save the combined video file.
    target_language: The language to dub the ad into. It must be ISO 3166-1
      alpha-2 country code.

  Returns:
    The path to the output video file with dubbed audio.
  """

  video = VideoFileClip(video_file)
  audio = AudioFileClip(dubbed_audio_file)
  duration_difference = video.duration - audio.duration
  if duration_difference > 0:
    silence = AudioFileClip(duration=duration_difference).set_duration(
        duration_difference
    )
    audio = concatenate_videoclips([audio, silence])
  elif duration_difference < 0:
    audio = audio.subclip(0, video.duration)
  final_clip = video.set_audio(audio)
  target_language_suffix = "_" + target_language.replace("-", "_").lower()
  dubbed_video_file = os.path.join(
      output_directory,
      _OUTPUT,
      _DEFAULT_DUBBED_VIDEO_FILE
      + target_language_suffix
      + _DEFAULT_OUTPUT_FORMAT,
  )
  final_clip.write_videofile(
      dubbed_video_file,
      codec="libx264",
      audio_codec="aac",
      temp_audiofile="temp-audio.m4a",
      remove_temp=True,
      verbose=False,
      logger=None,
  )
  return dubbed_video_file

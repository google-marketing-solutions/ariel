"""An audio processing module of Ariel package from the Google EMEA gTech Ads Data Science."""

import os
from typing import Final
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips

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


def combine_audio_video(
    *, video_path: str, audio_path: str, output_path: str
) -> None:
  """Combines an audio file with a video file, ensuring they have the same duration.

  Args:
    video_path: Path to the video file.
    audio_path: Path to the audio file.
    output_path: Path to save the combined video file.
  """

  video = VideoFileClip(video_path)
  audio = AudioFileClip(audio_path)
  duration_difference = video.duration - audio.duration
  if duration_difference > 0:
    silence = AudioFileClip(duration=duration_difference).set_duration(
        duration_difference
    )
    audio = concatenate_videoclips([audio, silence])
  elif duration_difference < 0:
    audio = audio.subclip(0, video.duration)
  final_clip = video.set_audio(audio)
  final_clip.write_videofile(
      output_path,
      codec="libx264",
      audio_codec="aac",
      temp_audiofile="temp-audio.m4a",
      remove_temp=True,
      verbose=False,
      logger=None,
  )

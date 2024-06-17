import os
from typing import Final
from moviepy.editor import VideoFileClip

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

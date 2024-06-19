import os
from typing import Final
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips

_DEFAULT_FPS: Final[int] = 30
_DEFAULT_DUBBED_VIDEO_FILE: Final[str] = "dubbed_video.mp4"


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

  with VideoFileClip(video_file) as video_clip:
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
  return video_output_file, audio_output_file


def combine_audio_video(
    *, video_file: str, dubbed_audio_file: str, output_directory: str
) -> str:
  """Combines an audio file with a video file, ensuring they have the same duration.

  Args:
    video_file: Path to the video file.
    dubbed_audio_file: Path to the audio file.
    output_directory: Path to save the combined video file.

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
  dubbed_video_file = os.path.join(output_directory, _DEFAULT_DUBBED_VIDEO_FILE)
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

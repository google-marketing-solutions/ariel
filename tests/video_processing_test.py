"""Tests for utility functions in video_processing.py."""

import os
import tempfile

from absl.testing import absltest
from ariel import video_processing
from moviepy.audio.AudioClip import AudioArrayClip
from moviepy.editor import ColorClip
from moviepy.video.compositing.CompositeVideoClip import clips_array
import numpy as np


def _create_mock_video(directory: str, video_duration: int = 5) -> str:
  """Creates a video with red, green, and blue segments and mock audio, saves it to the directory.

  Args:
      directory: The directory to save the video.
      video_duration: The duration of the video in seconds. Defaults to 5.

  Returns:
      The full path to the saved video file.
  """
  filename = os.path.join(directory, "mock_video.mp4")
  red = ColorClip((256, 200), color=(255, 0, 0)).set_duration(video_duration)
  green = ColorClip((256, 200), color=(0, 255, 0)).set_duration(video_duration)
  blue = ColorClip((256, 200), color=(0, 0, 255)).set_duration(video_duration)
  combined_arrays = clips_array([[red, green, blue]])
  combined_arrays.fps = 30
  samples = int(44100 * video_duration)
  audio_data = np.zeros((samples, 2), dtype=np.int16)
  audio_clip = AudioArrayClip(audio_data, fps=44100)
  final_clip = combined_arrays.set_audio(audio_clip)
  final_clip.write_videofile(filename, logger=None)
  return filename


class TestSplitAudioVideo(absltest.TestCase):

  def test_split_audio_video_valid_duration(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      mock_video_file = _create_mock_video(temporary_directory, 5)
      video_processing.split_audio_video(
          video_file=mock_video_file, output_directory=temporary_directory
      )
      self.assertTrue(
          all([
              os.path.exists(
                  os.path.join(temporary_directory, "mock_video_audio.mp3")
              ),
              os.path.exists(
                  os.path.join(temporary_directory, "mock_video_video.mp4")
              ),
          ])
      )


class CombineAudioVideoTest(absltest.TestCase):

  def test_combine_audio_video(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      audio_path = f"{temporary_directory}/audio.mp3"
      audio_duration = 5
      audio = AudioArrayClip(
          np.zeros((int(44100 * audio_duration), 2), dtype=np.int16),
          fps=44100,
      )
      audio.write_audiofile(audio_path)
      video_duration = 5
      directory = temporary_directory
      video_path = os.path.join(directory, "video.mp4")
      red = ColorClip((256, 200), color=(255, 0, 0)).set_duration(
          video_duration
      )
      green = ColorClip((256, 200), color=(0, 255, 0)).set_duration(
          video_duration
      )
      blue = ColorClip((256, 200), color=(0, 0, 255)).set_duration(
          video_duration
      )
      combined_arrays = clips_array([[red, green, blue]])
      combined_arrays.fps = 30
      combined_arrays.write_videofile(video_path)
      output_path = video_processing.combine_audio_video(
          video_file=video_path,
          dubbed_audio_file=audio_path,
          output_directory=temporary_directory,
          target_language="en-US",
      )
      self.assertTrue(os.path.exists(output_path))


if __name__ == "__main__":
  absltest.main()

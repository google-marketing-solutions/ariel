import os
import tempfile
from absl.testing import absltest
from absl.testing import parameterized
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


class BuildDemucsCommandTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "basic",
          {},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems audio.mp3"
          ),
      ),
      (
          "flac",
          {"flac": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --flac"
              " audio.mp3"
          ),
      ),
      (
          "mp3",
          {"mp3": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --mp3"
              " --mp3-bitrate 320 --mp3-preset 2 audio.mp3"
          ),
      ),
      (
          "int24",
          {"int24": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --int24"
              " audio.mp3"
          ),
      ),
      (
          "float32",
          {"float32": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --float32"
              " audio.mp3"
          ),
      ),
      (
          "segment",
          {"segment": 60},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --segment"
              " 60 audio.mp3"
          ),
      ),
      (
          "no_split",
          {"split": False},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --no-split"
              " audio.mp3"
          ),
      ),
  )
  def test_build_demucs_command(self, kwargs, expected_command):
    self.assertEqual(
        video_processing.build_demucs_command(
            audio_file="audio.mp3",
            output_directory="test",
            device="cpu",
            **kwargs,
        ),
        expected_command,
    )

  def test_raise_error_int24_float32(self):
    with self.assertRaisesRegex(
        ValueError, "Cannot set both int24 and float32 to True."
    ):
      video_processing.build_demucs_command(
          audio_file="audio.mp3",
          output_directory="test",
          device="cpu",
          int24=True,
          float32=True,
      )


if __name__ == "__main__":
  absltest.main()

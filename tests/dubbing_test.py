"""Tests for utility functions in dubbing.py."""

from absl.testing import parameterized
from ariel import dubbing


class TestIsVideo(parameterized.TestCase):

  @parameterized.named_parameters(
      ("valid_mp4", "my_video.mp4", True),
      ("wav_audio", "my_song.wav", False),
      ("mp3_audio", "another_song.mp3", False),
      ("flac_audio", "high_quality.flac", False),
      ("case_insensitive_mp4", "my_video.MP4", True),
  )
  def test_is_video(self, input_file, expected_result):
    self.assertEqual(dubbing.is_video(input_file=input_file), expected_result)

  @parameterized.named_parameters(
      ("unsupported_format_txt", "document.txt"),
      ("unsupported_format_jpg", "image.jpg"),
      ("unsupported_format_empty", ""),
  )
  def test_unsupported_format_raises_value_error(self, input_file):
    with self.assertRaisesRegex(ValueError, "Unsupported file format"):
      dubbing.is_video(input_file=input_file)

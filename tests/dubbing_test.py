"""Tests for utility functions in dubbing.py."""

import tempfile
from absl.testing import absltest
from absl.testing import parameterized
from ariel import dubbing
import tensorflow as tf


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


class TestReadSystemSettings(absltest.TestCase):

  def test_txt_file_success(self):
    """Test reading a .txt file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as temp_file:
      temp_file.write("This is a test file.")
      temp_file.flush()

      result = dubbing.read_system_settings(temp_file.name)
      self.assertEqual(result, "This is a test file.")

  def test_string_input(self):
    """Test returning a plain string."""
    result = dubbing.read_system_settings("Hello, world!")
    self.assertEqual(result, "Hello, world!")

  def test_unsupported_extension(self):
    """Test raising ValueError for unsupported extensions."""
    with self.assertRaisesRegex(ValueError, "Unsupported file type"):
      dubbing.read_system_settings("invalid.docx")

  def test_nonexistent_file(self):
    """Test raising FileNotFoundError for missing files."""
    with self.assertRaisesRegex(ValueError, "The file doesn't exist"):
      dubbing.read_system_settings("nonexistent.txt")


if __name__ == "__main__":
  absltest.main()

"""Tests for utility functions in dubbing.py."""

import os
import tempfile
from absl.testing import absltest
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


class TestSaveUtteranceMetadata(absltest.TestCase):

  def test_successful_save(self):
    metadata = {
        "start": 0.0,
        "end": 5.2,
        "chunk_path": "chunk_1.wav",
        "translated_text": "Hello, how are you?",
        "speaker_id": 1,
        "ssml_gender": "male",
        "dubbed_path": "dubbed_1.wav",
    }

    with tempfile.TemporaryDirectory() as temp_output_dir:
      dubbing.save_utterance_metadata([metadata], temp_output_dir)
      expected_file_path = os.path.join(
          temp_output_dir, dubbing._UTTERNACE_METADATA_FILE_NAME
      )
      self.assertTrue(os.path.exists(expected_file_path))


class TestCleanDirectory(absltest.TestCase):

  def test_clean_directory(self):
    with tempfile.TemporaryDirectory() as tempdir:
      os.makedirs(os.path.join(tempdir, "subdir"))
      with open(os.path.join(tempdir, "file1.txt"), "w") as f:
        f.write("Test file 1")
      with open(os.path.join(tempdir, "file2.txt"), "w") as f:
        f.write("Test file 2")
      with open(os.path.join(tempdir, "subdir", "file3.txt"), "w") as f:
        f.write("Test file 3")
      keep_files = ["file1.txt", "subdir"]
      dubbing.clean_directory(tempdir, keep_files)
      actual_output = [
          os.path.exists(os.path.join(tempdir, "file1.txt")),
          os.path.exists(os.path.join(tempdir, "subdir")),
          os.path.exists(os.path.join(tempdir, "file2.txt")),
          os.path.exists(os.path.join(tempdir, "subdir", "file3.txt")),
      ]
      expected_outputs = [True, True, False, True]
      self.assertEqual(actual_output, expected_outputs)

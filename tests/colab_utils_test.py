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

"""Tests for utility functions in colab_utils.py."""

import os
import tempfile
from unittest.mock import MagicMock, patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import colab_utils
import pandas as pd
import tensorflow as tf


class ExtractFileIdTest(parameterized.TestCase):

  @parameterized.named_parameters([
      (
          "with_id",
          "https://drive.google.com/file/d/1LstfvlSGXLR6TT6MFEAfpP5AbqHesXnv/view?usp=sharing&id=1234567890",
          "1234567890",
      ),
      (
          "with_d",
          "https://drive.google.com/file/d/1LstfvlSGXLR6TT6MFEAfpP5AbqHesXnv/view?usp=sharing",
          "1LstfvlSGXLR6TT6MFEAfpP5AbqHesXnv",
      ),
      (
          "with_file_d",
          "https://drive.google.com/file/d/1LstfvlSGXLR6TT6MFEAfpP5AbqHesXnv/view",
          "1LstfvlSGXLR6TT6MFEAfpP5AbqHesXnv",
      ),
      ("invalid_link", "https://www.google.com", None),
  ])
  def test_extract_file_id(self, sharable_link, expected_id):
    result = colab_utils.extract_file_id(sharable_link)
    self.assertEqual(result, expected_id)


class GetParentPathTest(absltest.TestCase):

  def test_get_parent_path_no_parent(self):
    service_mock = MagicMock()
    service_mock.files.return_value.get.return_value.execute.return_value = {
        "name": "MyFile.txt",
    }
    result = colab_utils.get_parent_path(service_mock, "12345")
    self.assertEqual(result, "/MyFile.txt")

  def test_get_parent_path_with_parents(self):
    service_mock = MagicMock()
    service_mock.files.return_value.get.return_value.execute.side_effect = [
        {
            "name": "MyFile.txt",
            "parents": ["67890"],
        },
        {
            "name": "Folder1",
            "parents": ["abcde"],
        },
        {
            "name": "Folder2",
        },
    ]
    result = colab_utils.get_parent_path(service_mock, "12345")
    self.assertEqual(result, "/Folder2/Folder1/MyFile.txt")


class GetFilePathFromSharableLinkTest(absltest.TestCase):

  @patch("ariel.colab_utils.build")
  @patch("ariel.colab_utils.default")
  @patch("ariel.colab_utils.extract_file_id")
  def test_get_file_path_from_sharable_link_no_parents(
      self, extract_file_id_mock, default_mock, build_mock
  ):
    extract_file_id_mock.return_value = "12345"
    creds_mock = MagicMock()
    default_mock.return_value = (creds_mock, None)
    service_mock = MagicMock()
    build_mock.return_value = service_mock
    service_mock.files.return_value.get.return_value.execute.return_value = {
        "name": "MyFile.txt",
    }
    expected_path = f"{colab_utils._BASE_DIRECTORY_DRIVE}/MyFile.txt"
    result = colab_utils.get_file_path_from_sharable_link(
        "https://drive.google.com/file/d/12345/view?usp=sharing"
    )
    self.assertEqual(result, expected_path)

  @patch("ariel.colab_utils.build")
  @patch("ariel.colab_utils.default")
  @patch("ariel.colab_utils.extract_file_id")
  @patch("ariel.colab_utils.get_parent_path")
  def test_get_file_path_from_sharable_link_with_parents(
      self, get_parent_path_mock, extract_file_id_mock, default_mock, build_mock
  ):
    extract_file_id_mock.return_value = "12345"
    creds_mock = MagicMock()
    default_mock.return_value = (creds_mock, None)
    service_mock = MagicMock()
    build_mock.return_value = service_mock
    service_mock.files.return_value.get.return_value.execute.return_value = {
        "name": "MyFile.txt",
        "parents": ["67890"],
    }

    get_parent_path_mock.return_value = "/Folder1/Folder2"
    expected_path = (
        f"{colab_utils._BASE_DIRECTORY_DRIVE}/Folder1/Folder2/MyFile.txt"
    )
    result = colab_utils.get_file_path_from_sharable_link(
        "https://drive.google.com/file/d/12345/view?usp=sharing"
    )
    self.assertEqual(result, expected_path)

  @patch("ariel.colab_utils.extract_file_id")
  def test_get_file_path_from_sharable_link_invalid_link(
      self, extract_file_id_mock
  ):
    extract_file_id_mock.return_value = None
    result = colab_utils.get_file_path_from_sharable_link(
        "https://www.google.com"
    )
    self.assertIsNone(result)


class CopyFileToColabBaseDirectoryTest(absltest.TestCase):

  def test_copy_file_to_colab_base_directory(self):
    """Tests the copy_file_to_colab_base_directory function."""
    with tempfile.TemporaryDirectory() as tmpdirname:
      temp_file_path = os.path.join(tmpdirname, "test_file.txt")
      with open(temp_file_path, "w") as f:
        f.write("This is a test file.")
      colab_directory = os.path.join(tmpdirname, "content")
      os.makedirs(colab_directory)
      colab_utils.copy_file_to_colab(
          source_file_path=temp_file_path, destination_folder=colab_directory
      )
      self.assertTrue(
          tf.io.gfile.exists(
              os.path.join(colab_directory, os.path.basename(temp_file_path))
          )
      )


class TestScriptMetadata(absltest.TestCase):

  def test_script_metadata_creation(self):
    metadata = colab_utils.ScriptMetadata(
        script_with_timestamps=[
            {"start": 0.0, "end": 1.5, "text": "Hello"},
            {"start": 1.5, "end": 3.0, "text": "world"},
        ],
        assigned_voice=["Alice", "Bob"],
        google_text_to_speech_parameters=[
            {"pitch": 0.1, "speed": 1.0, "volume_gain_db": 10}
        ],
        elevenlabs_text_to_speech_parameters=[{
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0,
            "use_speaker_boost": True,
        }],
    )
    self.assertEqual(
        metadata.script_with_timestamps,
        [
            {"start": 0.0, "end": 1.5, "text": "Hello"},
            {"start": 1.5, "end": 3.0, "text": "world"},
        ],
    )
    self.assertEqual(metadata.assigned_voice, ["Alice", "Bob"])
    self.assertEqual(
        metadata.google_text_to_speech_parameters,
        [{"pitch": 0.1, "speed": 1.0, "volume_gain_db": 10}],
    )
    self.assertEqual(
        metadata.elevenlabs_text_to_speech_parameters,
        [{
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0,
            "use_speaker_boost": True,
        }],
    )

  def test_script_metadata_optional_attributes(self):
    metadata = colab_utils.ScriptMetadata(
        script_with_timestamps=[{"start": 0.0, "end": 1.5, "text": "Hello"}],
        assigned_voice=["Alice"],
    )
    self.assertEqual(
        metadata.script_with_timestamps,
        [{"start": 0.0, "end": 1.5, "text": "Hello"}],
    )
    self.assertEqual(metadata.assigned_voice, ["Alice"])
    self.assertIsNone(metadata.google_text_to_speech_parameters)
    self.assertIsNone(metadata.elevenlabs_text_to_speech_parameters)


class TestCreateScriptMetadataFromDataFrame(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "elevenlabs_params",
          pd.DataFrame({
              "start": [0, 12.98],
              "end": [1.5, 13.9],
              "text": ["Test1", "Test2"],
              "assigned_voice": ["Ben", "Ben"],
              "stability": [0.5, 0.5],
              "similarity_boost": [0.75, 0.75],
              "style": [0, 0],
              "use_speaker_boost": [True, False],
              "speaker_id": ["speaker_01", "speaker_01"],
              "ssml_gender": ["Female", "Female"],
          }),
          colab_utils.ScriptMetadata(
              script_with_timestamps=[
                  {
                      "start": 0,
                      "end": 1.5,
                      "text": "Test1",
                      "speaker_id": "speaker_01",
                      "ssml_gender": "Female",
                  },
                  {
                      "start": 12.98,
                      "end": 13.9,
                      "text": "Test2",
                      "speaker_id": "speaker_01",
                      "ssml_gender": "Female",
                  },
              ],
              assigned_voice=["Ben", "Ben"],
              elevenlabs_text_to_speech_parameters=[
                  {
                      "stability": 0.5,
                      "similarity_boost": 0.75,
                      "style": 0,
                      "use_speaker_boost": True,
                  },
                  {
                      "stability": 0.5,
                      "similarity_boost": 0.75,
                      "style": 0,
                      "use_speaker_boost": False,
                  },
              ],
          ),
      ),
      (
          "google_params",
          pd.DataFrame({
              "start": [0, 12.98],
              "end": [1.5, 13.9],
              "text": ["Test1", "Test2"],
              "assigned_voice": ["Ben", "Ben"],
              "pitch": [0.1, 0.2],
              "speed": [1, 2],
              "volume_gain_db": [10, 20],
              "speaker_id": ["speaker_01", "speaker_01"],
              "ssml_gender": ["Female", "Female"],
          }),
          colab_utils.ScriptMetadata(
              script_with_timestamps=[
                  {
                      "start": 0,
                      "end": 1.5,
                      "text": "Test1",
                      "speaker_id": "speaker_01",
                      "ssml_gender": "Female",
                  },
                  {
                      "start": 12.98,
                      "end": 13.9,
                      "text": "Test2",
                      "speaker_id": "speaker_01",
                      "ssml_gender": "Female",
                  },
              ],
              assigned_voice=["Ben", "Ben"],
              google_text_to_speech_parameters=[
                  {"pitch": 0.1, "speed": 1, "volume_gain_db": 10},
                  {"pitch": 0.2, "speed": 2, "volume_gain_db": 20},
              ],
          ),
      ),
  )
  def test_create_script_metadata_from_dataframe(
      self, input_df, expected_metadata
  ):
    result_metadata = colab_utils.create_script_metadata_from_dataframe(
        input_df
    )
    self.assertEqual(result_metadata, expected_metadata)


if __name__ == "__main__":
  absltest.main()

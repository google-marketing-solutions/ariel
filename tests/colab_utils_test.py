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
    expected_path = f"{colab_utils._BASE_DIRECTORY_COLAB}/MyFile.txt"
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
        f"{colab_utils._BASE_DIRECTORY_COLAB}/Folder1/Folder2/MyFile.txt"
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


if __name__ == "__main__":
  absltest.main()

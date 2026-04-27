"""Tests Ariel's app endpoints in a Cloud Run environment."""

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import importlib
import os
from typing import override
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from google.cloud.exceptions import GoogleCloudError
import main
from models import VideoMetadata


@patch.dict(os.environ, {"K_SERVICE": "true"}, clear=True)
class MainTestCloudRun(unittest.TestCase):
  """Test cases for the main application in a Cloud Run environment."""

  @override
  def setUp(self):
    """Creates the FastAPI TestClient to mock the server."""
    super().setUp()
    # Reload main to apply the environment variable
    importlib.reload(main)
    self.client = TestClient(main.app)

  @patch("main.list_all_videos")
  def test_get_videos_endpoint_cloud_run(self, mock_list_all_videos):
    """Tests the /api/videos endpoint in a Cloud Run environment."""
    mock_video_metadata = {
        "videos": [
            VideoMetadata(
                video_id="test_video_id",
                name="test_video.mp4",
                url="https://example.com/video.mp4",
                download_url="https://example.com/download",
                original_video_url="https://example.com/original.mp4",
                created_at="2023-01-01T00:00:00",
                original_language="en",
                translate_language="es",
                duration=10.0,
                speakers=[],
                has_metadata=True,
            ).model_dump()
        ],
        "next_page_token": "",
    }
    mock_list_all_videos.return_value = mock_video_metadata

    response = self.client.get("/api/videos?max_results=5")
    self.assertEqual(response.status_code, 200)

    data = response.json()
    self.assertIn("videos", data)
    self.assertEqual(len(data["videos"]), 1)
    self.assertEqual(data["videos"][0]["name"], "test_video.mp4")
    mock_list_all_videos.assert_called_once()

  @patch("main.delete_video_from_gcs")
  def test_delete_video_cloud_run_success(self, mock_delete_video):
    """Tests successful deletion of a video project in Cloud Run."""
    response = self.client.delete("/api/videos/test_video_id")
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json()["message"], "Video deleted successfully")
    mock_delete_video.assert_called_once()

  @patch("main.delete_video_from_gcs")
  def test_delete_video_cloud_run_error(self, mock_delete_video):
    """Tests deletion error (GCS failure) in Cloud Run."""
    mock_delete_video.side_effect = GoogleCloudError("GCS failure")

    response = self.client.delete("/api/videos/test_video_id")
    self.assertEqual(response.status_code, 500)
    self.assertIn("Error deleting video", response.json()["error"])
    mock_delete_video.assert_called_once()


if __name__ == "__main__":
  unittest.main()

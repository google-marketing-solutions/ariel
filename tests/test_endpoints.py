"""Tests Ariel's app endpoints."""

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

import json
import os
import tempfile
from typing import override
import unittest
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

from fastapi.testclient import TestClient
import main
from models import GenderEnum
from models import Speaker
from models import Utterance

# Mock configuration before importing main
with patch("configuration.get_config") as mock_get_config:
  mock_config = MagicMock()
  mock_config.gcp_project_id = "test-project"
  mock_config.gcs_bucket_name = "test-bucket"
  mock_config.gemini_flash_model = "flash-model"
  mock_config.gemini_pro_model = "pro-model"
  mock_config.gemini_flash_tts_model = "flash-tts"
  mock_config.gemini_pro_tts_model = "pro-tts"
  mock_get_config.return_value = mock_config


class MainTest(unittest.TestCase):
  """Test cases for the main application (Integration/API)."""

  @override
  def setUp(self):
    """Creates the FastAPI TestClient to mock the server."""
    super().setUp()
    self.client = TestClient(main.app)

  def test_read_root(self):
    """Tests the catchall endpoint returns 200 for the frontend."""
    # The frontend/dist directory exists, so the catchall should return 200.
    response = self.client.get("/")
    self.assertEqual(response.status_code, 200)

  def test_get_videos_endpoint(self):
    """Tests the /api/videos endpoint returns 200."""
    with tempfile.TemporaryDirectory() as tmpdir:
      # Create a dummy video and metadata
      video_id = "test_video_id"
      video_dir = os.path.join(tmpdir, video_id)
      os.makedirs(video_dir)
      video_path = os.path.join(video_dir, f"{video_id}.mp4")
      with open(video_path, "w") as f:
        f.write("dummy video")

      metadata_path = os.path.join(video_dir, "metadata.json")
      with open(metadata_path, "w") as f:
        json.dump(
            {
                "video_id": video_id,
                "name": "test_video.mp4",
                "url": f"/temp/{video_id}/{video_id}.mp4",
                "download_url": f"/temp/{video_id}/{video_id}.mp4",
                "original_video_url": f"/temp/{video_id}/{video_id}",
                "created_at": "2023-01-01T00:00:00",
                "original_language": "en",
                "translate_language": "es",
                "duration": 10.0,
                "speakers": [],
                "has_metadata": True,
            },
            f,
        )

      # Temporarily replace the mount_point in main
      with patch("main.mount_point", tmpdir):
        response = self.client.get("/api/videos?max_results=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("videos", data)
        self.assertGreater(len(data["videos"]), 0)
        first_video = data["videos"][0]
        self.assertIn("original_video_url", first_video)
        self.assertEqual(
            first_video["original_video_url"], f"/temp/{video_id}/{video_id}"
        )

  @patch("main.upload_file_to_gcs")
  @patch("main.save_video")
  @patch("main.separate_audio_from_video")
  @patch("main.genai.Client")
  @patch("main.transcribe_video")
  @patch("main.moviepy.VideoFileClip")
  @patch("main.generate_audio")
  @patch("builtins.open", new_callable=mock_open)
  def test_process_video_endpoint(
      self,
      mock_file_open,
      mock_gen_audio,
      mock_video_clip,
      mock_transcribe,
      mock_genai_client,
      mock_separate,
      mock_save_video,
      mock_upload_file,
  ):
    """Tests /process endpoint flow."""
    # Setup mocks
    mock_save_video.return_value = (
        "temp/vid/video.mp4",
        "gs://bucket/vid/video.mp4",
    )
    mock_separate.return_value = (
        "temp/vid/audio.wav",
        "temp/vid/vocals.wav",
        "temp/vid/bg.wav",
    )

    speaker = Speaker(
        speaker_id="spk1",
        voice="voice1",
        speaker_name="Speaker 1",
        gender=GenderEnum.NEUTRAL,
    )

    utterance = Utterance(
        id="1",
        original_text="original",
        translated_text="translated",
        speaker=speaker,
        original_start_time=0.0,
        original_end_time=1.0,
        translated_start_time=0.0,
        translated_end_time=1.0,
        audio_url="temp/vid/audio_0.wav",
    )

    mock_transcribe.return_value = ("en", [speaker], [utterance])
    mock_gen_audio.return_value = 1.0

    mock_clip_instance = MagicMock()
    mock_clip_instance.duration = 10.0
    mock_video_clip.return_value = mock_clip_instance

    response = self.client.post(
        "/process",
        data={
            "translate_language": "es",
            "use_pro_model": "false",
            "source_video_id": "",
            "update_existing": "false",
        },
        files={"video": ("video.mp4", b"video content", "video/mp4")},
    )

    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertEqual(data["original_language"], "en")
    self.assertEqual(data["translate_language"], "es")

    mock_save_video.assert_called_once()
    mock_separate.assert_called_once()
    mock_transcribe.assert_called_once()

  @patch("main.merge_vocals")
  def test_generate_audio_endpoint(self, mock_merge_vocals):
    """Tests /generate_audio endpoint."""
    mock_merge_vocals.return_value = "temp/vid1/vocals.wav"

    video_payload = {
        "video_id": "vid1",
        "original_language": "en",
        "translate_language": "es",
        "speakers": [],
        "utterances": [],
        "model_name": "flash",
        "tts_model_name": "flash-tts",
    }

    response = self.client.post("/generate_audio", json=video_payload)

    self.assertEqual(response.status_code, 200)
    self.assertIn("audio_url", response.json())
    mock_merge_vocals.assert_called_once()

  @patch("main.merge_vocals")
  @patch("main.merge_background_and_vocals")
  @patch("main.combine_video_and_audio")
  @patch("main.os.listdir")
  @patch("main.os.path.exists")
  @patch("main.moviepy.VideoFileClip")
  @patch("builtins.open", new_callable=mock_open)
  @patch("main.upload_file_to_gcs")
  def test_generate_video_endpoint(
      self,
      mock_upload,
      mock_open_file,
      mock_video_clip,
      mock_exists,
      mock_listdir,
      mock_combine,
      mock_merge_bg,
      mock_merge_vocals,
  ):
    """Tests /generate_video endpoint."""
    mock_merge_vocals.return_value = "temp/vid1/vocals.wav"
    mock_merge_bg.return_value = "temp/vid1/merged.wav"
    mock_listdir.return_value = ["vid1"]
    mock_exists.return_value = True

    mock_clip_instance = MagicMock()
    mock_clip_instance.duration = 10.0
    mock_video_clip.return_value = mock_clip_instance

    video_payload = {
        "video_id": "vid1",
        "original_language": "en",
        "translate_language": "es",
        "speakers": [],
        "utterances": [],
        "model_name": "flash",
        "tts_model_name": "flash-tts",
    }

    response = self.client.post(
        "/generate_video", json={"video": video_payload}
    )

    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertIn("video_url", data)
    self.assertIn("vocals_url", data)
    self.assertIn("merged_audio_url", data)

    mock_merge_vocals.assert_called_once()
    mock_merge_bg.assert_called_once()
    mock_combine.assert_called_once()

  def test_process_video_missing_args(self):
    """Tests /process endpoint with missing video and source_video_id."""
    response = self.client.post(
        "/process",
        data={
            "translate_language": "es",
        },
    )
    self.assertEqual(response.status_code, 400)
    self.assertIn(
        "Either video file or source_video_id must be provided",
        response.json()["detail"],
    )

  def test_process_video_source_not_found(self):
    """Tests /process endpoint with a non-existent source_video_id."""
    response = self.client.post(
        "/process",
        data={
            "translate_language": "es",
            "source_video_id": "non_existent_id",
        },
    )
    self.assertEqual(response.status_code, 500)
    self.assertIn(
        "Source video non_existent_id not found.", response.json()["error"]
    )

  def test_load_project_not_found(self):
    """Tests /api/projects/{video_id} with a non-existent video_id."""
    response = self.client.get("/api/projects/non_existent_id")
    self.assertEqual(response.status_code, 404)
    self.assertEqual(response.json()["error"], "The file doesn't exist")

  def test_delete_video_not_found(self):
    """Tests DELETE /api/videos/{video_id} with a non-existent video_id."""
    response = self.client.delete("/api/videos/non_existent_id")
    self.assertEqual(response.status_code, 404)
    self.assertEqual(response.json()["error"], "Video not found")


if __name__ == "__main__":
  unittest.main()

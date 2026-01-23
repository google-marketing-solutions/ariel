"""Tests for the main application."""

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
from typing import override
import unittest
import unittest.mock
from io import BytesIO

from fastapi.testclient import TestClient

# We need to mock configuration modules before importing main
# because main imports get_config() at module level
with unittest.mock.patch("configuration.get_config") as mock_get_config:
    mock_config = unittest.mock.MagicMock()
    mock_config.gcp_project_id = "test-project"
    mock_config.gcs_bucket_name = "test-bucket"
    mock_config.gemini_flash_model = "flash-model"
    mock_config.gemini_pro_model = "pro-model"
    mock_config.gemini_flash_tts_model = "flash-tts"
    mock_config.gemini_pro_tts_model = "pro-tts"
    mock_get_config.return_value = mock_config
    import main
    from main import sanitize_filename

class MainTest(unittest.TestCase):
  """Test cases for the main application."""

  @override
  def setUp(self):
    self.client = TestClient(main.app)

  def test_read_root(self):
    """Tests the root endpoint."""
    response = self.client.get("/")
    self.assertEqual(response.status_code, 200)
    self.assertIn("Ariel", response.text)

  def test_sanitize_filename(self):
    """Tests filename sanitization."""
    self.assertEqual(sanitize_filename("valid_name.mp4"), "valid_name.mp4")
    self.assertEqual(sanitize_filename("start name.mp4"), "startname.mp4")
    self.assertEqual(sanitize_filename("bad$name!.mp4"), "badname!.mp4")
    self.assertEqual(sanitize_filename(""), "video.mp4")
    self.assertEqual(sanitize_filename("$%^"), "%^")

  @unittest.mock.patch("main.upload_video_to_gcs")
  @unittest.mock.patch("builtins.open")
  @unittest.mock.patch("shutil.copyfileobj")
  @unittest.mock.patch("os.makedirs")
  @unittest.mock.patch("main.config")
  def test_save_video(self, mock_config, mock_makedirs, mock_copyfileobj, mock_open, mock_upload):
    """Tests save_video function."""
    mock_config.gcs_bucket_name = "test-bucket"
    mock_upload.return_value = "video_path/video.mp4"

    mock_file = unittest.mock.MagicMock()
    upload_file = unittest.mock.MagicMock()
    upload_file.filename = "test video.mp4"
    upload_file.file = mock_file

    local_path, gcs_uri = main.save_video(upload_file)

    self.assertIn("video_path/video.mp4", local_path)
    self.assertEqual(gcs_uri, "gs://test-bucket/video_path/video.mp4")

    # Verify GCS upload
    mock_upload.assert_called_once()

    # Verify local save
    mock_makedirs.assert_called_once()
    mock_copyfileobj.assert_called_once()

  @unittest.mock.patch("main.upload_file_to_gcs")
  @unittest.mock.patch("main.save_video")
  @unittest.mock.patch("main.separate_audio_from_video")
  @unittest.mock.patch("main.genai.Client")
  @unittest.mock.patch("main.transcribe_media")
  @unittest.mock.patch("main.annotate_transcript")
  # We might need to mock ThreadPoolExecutor to run synchronously or mock map
  def test_process_video_endpoint(
      self,
      mock_annotate,
      mock_transcribe,
      mock_genai_client,
      mock_separate,
      mock_save_video,
      mock_upload_file
  ):
    """Tests /process endpoint flow."""
    # Setup mocks
    mock_save_video.return_value = ("temp/vid/video.mp4", "gs://bucket/vid/video.mp4")
    mock_separate.return_value = ("temp/vid/audio.wav", "temp/vid/vocals.wav", "temp/vid/bg.wav")

    # Mock file open for uploads
    with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data=b"data")):
        response = self.client.post(
            "/process",
            files={"video": ("video.mp4", b"video content", "video/mp4")},
            data={
                "original_language": "en",
                "translate_language": "es",
                "adjust_speed": "false",
                "speakers": '[{"id": "spk1", "voice": "voice1"}]',
                "prompt_enhancements": "",
                "use_pro_model": "false"
            }
        )

    # We might expect 200 and JSON with Utterances, but typically we return a Video object
    # which FastAPI converts to JSON.
    # Since we mocked almost everything, we just check if it ran through.
    # Note: annotate_transcript returning empty list means no utterances => empty list
    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertEqual(data["original_language"], "en")
    self.assertEqual(data["translate_language"], "es")

    mock_save_video.assert_called_once()
    mock_separate.assert_called_once()
    mock_transcribe.assert_called_once()
    mock_annotate.assert_called_once()

  @unittest.mock.patch("main.merge_vocals")
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
        "tts_model_name": "flash-tts"
    }

    response = self.client.post("/generate_audio", json=video_payload)

    self.assertEqual(response.status_code, 200)
    self.assertIn("audio_url", response.json())
    mock_merge_vocals.assert_called_once()

  @unittest.mock.patch("main.merge_vocals")
  @unittest.mock.patch("main.merge_background_and_vocals")
  @unittest.mock.patch("main.combine_video_and_audio")
  def test_generate_video_endpoint(self, mock_combine, mock_merge_bg, mock_merge_vocals):
    """Tests /generate_video endpoint."""
    mock_merge_vocals.return_value = "temp/vid1/vocals.wav"
    mock_merge_bg.return_value = "temp/vid1/merged.wav"

    video_payload = {
        "video_id": "vid1",
        "original_language": "en",
        "translate_language": "es",
        "speakers": [],
        "utterances": [],
        "model_name": "flash",
        "tts_model_name": "flash-tts"
    }

    response = self.client.post("/generate_video", json=video_payload)

    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertIn("video_url", data)
    self.assertIn("vocals_url", data)
    self.assertIn("merged_audio_url", data)

    mock_merge_vocals.assert_called_once()
    mock_merge_bg.assert_called_once()
    mock_combine.assert_called_once()


if __name__ == "__main__":
  unittest.main()

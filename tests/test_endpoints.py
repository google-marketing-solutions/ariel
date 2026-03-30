"""Tests Ariel's app endpoints."""

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

  def setUp(self):
    """Creates the FastAPI TestClient to mock the server."""
    super().setUp()
    self.client = TestClient(main.app)

  def test_read_root(self):
    """Tests the catchall endpoint returns 200 for the frontend."""
    # The frontend/dist directory exists, so the catchall should return 200.
    response = self.client.get("/")
    self.assertEqual(response.status_code, 200)

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

    # Use real Pydantic models to avoid validation errors
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


if __name__ == "__main__":
  unittest.main()

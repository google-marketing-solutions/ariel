"""Tests internal logic for dealing with video files and projects."""

import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

from main import clean_video_name
from main import get_videos
from main import sanitize_filename
from main import save_video

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestVideoLogic(unittest.TestCase):
  """Tests for internal logic when dealing with video files and projects."""

  def setUp(self):
    """Define reusable fake file system data."""
    super().setUp()
    self.local_root = "static/temp"
    self.folder_name = "2026-01-21T09_56_05.967648-14c53e20-b364-46b0-ae40-9fb486f47a11-video.mp4"
    self.original_video = self.folder_name
    self.translated_video = f"{self.folder_name}.en-GB.mp4"

    self.files_list = [
        self.original_video,
        self.translated_video,
        "metadata.json",
        "audio_0.wav",
    ]

    self.fake_meta = json.dumps({
        "name": "video.mp4",
        "url": f"/temp/{self.folder_name}/{self.translated_video}",
        "download_url": f"/temp/{self.folder_name}/{self.translated_video}",
        "created_at": "2026-01-21T09:56:05.967648",
        "original_language": "en-GB",
        "translate_language": "it-IT",
        "duration": 10.5,
        "speakers": [
            {
                "speaker_id": "speaker_1",
                "voice": "voice_1",
                "speaker_name": "Speaker 1",
                "gender": "neutral",
            },
        ],
        "video_id": self.folder_name,
        "has_metadata": True,
    })

  @patch("main.os.walk")
  @patch("main.os.path.exists")
  @patch("main.os.path.getmtime")
  @patch("main.open", new_callable=mock_open)
  @patch("main.mount_point", "static/temp")
  def test_get_videos_local_mode(
      self, mock_file, mock_getmtime, mock_exists, mock_walk
  ):
    """Tests finding and returning the project list when running locally."""
    full_path = f"{self.local_root}/{self.folder_name}"
    # In main.py, os.walk is called on mount_point
    mock_walk.return_value = [
        (self.local_root, [self.folder_name], []),
        (full_path, [], self.files_list),
    ]

    # We need to be careful with mock_exists as it's called multiple times
    def exists_side_effect(path):
      if path.endswith("metadata.json"):
        return True
      return True

    mock_exists.side_effect = exists_side_effect

    mock_getmtime.return_value = 1700000000.0
    mock_file.return_value.read.return_value = self.fake_meta

    results = get_videos()

    # Verify return type and content
    self.assertIn("videos", results)
    videos = results["videos"]

    self.assertEqual(len(videos), 1)
    video = videos[0]

    # Video is a VideoMetadata object (Pydantic)
    expected_url = f"/temp/{self.folder_name}/{self.translated_video}"
    self.assertEqual(video.url, expected_url)

    # Verify metadata extraction
    self.assertEqual(video.original_language, "en-GB")
    self.assertEqual(len(video.speakers), 1)
    self.assertEqual(video.speakers[0].voice, "voice_1")

  def test_clean_video_name(self):
    """Test the clean_video_name function."""
    raw_name = "2026-01-16T13_31_34.830635-ed69b287-ac8d-4876-a8c3-481208407350-video.mp4"
    self.assertEqual(clean_video_name(raw_name), "video.mp4")

    raw_name = "2026-01-16T13_31_34.830635-ed69b287-ac8d-4876-a8c3-481208407350-video.mp4.en-GB.mp4"
    self.assertEqual(clean_video_name(raw_name), "video.mp4.en-GB.mp4")

  def test_sanitize_filename(self):
    """Tests filename sanitization."""
    self.assertEqual(sanitize_filename("valid_name.mp4"), "valid_name.mp4")
    self.assertEqual(sanitize_filename("start name.mp4"), "startname.mp4")
    self.assertEqual(sanitize_filename("bad$name!.mp4"), "badname!.mp4")
    self.assertEqual(sanitize_filename(""), "video.mp4")
    self.assertEqual(sanitize_filename("$%^"), "%^")

  @patch("main.upload_video_to_gcs")
  @patch("builtins.open", new_callable=mock_open)
  @patch("shutil.copyfileobj")
  @patch("os.makedirs")
  @patch("main.config")
  def test_save_video(
      self,
      mock_config,
      mock_makedirs,
      mock_copyfileobj,
      mock_open_file,
      mock_upload,
  ):
    """Tests save_video function."""
    mock_config.gcs_bucket_name = "test-bucket"
    mock_upload.return_value = "video_path/video.mp4"

    upload_file = MagicMock()
    upload_file.filename = "test video.mp4"
    upload_file.file = io.BytesIO(b"test content")

    local_path, gcs_uri = save_video(upload_file)

    self.assertIn("video_path/video.mp4", local_path)
    self.assertEqual(gcs_uri, "gs://test-bucket/video_path/video.mp4")

    # Verify GCS upload
    mock_upload.assert_called_once()
    # Verify local save
    mock_makedirs.assert_called_once()
    mock_copyfileobj.assert_called_once()


if __name__ == "__main__":
  unittest.main()

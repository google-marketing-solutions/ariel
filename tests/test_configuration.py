"""Tests for the configuration module."""

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

import os
import unittest
import unittest.mock

from configuration import get_config


class ConfigurationTest(unittest.TestCase):
  """Test cases for configuration module."""

  @unittest.mock.patch.dict(os.environ, {
      "GCP_PROJECT_ID": "test-project",
      "GCP_PROJECT_LOCATION": "test-location",
      "GCS_BUCKET_NAME": "test-bucket",
  })
  def test_get_config_defaults(self):
    """Tests that get_config returns correct defaults."""
    config = get_config()

    self.assertEqual(config.gcp_project_id, "test-project")
    self.assertEqual(config.gcp_project_location, "test-location")
    self.assertEqual(config.gcs_bucket_name, "test-bucket")
    # Check default values
    self.assertEqual(config.gemini_model, "gemini-2.5-flash")
    self.assertEqual(config.gemini_flash_model, "gemini-2.5-flash")
    self.assertEqual(config.gemini_pro_model, "gemini-2.5-pro")
    self.assertEqual(config.audio_format, "mp3")
    self.assertEqual(config.video_format, "mp4")
    self.assertEqual(config.gemini_tts_model, "gemini-2.5-pro-tts")
    self.assertEqual(config.gemini_flash_tts_model, "gemini-2.5-flash-tts")
    self.assertEqual(config.gemini_pro_tts_model, "gemini-2.5-pro-tts")

  @unittest.mock.patch.dict(os.environ, {
      "GCP_PROJECT_ID": "test-project",
      "GCP_PROJECT_LOCATION": "test-location",
      "GCS_BUCKET_NAME": "test-bucket",
      "GEMINI_MODEL": "custom-model",
      "GEMINI_FLASH_MODEL": "custom-flash",
      "GEMINI_PRO_MODEL": "custom-pro",
      "AUDIO_FORMAT": "wav",
      "VIDEO_FORMAT": "avi",
      "GEMINI_TTS_MODEL": "custom-tts",
      "GEMINI_FLASH_TTS_MODEL": "custom-flash-tts",
      "GEMINI_PRO_TTS_MODEL": "custom-pro-tts",
  })
  def test_get_config_overrides(self):
    """Tests that get_config respects environment variable overrides."""
    config = get_config()

    self.assertEqual(config.gemini_model, "custom-model")
    self.assertEqual(config.gemini_flash_model, "custom-flash")
    self.assertEqual(config.gemini_pro_model, "custom-pro")
    self.assertEqual(config.audio_format, "wav")
    self.assertEqual(config.video_format, "avi")
    self.assertEqual(config.gemini_tts_model, "custom-tts")
    self.assertEqual(config.gemini_flash_tts_model, "custom-flash-tts")
    self.assertEqual(config.gemini_pro_tts_model, "custom-pro-tts")


if __name__ == "__main__":
  unittest.main()

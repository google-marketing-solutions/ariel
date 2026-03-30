"""Tests for the transcribe functions."""

# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
import unittest
import unittest.mock

import google.api_core.exceptions
import pydantic
from transcribe import transcribe_video


class TestTranscribeVideo(unittest.TestCase):
  """Test cases for the transcribe_video function."""

  @unittest.mock.patch("transcribe.google.genai.Client")
  def test_transcribe_video_success(self, mock_genai_client):
    """Tests a successful transcription and translation."""
    mock_client = mock_genai_client.return_value
    mock_response = unittest.mock.MagicMock()

    # Create a mock ProcessResponse
    process_response_data = {
        "primary_language": "en-US",
        "speakers": [{
            "speaker_id": "spk_0",
            "voice": "echo",
            "speaker_name": "Narrator",
            "gender": "male",
        }],
        "utterances": [{
            "id": "utt_0",
            "original_text": "Hello world.",
            "translated_text": "Hallo Welt.",
            "translation_instructions": "Formal translation.",
            "speaker": {
                "speaker_id": "spk_0",
                "voice": "echo",
                "speaker_name": "Narrator",
                "gender": "male",
            },
            "speaking_instructions": "Clear and friendly.",
            "original_start_time": 0.5,
            "original_end_time": 1.5,
            "translated_start_time": 0.0,
            "translated_end_time": 0.0,
            "speaking_rate": 1.0,
            "removed": False,
            "muted": False,
            "audio_url": "",
        }],
    }
    mock_response.text = json.dumps(process_response_data)
    mock_client.models.generate_content.return_value = mock_response

    gcs_video_path = "gs://fake-bucket/fake-video.mp4"
    translate_language = "de-DE"
    duration = 10.0
    gemini_model = "some-gemini-model"

    original_language, speaker_list, utterances = transcribe_video(
        gcs_video_path,
        translate_language,
        duration,
        mock_client,
        gemini_model,
    )

    self.assertEqual(original_language, "en-US")
    self.assertEqual(len(speaker_list), 1)
    self.assertEqual(speaker_list[0].speaker_id, "spk_0")
    self.assertEqual(len(utterances), 1)
    self.assertEqual(utterances[0].original_text, "Hello world.")
    self.assertEqual(utterances[0].translated_text, "Hallo Welt.")

    mock_client.models.generate_content.assert_called_once()
    call_args = mock_client.models.generate_content.call_args
    self.assertEqual(call_args.kwargs["model"], gemini_model)

  @unittest.mock.patch("transcribe.google.genai.Client")
  def test_transcribe_video_api_error(self, mock_genai_client):
    """Tests handling of a GoogleAPICallError."""
    mock_client = mock_genai_client.return_value
    mock_client.models.generate_content.side_effect = (
        google.api_core.exceptions.GoogleAPICallError("API Error")
    )

    gcs_video_path = "gs://fake-bucket/fake-video.mp4"
    translate_language = "de-DE"
    duration = 10.0
    gemini_model = "some-gemini-model"

    original_language, speaker_list, utterances = transcribe_video(
        gcs_video_path,
        translate_language,
        duration,
        mock_client,
        gemini_model,
    )

    self.assertEqual(original_language, "")
    self.assertEqual(speaker_list, [])
    self.assertEqual(utterances, [])

  @unittest.mock.patch("transcribe.google.genai.Client")
  def test_transcribe_video_validation_error(self, mock_genai_client):
    """Tests handling of a Pydantic ValidationError."""
    mock_client = mock_genai_client.return_value
    mock_response = unittest.mock.MagicMock()
    mock_response.text = (  # Invalid JSON for ProcessResponse
        '{"invalid": "json"}'
    )
    mock_client.models.generate_content.return_value = mock_response

    gcs_video_path = "gs://fake-bucket/fake-video.mp4"
    translate_language = "de-DE"
    duration = 10.0
    gemini_model = "some-gemini-model"

    with self.assertRaises(pydantic.ValidationError):
      transcribe_video(
          gcs_video_path,
          translate_language,
          duration,
          mock_client,
          gemini_model,
      )


if __name__ == "__main__":
  unittest.main()

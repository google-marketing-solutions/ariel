"""Tests for the transcribe functions."""

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
import unittest
import unittest.mock

import transcribe


class TranscribeTest(unittest.TestCase):
  """Test cases for the transcribe script."""

  @unittest.mock.patch("transcribe.whisper_model")
  def test_transcribe_media(self, mock_whisper_model):
    """Tests that transcribe_media returns a formatted transcript."""
    mock_segment = unittest.mock.MagicMock()
    mock_segment.start = 0.0
    mock_segment.end = 1.0
    mock_segment.text = "Hello world"
    mock_segments = [mock_segment]
    mock_info = unittest.mock.MagicMock()
    mock_info.language = "en"
    mock_info.language_probability = 0.9

    mock_whisper_model.transcribe.return_value = (mock_segments, mock_info)
    result = transcribe.transcribe_media("dummy_path")
    self.assertEqual(result, "[0.0s -> 1.0s]  Hello world")
    mock_whisper_model.transcribe.assert_called_once_with(
        "dummy_path", beam_size=5
    )

  @unittest.mock.patch("google.genai.Client")
  def test_annotate_transcript(self, mock_client):
    """Tests that annotate_transcript correctly processes the API response."""
    mock_response = unittest.mock.MagicMock()
    mock_response.text = json.dumps([{
        "speaker_id": "speaker_1",
        "gender": "female",
        "transcript": "Hello",
        "tone": "enthusiastic",
        "start_time": 0.5,
        "end_time": 1.0,
    }])
    mock_response.usage_metadata.total_token_count = 100
    mock_client.models.generate_content.return_value = mock_response

    segments = transcribe.annotate_transcript(
        client=mock_client,
        model_name="gemini-2.5-pro",
        gcs_uri="gs://dummy/audio.wav",
        num_speakers=1,
        script="[0.5s -> 1.0s] Hello",
        mime_type="audio/wav",
    )
    self.assertEqual(len(segments), 1)
    self.assertEqual(segments[0].speaker_id, "speaker_1")
    mock_client.models.generate_content.assert_called_once()

  @unittest.mock.patch("google.genai.Client")
  def test_match_voice(self, mock_client):
    """Tests that match_voice correctly maps speakers to voices."""
    segments = [
        transcribe.TranscribeSegment(
            speaker_id="speaker_1",
            gender="female",
            transcript="Hello",
            tone="enthusiastic",
            start_time=0.5,
            end_time=1.0,
        )
    ]
    mock_response = unittest.mock.MagicMock()
    mock_response.text = json.dumps({"voice_name": "Zephyr"})
    mock_response.usage_metadata.total_token_count = 50
    mock_client.models.generate_content.return_value = mock_response

    voice_map = transcribe.match_voice(
        client=mock_client,
        model_name="gemini-2.5-pro",
        segments=segments,
    )
    self.assertEqual(voice_map, {"speaker_1": "Zephyr"})
    mock_client.models.generate_content.assert_called_once()

  @unittest.mock.patch("transcribe.whisper_model")
  def test_transcribe_media_no_dialog(self, mock_whisper_model):
    """Tests that transcribe_media returns an empty string when no dialog is detected."""
    mock_segments = []
    mock_info = unittest.mock.MagicMock()
    mock_info.language = None
    mock_info.language_probability = 0.0

    mock_whisper_model.transcribe.return_value = (mock_segments, mock_info)
    result = transcribe.transcribe_media("dummy_path_no_dialog")
    self.assertEqual(result, "")
    mock_whisper_model.transcribe.assert_called_once_with(
        "dummy_path_no_dialog", beam_size=5
    )


if __name__ == "__main__":
  unittest.main()

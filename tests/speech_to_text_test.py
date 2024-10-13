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

"""Tests for utility functions in speech_to_text.py."""

from collections import namedtuple
import tempfile
from unittest.mock import MagicMock, patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import speech_to_text
from faster_whisper import WhisperModel
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np
from vertexai.generative_models import GenerativeModel


class TranscribeTests(parameterized.TestCase):

  def test_transcribe(self):
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      silence_duration = 5
      silence = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence.write_audiofile(temporary_file.name)
      mock_model = MagicMock(spec=WhisperModel)
      Segment = namedtuple("Segment", ["text"])
      mock_model.transcribe.return_value = [Segment(text="Test.")], None
      transcribed_text = speech_to_text.transcribe(
          vocals_filepath=temporary_file.name,
          advertiser_name="Advertiser Name",
          original_language="en",
          model=mock_model,
      )
      self.assertEqual(
          transcribed_text,
          "Test.",
      )

  @parameterized.named_parameters(
      ("exact_match", "Hello, how are you today?", ["how are you"], False),
      ("punctuation_difference", "That's great news!", ["great news"], False),
      ("case_insensitive", "This is a TEST sentence.", ["test"], False),
      (
          "multiple_phrases",
          "Hi there! How's it going?",
          ["hi there", "how's it going"],
          False,
      ),
      ("no_match", "This is a different sentence.", ["not found"], True),
      ("no_dubbing_phrases_empty", "Hello, how are you?", [], True),
  )
  def test_is_substring_present(
      self, utterance, no_dubbing_phrases, expected_result
  ):
    result = speech_to_text.is_substring_present(
        utterance=utterance, no_dubbing_phrases=no_dubbing_phrases
    )
    self.assertEqual(result, expected_result)

  @parameterized.named_parameters(
      ("with_dubbing_phrase", ["hello world"], False),
      ("without_dubbing_phrase", ["goodbye"], True),
      ("empty_no_dubbing_phrases", [], True),
  )
  def test_transcribe_chunks(self, no_dubbing_phrases, expected_for_dubbing):
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      silence_duration = 5
      silence = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence.write_audiofile(temporary_file.name)
      mock_model = MagicMock(spec=WhisperModel)
      Segment = namedtuple("Segment", ["text"])
      mock_model.transcribe.return_value = [
          Segment(text="hello world this is a test")
      ], None
      utterance_metadata = [dict(path=temporary_file.name, start=0.0, end=5.0)]
      advertiser_name = "Advertiser Name"
      original_language = "en"
      transcribed_audio_chunks = speech_to_text.transcribe_audio_chunks(
          utterance_metadata=utterance_metadata,
          advertiser_name=advertiser_name,
          original_language=original_language,
          model=mock_model,
          no_dubbing_phrases=no_dubbing_phrases,
      )
      expected_result = [
          dict(
              path=temporary_file.name,
              start=0.0,
              end=5.0,
              text="hello world this is a test",
              for_dubbing=expected_for_dubbing,
          )
      ]
      self.assertEqual(transcribed_audio_chunks, expected_result)


class GCSTest(absltest.TestCase):

  @patch("google.cloud.storage.Client", autospec=True)
  def test_create_gcs_bucket(self, mock_storage_client):
    mock_client = mock_storage_client.return_value
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    speech_to_text.create_gcs_bucket(
        gcp_project_id="test-project",
        gcs_bucket_name="test-bucket",
        gcp_region="US",
    )

    mock_client.bucket.assert_called_once_with("test-bucket")
    mock_bucket.create.assert_called_once_with(location="US")

  @patch("google.cloud.storage.Client", autospec=True)
  def test_upload_file_to_gcs(self, mock_storage_client):
    mock_client = mock_storage_client.return_value
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    speech_to_text.upload_file_to_gcs(
        gcp_project_id="test-project",
        gcs_bucket_name="test-bucket",
        file_path="test_file.txt",
    )

    mock_client.bucket.assert_called_once_with("test-bucket")
    mock_bucket.blob.assert_called_once_with("test_file.txt")
    mock_blob.upload_from_filename.assert_called_once_with("test_file.txt")

  @patch("google.cloud.storage.Client", autospec=True)
  def test_remove_gcs_bucket(self, mock_storage_client):
    mock_client = mock_storage_client.return_value
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    speech_to_text.remove_gcs_bucket(
        gcp_project_id="test-project", gcs_bucket_name="test-bucket"
    )

    mock_client.bucket.assert_called_once_with("test-bucket")
    mock_bucket.delete.assert_called_once_with(force=True)


class TestProcessSpeakerDiarizationResponse(parameterized.TestCase):

  @parameterized.parameters([
      ("", []),
      ("(speaker_1, female)\n", [("speaker_1", "female")]),
  ])
  def test_process_speaker_diarization_response(
      self, response, expected_output
  ):
    self.assertEqual(
        speech_to_text.process_speaker_diarization_response(response=response),
        expected_output,
    )


class DiarizationTest(absltest.TestCase):

  @patch("vertexai.generative_models.GenerativeModel.generate_content")
  def test_diarize_speakers(self, mock_generate_content):
    del mock_generate_content
    mock_model = MagicMock(spec=GenerativeModel)
    mock_model.generate_content.return_value = MagicMock(
        text="(speaker_01, Female), (speaker_02, Female)")
    utterance_metadata = [
        {
            "start": 0.00,
            "end": 10.00,
            "text": "Hello there!",
            "path": "path/to/audio1.mp3",
            "for_dubbing": True,
        },
        {
            "start": 10.00,
            "end": 20.00,
            "text": "How are you?",
            "path": "path/to/audio2.mp3",
            "for_dubbing": True,
        },
    ]
    result = speech_to_text.diarize_speakers(
        gcs_input_path="gs://test-bucket/test-video.mp4",
        utterance_metadata=utterance_metadata,
        number_of_speakers=2,
        model=mock_model,
    )
    expected_result = [("speaker_01", "Female"), ("speaker_02", "Female")]
    self.assertEqual(result, expected_result)


class AddSpeakerInfoTest(absltest.TestCase):

  def test_add_speaker_info(self):
    utterance_metadata = [
        {
            "text": "Hello",
            "start": 0.0,
            "end": 1.0,
            "path": "path/to/file.mp3",
        },
        {
            "text": "world",
            "start": 1.0,
            "end": 2.0,
            "path": "path/to/file.mp3",
        },
    ]
    speaker_info = [("speaker1", "male"), ("speaker2", "female")]
    expected_result = [
        {
            "text": "Hello",
            "start": 0.0,
            "end": 1.0,
            "speaker_id": "speaker1",
            "ssml_gender": "male",
            "path": "path/to/file.mp3",
        },
        {
            "text": "world",
            "start": 1.0,
            "end": 2.0,
            "speaker_id": "speaker2",
            "ssml_gender": "female",
            "path": "path/to/file.mp3",
        },
    ]
    result = speech_to_text.add_speaker_info(utterance_metadata, speaker_info)
    self.assertEqual(result, expected_result)

  def test_add_speaker_info_unequal_lengths(self):
    utterance_metadata = [
        {"text": "Hello", "start": 0.0, "stop": 1.0},
        {"text": "world", "start": 1.0, "stop": 2.0},
    ]
    speaker_info = [("speaker1", "male")]
    with self.assertRaisesRegex(
        speech_to_text.GeminiDiarizationError,
        "The length of 'utterance_metadata' and 'speaker_info' must be the"
        " same.",
    ):
      speech_to_text.add_speaker_info(utterance_metadata, speaker_info)


if __name__ == "__main__":
  absltest.main()

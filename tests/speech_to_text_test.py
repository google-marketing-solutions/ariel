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
import time
from unittest.mock import MagicMock, patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import speech_to_text
from faster_whisper import WhisperModel
import google.generativeai as genai
from google.generativeai.types import file_types
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np


class TranscribeTests(absltest.TestCase):

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

  def test_transcribe_chunks(self):
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
      transcribed_audio_chunks = speech_to_text.transcribe_audio_chunks(
          utterance_metadata=[
              dict(path=temporary_file.name, start=0.0, end=5.0)
          ],
          advertiser_name="Advertiser Name",
          original_language="en",
          model=mock_model,
      )
      self.assertEqual(
          transcribed_audio_chunks,
          [dict(path=temporary_file.name, start=0.0, end=5.0, text="Test.")],
      )


class UploadToGeminiTest(parameterized.TestCase):

  @parameterized.named_parameters(
      ("mp4_success", "test_path.mp4", "test_file.mp4", "video/mp4"),
      ("mp3_success", "test_path.mp3", "test_file.mp3", "audio/mpeg"),
  )
  def test_upload_to_gemini_success(
      self, file, expected_display_name, expected_mime_type
  ):
    mock_file = MagicMock(spec=file_types.File)
    mock_file.display_name = expected_display_name
    mock_file.uri = f"gs://test-bucket/{expected_display_name}"

    with patch(
        "google.generativeai.upload_file", return_value=mock_file
    ) as mock_upload_file:
      result_file = speech_to_text.upload_to_gemini(file=file)
      self.assertEqual(result_file.display_name, expected_display_name)
      self.assertEqual(
          result_file.uri, f"gs://test-bucket/{expected_display_name}"
      )
      mock_upload_file.assert_called_once_with(
          file, mime_type=expected_mime_type
      )

  def test_upload_to_gemini_invalid_extension(self):
    with self.assertRaises(ValueError):
      speech_to_text.upload_to_gemini(file="test_path.txt")


class WaitForFileActiveTest(absltest.TestCase):

  def test_wait_for_file_active_success(self):
    mock_file = MagicMock(spec=file_types.File)
    mock_file.state.name = speech_to_text._PROCESSING
    mock_file.name = "test_file.mp4"
    with patch("ariel.speech_to_text.wait_for_file_active", return_value=None):
      mock_file.state.name = speech_to_text._ACTIVE
      speech_to_text.wait_for_file_active(file=mock_file)

  def test_wait_for_file_active_timeout(self):
    mock_file = MagicMock(spec=file_types.File)
    mock_file.state.name = speech_to_text._PROCESSING
    mock_file.name = "test_file.mp4"
    mock_get_file = MagicMock(return_value=mock_file)
    with patch("ariel.speech_to_text.genai.get_file", new=mock_get_file):
      with patch(
          "ariel.speech_to_text.wait_for_file_active"
      ) as mock_wait_for_file:
        mock_wait_for_file.side_effect = speech_to_text.FileProcessingError(
            "File 'test_file.mp4' failed to process."
        )
        with patch(
            "time.sleep", side_effect=lambda _: time.sleep(0.1)
        ) as mock_sleep:
          with self.assertRaisesRegex(
              speech_to_text.FileProcessingError,
              "File 'test_file.mp4' failed to process.",
          ):
            speech_to_text.wait_for_file_active(file=mock_file)


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


class DiarizeSpeakersTest(absltest.TestCase):

  @patch("google.generativeai")
  @patch("ariel.speech_to_text.wait_for_file_active")
  @patch("ariel.speech_to_text.upload_to_gemini")
  def test_diarize_speakers(
      self, mock_upload_to_gemini, mock_wait_for_file_active, mock_genai
  ):
    video_file = "test_video.mp4"
    utterance_metadata = [
        {"start": 0.0, "stop": 5.0, "text": "Hello, this is a test video."},
        {"start": 5.0, "stop": 10.0, "text": "How are you?"},
    ]
    number_of_speakers = 2
    model = MagicMock(spec=genai.GenerativeModel)
    diarization_instructions = "Please be specific."

    mock_chat_session = MagicMock()
    mock_chat_session.send_message.return_value = MagicMock(
        text="(speaker_1, Male), (speaker_2, Female)"
    )
    mock_chat_session.rewind.return_value = None
    model.start_chat.return_value = mock_chat_session

    mock_file = MagicMock()
    mock_file.name = "test_video.mp4"
    mock_file.state = MagicMock(name="ACTIVE")
    mock_upload_to_gemini.return_value = mock_file

    result = speech_to_text.diarize_speakers(
        file=video_file,
        utterance_metadata=utterance_metadata,
        number_of_speakers=number_of_speakers,
        model=model,
        diarization_instructions=diarization_instructions,
    )

    self.assertEqual(result, [("speaker_1", "Male"), ("speaker_2", "Female")])

  @patch("google.generativeai")
  @patch("ariel.speech_to_text.wait_for_file_active")
  @patch("ariel.speech_to_text.upload_to_gemini")
  def test_diarize_speakers_file_processing_error(
      self, mock_upload_to_gemini, mock_wait_for_file_active, mock_genai
  ):
    video_file = "test_video.mp4"
    utterance_metadata = [
        {"start": 0.0, "stop": 5.0, "text": "Hello, this is a test video."},
        {"start": 5.0, "stop": 10.0, "text": "How are you?"},
    ]
    number_of_speakers = 2
    model = MagicMock(spec=genai.GenerativeModel)

    mock_file = MagicMock()
    mock_file.name = "test_video.mp4"
    mock_file.state = MagicMock(name="PROCESSING")
    mock_upload_to_gemini.return_value = mock_file

    mock_wait_for_file_active.side_effect = speech_to_text.FileProcessingError(
        "File processing failed."
    )

    with self.assertRaises(speech_to_text.FileProcessingError) as context:
      speech_to_text.diarize_speakers(
          file=video_file,
          utterance_metadata=utterance_metadata,
          number_of_speakers=number_of_speakers,
          model=model,
      )

    self.assertEqual(str(context.exception), "File processing failed.")


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
        ValueError,
        "The length of 'utterance_metadata' and 'speaker_info' must be the"
        " same.",
    ):
      speech_to_text.add_speaker_info(utterance_metadata, speaker_info)


if __name__ == "__main__":
  absltest.main()

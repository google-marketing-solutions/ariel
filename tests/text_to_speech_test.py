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

"""Tests for utility functions in text_to_speech.py."""

import tempfile
from unittest.mock import MagicMock
from absl.testing import absltest
from absl.testing import parameterized
from ariel import text_to_speech
from google.cloud import texttospeech
from pydub import AudioSegment


class ListAvailableVoicesTest(absltest.TestCase):

  def test_list_available_voices(self):
    mock_client = MagicMock(spec=texttospeech.TextToSpeechClient)
    mock_response = texttospeech.ListVoicesResponse(
        voices=[
            texttospeech.Voice(
                name="en-US-Standard-A",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            ),
            texttospeech.Voice(
                name="en-US-Standard-B",
                ssml_gender=texttospeech.SsmlVoiceGender.MALE,
            ),
            texttospeech.Voice(
                name="en-US-Standard-C",
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
            ),
        ]
    )
    mock_client.list_voices.return_value = mock_response
    result = text_to_speech.list_available_voices("en-US", client=mock_client)
    self.assertEqual(
        result,
        {
            "en-US-Standard-A": "Female",
            "en-US-Standard-B": "Male",
            "en-US-Standard-C": "Neutral",
        },
    )


class TestAssignVoices(parameterized.TestCase):

  @parameterized.named_parameters([
      (
          "preferred_voices_match",
          [
              {"speaker_id": "speaker1", "ssml_gender": "Male"},
              {"speaker_id": "speaker2", "ssml_gender": "Female"},
          ],
          ["News", "Studio"],
          {"speaker1": "en-US-News-B", "speaker2": "en-US-Studio-C"},
          True,
      ),
      (
          "no_preferred_voices_match",
          [
              {"speaker_id": "speaker1", "ssml_gender": "Male"},
              {"speaker_id": "speaker2", "ssml_gender": "Female"},
          ],
          ["NonExistent1", "NonExistent2"],
          {"speaker1": None, "speaker2": None},
          True,
      ),
      (
          "no_preferred_voices_no_fallback",
          [
              {"speaker_id": "speaker1", "ssml_gender": "Male"},
              {"speaker_id": "speaker2", "ssml_gender": "Female"},
          ],
          None,
          {"speaker1": None, "speaker2": None},
          False,
      ),
  ])
  def test_assign_voices(
      self,
      utterance_metadata,
      preferred_voices,
      expected_assignment,
      fallback_no_preferred_category_match,
  ):
    mock_client = MagicMock(spec=texttospeech.TextToSpeechClient)
    mock_response = texttospeech.ListVoicesResponse(
        voices=[
            texttospeech.Voice(
                name="en-US-News-B",
                ssml_gender=texttospeech.SsmlVoiceGender.MALE,
            ),
            texttospeech.Voice(
                name="en-US-Studio-C",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            ),
        ]
    )
    mock_client.list_voices.return_value = mock_response

    assignment = text_to_speech.assign_voices(
        utterance_metadata=utterance_metadata,
        target_language="en-US",
        client=mock_client,
        preferred_voices=preferred_voices,
        fallback_no_preferred_category_match=fallback_no_preferred_category_match,
    )
    self.assertEqual(assignment, expected_assignment)


class UpdateUtteranceMetadataTest(absltest.TestCase):

  def test_update_utterance_metadata(self):
    utterance_metadata = [
        {
            "start": 0.0,
            "end": 1.0,
            "chunk_path": "path/to/chunk1.wav",
            "translated_text": "Hello",
            "speaker_id": "speaker1",
            "ssml_gender": "male",
        },
        {
            "start": 1.0,
            "end": 2.0,
            "chunk_path": "path/to/chunk2.wav",
            "translated_text": "World",
            "speaker_id": "speaker2",
            "ssml_gender": "female",
        },
    ]
    assigned_voices = {
        "speaker1": "en-US-Wavenet-C",
        "speaker2": "en-US-Wavenet-F",
    }
    expected_output = [
        {
            "start": 0.0,
            "end": 1.0,
            "chunk_path": "path/to/chunk1.wav",
            "translated_text": "Hello",
            "speaker_id": "speaker1",
            "ssml_gender": "male",
            "assigned_google_voice": "en-US-Wavenet-C",
            "google_voice_pitch": -12.0,
            "google_voice_speed": 1.0,
            "google_voice_volume_gain_db": 16.0,
        },
        {
            "start": 1.0,
            "end": 2.0,
            "chunk_path": "path/to/chunk2.wav",
            "translated_text": "World",
            "speaker_id": "speaker2",
            "ssml_gender": "female",
            "assigned_google_voice": "en-US-Wavenet-F",
            "google_voice_pitch": -12.0,
            "google_voice_speed": 1.0,
            "google_voice_volume_gain_db": 16.0,
        },
    ]
    actual_output = text_to_speech.update_utterance_metadata(
        utterance_metadata=utterance_metadata, assigned_voices=assigned_voices
    )
    self.assertEqual(actual_output, expected_output)


class TestConvertTextToSpeech(absltest.TestCase):

  def test_convert_text_to_speech(self):
    mock_client = MagicMock(spec=texttospeech.TextToSpeechClient)
    mock_response = texttospeech.SynthesizeSpeechResponse(
        audio_content=b"mock_audio_data"
    )
    mock_client.synthesize_speech.return_value = mock_response
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      output_file = temporary_file.name
      result = text_to_speech.convert_text_to_speech(
          client=mock_client,
          assigned_google_voice="en-US-Wavenet-A",
          target_language="en-US",
          output_filename=output_file,
          text="This is a test.",
          pitch=0.0,
          speed=1.0,
          volume_gain_db=0.0,
      )
      self.assertEqual(result, output_file)
      mock_client.synthesize_speech.assert_called_once()


class TestAdjustAudioSpeed(parameterized.TestCase):

  def test_adjust_audio_speed_positive_duration(self):
    """Tests adjustment when target duration is valid."""
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
      sample_audio = AudioSegment.silent(duration=5.0 * 1000)
      sample_audio.export(temp_file.name, format="mp3")
      target_duration = 3.0
      text_to_speech.adjust_audio_speed(
          input_mp3_path=temp_file.name, target_duration=target_duration
      )
      adjusted_audio = AudioSegment.from_mp3(temp_file.name)
      self.assertAlmostEqual(
          adjusted_audio.duration_seconds, target_duration, delta=0.2
      )

  def test_adjust_audio_speed_zero_duration(self):
    """Tests error handling when target duration is zero."""
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
      sample_audio = AudioSegment.silent(duration=5.0 * 1000)
      sample_audio.export(temp_file.name, format="mp3")
      target_duration = 0.0
      with self.assertRaisesRegex(
          ValueError,
          "The target duration must be more than 0.0 seconds. Got"
          f" {target_duration}.",
      ):
        text_to_speech.adjust_audio_speed(
            input_mp3_path=temp_file.name, target_duration=target_duration
        )

  @parameterized.named_parameters(
      ("TargetBelowMinimum", 0.8, 0.5),
      ("InputBelowMinimum", 2.0, 0.5),
  )
  def test_adjust_audio_speed_below_minimum(
      self, target_duration, expected_duration
  ):
    """Tests when target or input duration is below the minimum."""
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
      sample_audio = AudioSegment.silent(duration=0.5 * 1000)
      sample_audio.export(temp_file.name, format="mp3")
      text_to_speech.adjust_audio_speed(
          input_mp3_path=temp_file.name, target_duration=target_duration
      )
      adjusted_audio = AudioSegment.from_mp3(temp_file.name)
      self.assertAlmostEqual(
          adjusted_audio.duration_seconds, expected_duration, delta=0.1
      )


class TestDubUtterances(absltest.TestCase):

  def setUp(self):
    self.mock_adjust_audio_speed = MagicMock()
    self.mock_client = MagicMock(spec=texttospeech.TextToSpeechClient)
    self.original_convert_text_to_speech = text_to_speech.convert_text_to_speech
    self.original_adjust_audio_speed = text_to_speech.adjust_audio_speed
    text_to_speech.adjust_audio_speed = self.mock_adjust_audio_speed

  def tearDown(self):
    text_to_speech.convert_text_to_speech = self.original_convert_text_to_speech
    text_to_speech.adjust_audio_speed = self.original_adjust_audio_speed

  def test_dub_utterances(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      utterance_metadata = [
          {
              "start": 0.0,
              "end": 5.5,
              "path": "chunk_1.wav",
              "translated_text": "This is dubbed text 1.",
              "assigned_google_voice": "en-US-Wavenet-A",
              "for_dubbing": True,
              "google_voice_pitch": 0.0,
              "google_voice_speed": 1.0,
              "google_voice_volume_gain_db": 0.0,
          },
          {
              "start": 5.5,
              "end": 12.0,
              "path": "chunk_2.wav",
              "translated_text": "This is dubbed text 2.",
              "assigned_google_voice": "en-US-Wavenet-B",
              "for_dubbing": False,
              "google_voice_pitch": 0.0,
              "google_voice_speed": 1.0,
              "google_voice_volume_gain_db": 0.0,
          },
      ]

      def mock_convert_text_to_speech(
          client,
          assigned_google_voice,
          target_language,
          output_filename,
          text,
          pitch,
          speed,
          volume_gain_db,
      ):
        del (
            client,
            assigned_google_voice,
            target_language,
            text,
            pitch,
            speed,
            volume_gain_db,
        )
        return output_filename

      text_to_speech.convert_text_to_speech = mock_convert_text_to_speech
      result = text_to_speech.dub_utterances(
          client=self.mock_client,
          utterance_metadata=utterance_metadata,
          output_directory=temp_dir,
          target_language="en-US",
      )
      expected_output = [
          {
              "start": 0.0,
              "end": 5.5,
              "path": "chunk_1.wav",
              "translated_text": "This is dubbed text 1.",
              "assigned_google_voice": "en-US-Wavenet-A",
              "google_voice_pitch": 0.0,
              "google_voice_speed": 1.0,
              "google_voice_volume_gain_db": 0.0,
              "dubbed_path": f"{temp_dir}/dubbed_chunk_1.mp3",
              "for_dubbing": True,
          },
          {
              "start": 5.5,
              "end": 12.0,
              "path": "chunk_2.wav",
              "translated_text": "This is dubbed text 2.",
              "assigned_google_voice": "en-US-Wavenet-B",
              "google_voice_pitch": 0.0,
              "google_voice_speed": 1.0,
              "google_voice_volume_gain_db": 0.0,
              "dubbed_path": "chunk_2.wav",
              "for_dubbing": False,
          },
      ]
      self.assertEqual(result, expected_output)


if __name__ == "__main__":
  absltest.main()

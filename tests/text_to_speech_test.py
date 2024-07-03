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
from elevenlabs.client import ElevenLabs
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


class TestElevenLabsAssignVoices(absltest.TestCase):

  def setUp(self):
    self.mock_client = MagicMock()
    voice1 = MagicMock(name="Voice1", labels={"gender": "male"})
    voice2 = MagicMock(name="Voice2", labels={"gender": "female"})
    rachel = MagicMock(name="Rachel", labels={"gender": "female"})
    voice1.name = "Voice1"
    voice2.name = "Voice2"
    rachel.name = "Rachel"
    self.mock_client.voices.get_all.return_value.voices = [
        voice1,
        voice2,
        rachel,
    ]

  def test_assign_voices_with_preferred_voices(self):
    utterance_metadata = [
        {
            "start": 0,
            "end": 1,
            "chunk_path": "path1",
            "translated_text": "text1",
            "speaker_id": "1",
            "ssml_gender": "Male",
        },
        {
            "start": 1,
            "end": 2,
            "chunk_path": "path2",
            "translated_text": "text2",
            "speaker_id": "2",
            "ssml_gender": "Female",
        },
    ]
    preferred_voices = ["Rachel"]
    expected_result = {"1": "Voice1", "2": "Rachel"}
    result = text_to_speech.elevenlabs_assign_voices(
        utterance_metadata=utterance_metadata,
        client=self.mock_client,
        preferred_voices=preferred_voices,
    )
    self.assertEqual(result, expected_result)

  def test_assign_voices_without_preferred_voices(self):
    utterance_metadata = [
        {
            "start": 0,
            "end": 1,
            "chunk_path": "path1",
            "translated_text": "text1",
            "speaker_id": "1",
            "ssml_gender": "Male",
        },
        {
            "start": 1,
            "end": 2,
            "chunk_path": "path2",
            "translated_text": "text2",
            "speaker_id": "2",
            "ssml_gender": "Female",
        },
    ]
    expected_result = {"1": "Voice1", "2": "Voice2"}
    result = text_to_speech.elevenlabs_assign_voices(
        utterance_metadata=utterance_metadata,
        client=self.mock_client,
    )
    self.assertEqual(result, expected_result)

  def test_assign_voices_with_fallback(self):
    utterance_metadata = [
        {
            "start": 0,
            "end": 1,
            "chunk_path": "path1",
            "translated_text": "text1",
            "speaker_id": "1",
            "ssml_gender": "Male",
        },
        {
            "start": 1,
            "end": 2,
            "chunk_path": "path2",
            "translated_text": "text2",
            "speaker_id": "2",
            "ssml_gender": "Female",
        },
        {
            "start": 2,
            "end": 3,
            "chunk_path": "path3",
            "translated_text": "text3",
            "speaker_id": "3",
            "ssml_gender": "Female",
        },
    ]
    preferred_voices = ["Rachel"]
    expected_result = {"1": "Voice1", "2": "Rachel", "3": "Voice2"}
    result = text_to_speech.elevenlabs_assign_voices(
        utterance_metadata=utterance_metadata,
        client=self.mock_client,
        preferred_voices=preferred_voices,
        fallback_no_preferred_category_match=True,
    )

    self.assertEqual(result, expected_result)

  def test_assign_voices_with_no_matching_voices(self):
    utterance_metadata = [
        {
            "start": 0,
            "end": 1,
            "chunk_path": "path1",
            "translated_text": "text1",
            "speaker_id": "1",
            "ssml_gender": "Male",
        },
    ]
    voice2 = MagicMock(name="Voice2", labels={"gender": "female"})
    voice2.name = "Voice2"
    self.mock_client.voices.get_all.return_value.voices = [voice2]
    expected_result = {"1": None}
    result = text_to_speech.elevenlabs_assign_voices(
        utterance_metadata=utterance_metadata,
        client=self.mock_client,
        fallback_no_preferred_category_match=True,
    )
    self.assertEqual(result, expected_result)


class UpdateUtteranceMetadataTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "GoogleTTS",
          False,
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "path/to/chunk1.mp3",
                  "translated_text": "Hello",
                  "speaker_id": "speaker1",
                  "ssml_gender": "Male",
              },
              {
                  "start": 1.0,
                  "end": 2.0,
                  "chunk_path": "path/to/chunk2.mp3",
                  "translated_text": "World",
                  "speaker_id": "speaker2",
                  "ssml_gender": "Female",
              },
          ],
          {
              "speaker1": "en-US-Wavenet-C",
              "speaker2": "en-US-Wavenet-F",
          },
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "path/to/chunk1.mp3",
                  "translated_text": "Hello",
                  "speaker_id": "speaker1",
                  "ssml_gender": "Male",
                  "assigned_voice": "en-US-Wavenet-C",
                  "pitch": -10.0,
                  "speed": 1.0,
                  "volume_gain_db": 16.0,
              },
              {
                  "start": 1.0,
                  "end": 2.0,
                  "chunk_path": "path/to/chunk2.mp3",
                  "translated_text": "World",
                  "speaker_id": "speaker2",
                  "ssml_gender": "Female",
                  "assigned_voice": "en-US-Wavenet-F",
                  "pitch": -5.0,
                  "speed": 1.0,
                  "volume_gain_db": 16.0,
              },
          ],
      ),
      (
          "OtherTTS",
          True,
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "path/to/chunk1.mp3",
                  "translated_text": "Hello",
                  "speaker_id": "speaker1",
                  "ssml_gender": "Male",
              },
              {
                  "start": 1.0,
                  "end": 2.0,
                  "chunk_path": "path/to/chunk2.mp3",
                  "translated_text": "World",
                  "speaker_id": "speaker2",
                  "ssml_gender": "Female",
              },
          ],
          {"speaker1": "Callum", "speaker2": "Sophie"},
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "path/to/chunk1.mp3",
                  "translated_text": "Hello",
                  "speaker_id": "speaker1",
                  "ssml_gender": "Male",
                  "assigned_voice": "Callum",
                  "stability": 0.5,
                  "similarity_boost": 0.75,
                  "style": 0.0,
                  "use_speaker_boost": True,
              },
              {
                  "start": 1.0,
                  "end": 2.0,
                  "chunk_path": "path/to/chunk2.mp3",
                  "translated_text": "World",
                  "speaker_id": "speaker2",
                  "ssml_gender": "Female",
                  "assigned_voice": "Sophie",
                  "stability": 0.5,
                  "similarity_boost": 0.75,
                  "style": 0.0,
                  "use_speaker_boost": True,
              },
          ],
      ),
  )
  def test_update_utterance_metadata(
      self, use_elevenlabs, utterance_metadata, assigned_voices, expected_output
  ):
    actual_output = text_to_speech.update_utterance_metadata(
        utterance_metadata=utterance_metadata,
        assigned_voices=assigned_voices,
        use_elevenlabs=use_elevenlabs,
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


class TestElevenlabsConvertTextToSpeech(absltest.TestCase):

  def test_convert_text_to_speech(self):
    mock_client = MagicMock(spec=ElevenLabs)
    mock_audio = b"mock_audio_data"
    mock_client.generate = MagicMock(return_value=mock_audio)
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      output_file = temporary_file.name

      result = text_to_speech.elevenlabs_convert_text_to_speech(
          client=mock_client,
          model="eleven_multilingual_v2",
          assigned_elevenlabs_voice="Bella",
          output_filename=output_file,
          text="This is a test for ElevenLabs conversion.",
          stability=0.5,
          similarity_boost=0.8,
          style=0.6,
          use_speaker_boost=True,
      )
      self.assertEqual(result, output_file)


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


class TestDubUtterances(parameterized.TestCase):

  def setUp(self):
    self.mock_adjust_audio_speed = MagicMock()
    text_to_speech.adjust_audio_speed = self.mock_adjust_audio_speed
    self.mock_convert_text_to_speech = MagicMock(return_value="dummy_path")
    self.original_convert_text_to_speech = text_to_speech.convert_text_to_speech
    self.original_elevenlabs_convert_text_to_speech = (
        text_to_speech.elevenlabs_convert_text_to_speech
    )
    self.mock_client = MagicMock()

  def tearDown(self):
    text_to_speech.convert_text_to_speech = self.original_convert_text_to_speech
    text_to_speech.adjust_audio_speed = text_to_speech.adjust_audio_speed
    text_to_speech.elevenlabs_convert_text_to_speech = (
        self.original_elevenlabs_convert_text_to_speech
    )

  @parameterized.named_parameters(
      (
          "TextToSpeech",
          texttospeech.TextToSpeechClient,
          [{
              "start": 0.0,
              "end": 5.5,
              "path": "chunk_1.mp3",
              "translated_text": "This is dubbed text 1.",
              "assigned_voice": "en-US-Wavenet-A",
              "for_dubbing": True,
              "pitch": 0.0,
              "speed": 1.0,
              "volume_gain_db": 0.0,
          }],
          [{
              "start": 0.0,
              "end": 5.5,
              "path": "chunk_1.mp3",
              "translated_text": "This is dubbed text 1.",
              "assigned_voice": "en-US-Wavenet-A",
              "for_dubbing": True,
              "pitch": 0.0,
              "speed": 1.0,
              "volume_gain_db": 0.0,
              "dubbed_path": "dummy_path",
          }],
      ),
      (
          "ElevenLabs",
          ElevenLabs,
          [{
              "start": 5.5,
              "end": 12.0,
              "path": "chunk_2.mp3",
              "translated_text": "This is dubbed text 2.",
              "assigned_voice": "Callum",
              "for_dubbing": False,
              "stability": 0.5,
              "similarity_boost": 0.8,
              "style": "friendly",
              "use_speaker_boost": True,
          }],
          [{
              "start": 5.5,
              "end": 12.0,
              "path": "chunk_2.mp3",
              "translated_text": "This is dubbed text 2.",
              "assigned_voice": "Callum",
              "for_dubbing": False,
              "stability": 0.5,
              "similarity_boost": 0.8,
              "style": "friendly",
              "use_speaker_boost": True,
              "dubbed_path": "chunk_2.mp3",
          }],
      ),
  )
  def test_dub_utterances(self, client_class, input_metadata, expected_output):
    with tempfile.TemporaryDirectory() as temp_dir:
      self.mock_client = MagicMock(spec=client_class)
      utterance_metadata = input_metadata
      if client_class == texttospeech.TextToSpeechClient:
        text_to_speech.convert_text_to_speech = self.mock_convert_text_to_speech
      else:
        text_to_speech.elevenlabs_convert_text_to_speech = (
            self.mock_convert_text_to_speech
        )
      result = text_to_speech.dub_utterances(
          client=self.mock_client,
          utterance_metadata=utterance_metadata,
          output_directory=temp_dir,
          target_language="en-US",
      )
      self.assertEqual(result, expected_output)


if __name__ == "__main__":
  absltest.main()

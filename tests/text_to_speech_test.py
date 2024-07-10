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

import os
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch
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
          "google_tts",
          False,
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
          "other_tts",
          True,
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
      (
          "clone_voices",
          True,
          True,
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "path/to/chunk1.mp3",
                  "translated_text": "Hello",
                  "speaker_id": "speaker1",
              },
          ],
          None,
          [{
              "start": 0.0,
              "end": 1.0,
              "chunk_path": "path/to/chunk1.mp3",
              "translated_text": "Hello",
              "speaker_id": "speaker1",
              "stability": 0.5,
              "similarity_boost": 0.75,
              "style": 0.0,
              "use_speaker_boost": True,
          }],
      ),
  )
  def test_update_utterance_metadata(
      self,
      use_elevenlabs,
      clone_voices,
      utterance_metadata,
      assigned_voices,
      expected_output,
  ):
    actual_output = text_to_speech.update_utterance_metadata(
        utterance_metadata=utterance_metadata,
        assigned_voices=assigned_voices,
        use_elevenlabs=use_elevenlabs,
        clone_voices=clone_voices,
    )
    self.assertEqual(actual_output, expected_output)

  def test_update_utterance_metadata_clone_voices_without_elevenlabs(self):
    utterance_metadata = [
        {
            "start": 0.0,
            "end": 1.0,
            "chunk_path": "path/to/chunk1.mp3",
            "translated_text": "Hello",
            "speaker_id": "speaker1",
        },
    ]
    assigned_voices = {"speaker1": "en-US-Wavenet-C"}
    use_elevenlabs = False
    clone_voices = True
    with self.assertRaises(ValueError):
      text_to_speech.update_utterance_metadata(
          utterance_metadata=utterance_metadata,
          assigned_voices=assigned_voices,
          use_elevenlabs=use_elevenlabs,
          clone_voices=clone_voices,
      )


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


class TestCreateSpeakerToPathsMapping(parameterized.TestCase):

  @parameterized.named_parameters(
      ("empty_input", [], {}),
      (
          "single_speaker",
          [
              {"speaker_id": "speaker1", "vocals_path": "path/to/file1.wav"},
              {"speaker_id": "speaker1", "vocals_path": "path/to/file2.wav"},
          ],
          {"speaker1": ["path/to/file1.wav", "path/to/file2.wav"]},
      ),
      (
          "multiple_speakers",
          [
              {"speaker_id": "speaker1", "vocals_path": "path/to/file1.wav"},
              {"speaker_id": "speaker2", "vocals_path": "path/to/file3.wav"},
              {"speaker_id": "speaker1", "vocals_path": "path/to/file2.wav"},
          ],
          {
              "speaker1": ["path/to/file1.wav", "path/to/file2.wav"],
              "speaker2": ["path/to/file3.wav"],
          },
      ),
  )
  def test_create_speaker_to_paths_mapping(self, input_data, expected_result):
    result = text_to_speech.create_speaker_to_paths_mapping(input_data)
    self.assertEqual(result, expected_result)


from elevenlabs.types.voice import Voice


class TestElevenlabsCloneVoices(absltest.TestCase):

  def test_clone_voices_success(self):
    mock_client = MagicMock(spec=ElevenLabs)
    mock_voice = MagicMock(spec=Voice)
    mock_client.clone.return_value = mock_voice
    speaker_to_paths_mapping = {
        "speaker1": ["path/to/audio1.wav", "path/to/audio2.wav"],
        "speaker2": ["path/to/audio3.wav"],
    }
    result = text_to_speech.elevenlabs_clone_voices(
        client=mock_client, speaker_to_paths_mapping=speaker_to_paths_mapping
    )
    self.assertEqual(result, {"speaker1": mock_voice, "speaker2": mock_voice})
    mock_client.clone.assert_called()


class TestAdjustAudioSpeed(absltest.TestCase):

  @patch("pydub.AudioSegment.from_file")
  @patch("pydub.AudioSegment.export")
  def test_adjust_speed_with_calculated_speed(
      self, mock_export, mock_from_file
  ):
    reference_audio_mock = AudioSegment.silent(duration=60000)
    dubbed_audio_mock = AudioSegment.silent(duration=90000)
    mock_from_file.side_effect = [reference_audio_mock, dubbed_audio_mock]
    speedup_result_mock = AudioSegment.silent(duration=60000)

    def mock_speedup(audio_segment, speed, chunk_size, crossfade):
      del audio_segment
      self.assertEqual(speed, 1.5)
      self.assertEqual(chunk_size, 50)
      self.assertEqual(crossfade, 500)
      return speedup_result_mock

    with patch("pydub.effects.speedup", new=mock_speedup):
      text_to_speech.adjust_audio_speed(
          reference_file="ref.mp3", dubbed_file="dub.mp3"
      )
    mock_from_file.assert_any_call("ref.mp3")
    mock_from_file.assert_any_call("dub.mp3")
    mock_export.assert_called_once_with("dub.mp3", format="mp3")


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

    @patch("text_to_speech.create_speaker_to_paths_mapping")
    @patch("text_to_speech.elevenlabs_clone_voices")
    @patch("text_to_speech.elevenlabs_convert_text_to_speech")
    def test_dub_utterances_elevenlabs_clone_voices_success(
        self,
        mock_convert_text_to_speech,
        mock_elevenlabs_clone_voices,
        mock_create_speaker_to_paths_mapping,
    ):
      """Tests successful dubbing with ElevenLabs voice cloning."""
      input_metadata = [{
          "start": 0.0,
          "end": 5.5,
          "path": "chunk_1.mp3",
          "translated_text": "This is dubbed text 1.",
          "assigned_voice": "Callum",
          "for_dubbing": True,
          "stability": 0.5,
          "similarity_boost": 0.8,
          "style": "friendly",
          "use_speaker_boost": True,
          "speaker_id": "speaker_1",
      }]

      expected_output = [{
          "start": 0.0,
          "end": 5.5,
          "path": "chunk_1.mp3",
          "translated_text": "This is dubbed text 1.",
          "assigned_voice": "Callum",
          "for_dubbing": True,
          "stability": 0.5,
          "similarity_boost": 0.8,
          "style": "friendly",
          "use_speaker_boost": True,
          "speaker_id": "speaker_1",
          "dubbed_path": "dummy_path",
      }]
      mock_create_speaker_to_paths_mapping.return_value = {
          "speaker_1": ["chunk_1.mp3"]
      }
      mock_elevenlabs_clone_voices.return_value = {"speaker_1": "Callum"}
      mock_convert_text_to_speech.return_value = "dummy_path"

      with tempfile.TemporaryDirectory() as temp_dir:
        mock_client = MagicMock(spec=ElevenLabs)

        result = text_to_speech.dub_utterances(
            client=mock_client,
            utterance_metadata=input_metadata,
            output_directory=temp_dir,
            target_language="en-US",
            use_elevenlabs=True,
            clone_voices=True,
        )
        self.assertEqual(result, expected_output)

  def test_dub_utterances_clone_voices_error(self):
    with self.assertRaisesRegex(
        ValueError, "Voice cloning requires using ElevenLabs API."
    ):
      text_to_speech.dub_utterances(
          client=self.mock_client,
          utterance_metadata=[],
          output_directory="dummy_dir",
          target_language="en-US",
          clone_voices=True,
      )


if __name__ == "__main__":
  absltest.main()

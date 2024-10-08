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

import io
import os
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import text_to_speech
from elevenlabs.client import ElevenLabs
from elevenlabs.types.voice import Voice
from google.cloud import texttospeech
import numpy as np
from pydub import AudioSegment
import scipy


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
      ),
      (
          "no_preferred",
          [
              {"speaker_id": "speaker1", "ssml_gender": "Male"},
              {"speaker_id": "speaker2", "ssml_gender": "Female"},
          ],
          None,
          {"speaker1": "en-US-News-B", "speaker2": "en-US-Studio-C"},
      ),
  ])
  def test_assign_voices(
      self,
      utterance_metadata,
      preferred_voices,
      expected_assignment,
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
    )
    self.assertEqual(assignment, expected_assignment)

  def test_assign_voices_value_error(self):
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
    utterance_metatdata = [
        {"speaker_id": "speaker1", "ssml_gender": "Male"},
        {"speaker_id": "speaker2", "ssml_gender": "Female"},
    ]
    preferred_voices = ["NonExistent1", "NonExistent2"]
    with self.assertRaisesRegex(
        ValueError, "Could not allocate a voice for speaker_id"
    ):
      text_to_speech.assign_voices(
          utterance_metadata=utterance_metatdata,
          target_language="en-US",
          client=mock_client,
          preferred_voices=preferred_voices,
      )


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


class TestElevenLabsAssignVoicesValueError(absltest.TestCase):

  def setUp(self):
    self.mock_client = MagicMock()
    self.mock_client.voices.get_all.return_value.voices = []

  def test_assign_voices_value_error(self):
    self.mock_client.voices.get_all.return_value.voices = []
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
    with self.assertRaisesRegex(
        ValueError, "No suitable voice found for speaker_id"
    ):
      text_to_speech.elevenlabs_assign_voices(
          utterance_metadata=utterance_metadata,
          client=self.mock_client,
          preferred_voices=["Unknown"],
      )


class TestAddTextToSpeechProperties(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "NoElevenLabsFemale",
          False,
          "Female",
          {
              "text": "Hello there!",
              "start": 0.0,
              "end": 1.5,
              "speaker_id": "speaker1",
              "ssml_gender": "Female",
              "pitch": text_to_speech._DEFAULT_SSML_FEMALE_PITCH,
              "speed": text_to_speech._DEFAULT_SPEED,
              "volume_gain_db": text_to_speech._DEFAULT_VOLUME_GAIN_DB,
          },
      ),
      (
          "NoElevenLabsMale",
          False,
          "Male",
          {
              "text": "Hello there!",
              "start": 0.0,
              "end": 1.5,
              "speaker_id": "speaker1",
              "ssml_gender": "Male",
              "pitch": text_to_speech._DEFAULT_SSML_MALE_PITCH,
              "speed": text_to_speech._DEFAULT_SPEED,
              "volume_gain_db": text_to_speech._DEFAULT_VOLUME_GAIN_DB,
          },
      ),
      (
          "ElevenLabs",
          True,
          "Female",
          {
              "text": "Hello there!",
              "start": 0.0,
              "end": 1.5,
              "speaker_id": "speaker1",
              "ssml_gender": "Female",
              "stability": text_to_speech._DEFAULT_STABILITY,
              "similarity_boost": text_to_speech._DEFAULT_SIMILARITY_BOOST,
              "style": text_to_speech._DEFAULT_STYLE,
              "use_speaker_boost": text_to_speech._DEFAULT_USE_SPEAKER_BOOST,
          },
      ),
  )
  def test_add_text_to_speech_properties(
      self, use_elevenlabs, ssml_gender, expected_metadata
  ):
    utterance_metadata = {
        "text": "Hello there!",
        "start": 0.0,
        "end": 1.5,
        "speaker_id": "speaker1",
        "ssml_gender": ssml_gender,
    }
    result = text_to_speech.add_text_to_speech_properties(
        utterance_metadata=utterance_metadata, use_elevenlabs=use_elevenlabs
    )
    self.assertEqual(result, expected_metadata)


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
      elevenlabs_clone_voices,
      utterance_metadata,
      assigned_voices,
      expected_output,
  ):
    actual_output = text_to_speech.update_utterance_metadata(
        utterance_metadata=utterance_metadata,
        assigned_voices=assigned_voices,
        use_elevenlabs=use_elevenlabs,
        elevenlabs_clone_voices=elevenlabs_clone_voices,
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
    elevenlabs_clone_voices = True
    with self.assertRaises(ValueError):
      text_to_speech.update_utterance_metadata(
          utterance_metadata=utterance_metadata,
          assigned_voices=assigned_voices,
          use_elevenlabs=use_elevenlabs,
          elevenlabs_clone_voices=elevenlabs_clone_voices,
      )


class TestConvertTextToSpeech(absltest.TestCase):

  def test_convert_text_to_speech(self):
    mock_client = MagicMock(spec=texttospeech.TextToSpeechClient)
    sample_rate = 44100
    t = np.linspace(0.0, 1.0, sample_rate, endpoint=False)
    amplitude = 4096
    data = amplitude * np.sin(2 * np.pi * 440 * t)
    data = data.astype(np.int16)
    buffer = io.BytesIO()
    scipy.io.wavfile.write(buffer, sample_rate, data)
    mock_response = texttospeech.SynthesizeSpeechResponse(
        audio_content=buffer.getvalue()
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


class TestCalculateTargetUtteranceSpeed(absltest.TestCase):

  def test_calculate_target_utterance_speed(self):
    with tempfile.TemporaryDirectory() as tempdir:
      dubbed_audio_mock = AudioSegment.silent(duration=90000)
      dubbed_file_path = os.path.join(tempdir, "dubbed.mp3")
      dubbed_audio_mock.export(dubbed_file_path, format="mp3")
      result = text_to_speech.calculate_target_utterance_speed(
          reference_length=60.0, dubbed_file=dubbed_file_path
      )
      expected_result = 90000 / 60000
      self.assertEqual(result, expected_result)


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


class TestElevenlabsCloneVoices(absltest.TestCase):

  def test_clone_voices_success(self):
    mock_client = MagicMock(spec=ElevenLabs)
    mock_voice = MagicMock(spec=Voice)
    mock_client.clone.return_value = mock_voice
    speaker_to_paths_mapping = {
        "speaker1": ["path/to/audio1.wav", "path/to/audio2.wav"],
        "speaker2": ["path/to/audio3.wav"],
    }
    result = text_to_speech.elevenlabs_run_clone_voices(
        client=mock_client, speaker_to_paths_mapping=speaker_to_paths_mapping
    )
    self.assertEqual(result, {"speaker1": mock_voice, "speaker2": mock_voice})
    mock_client.clone.assert_called()


class TestDubAllUtterances(parameterized.TestCase):

  @parameterized.named_parameters(
      ("not_for_dubbing", False, "original_path", False, False),
      ("for_dubbing_elevenlabs", True, "dubbed_path.mp3", True, False),
      ("for_dubbing_google", True, "dubbed_path.mp3", False, False),
      ("for_dubbing_google_adjust_speed", True, "dubbed_path.mp3", False, True),
  )
  @patch("ariel.text_to_speech.convert_text_to_speech")
  @patch("ariel.text_to_speech.elevenlabs_convert_text_to_speech")
  @patch("ariel.text_to_speech.adjust_audio_speed")
  @patch("ariel.text_to_speech.calculate_target_utterance_speed")
  def test_dubbing_logic(
      self,
      for_dubbing_value,
      expected_dubbed_path,
      use_elevenlabs,
      adjust_speed,
      mock_calculate_target_utterance_speed,
      mock_adjust_audio_speed,
      mock_elevenlabs_convert_text_to_speech,
      mock_convert_text_to_speech,
  ):
    utterance_metadata = [{
        "start": 0.0,
        "end": 1.0,
        "for_dubbing": for_dubbing_value,
        "path": "original_path",
        "translated_text": "translated text",
        "stability": 0.5,
        "similarity_boost": 0.5,
        "style": "General",
        "use_speaker_boost": False,
        "assigned_voice": "test_voice",
        "pitch": 1.0,
        "speed": 1.0,
        "volume_gain_db": 1.0,
        "stability": 1.0,
        "similarity_boost": 1.0,
        "style": 1.0,
        "use_speaker_boost": True,
    }]
    client = MagicMock()
    preprocessing_output = dict(
        video_file="test_output/test_video.mp4",
        audio_file="test_output/test_audio.mp3",
        audio_vocals_file="test_output/test_audio_vocals.mp3",
        audio_background_file="test_output/test_audio_background.mp3",
    )
    tts = text_to_speech.TextToSpeech(
        client=client,
        utterance_metadata=utterance_metadata,
        output_directory="test_output",
        target_language="en-US",
        preprocessing_output=preprocessing_output,
        use_elevenlabs=use_elevenlabs,
        adjust_speed=adjust_speed,
    )
    mock_convert_text_to_speech.return_value = "dubbed_path.mp3"
    mock_elevenlabs_convert_text_to_speech.return_value = "dubbed_path.mp3"
    mock_calculate_target_utterance_speed.return_value = 1.0

    result = tts.dub_all_utterances()

    self.assertEqual(result[0].get("dubbed_path"), expected_dubbed_path)

  @patch("ariel.text_to_speech.audio_processing.run_cut_and_save_audio")
  @patch("ariel.text_to_speech.create_speaker_to_paths_mapping")
  @patch("ariel.text_to_speech.elevenlabs_run_clone_voices")
  def test_voice_cloning(
      self,
      mock_elevenlabs_run_clone_voices,
      mock_create_speaker_to_paths_mapping,
      mock_run_cut_and_save_audio,
  ):
    utterance_metadata = [{"for_dubbing": True, "speaker_id": "spk_1"}]
    client = MagicMock()
    preprocessing_output = dict(
        video_file="test_output/test_video.mp4",
        audio_file="test_output/test_audio.mp3",
        audio_vocals_file="test_output/test_audio_vocals.mp3",
        audio_background_file="test_output/test_audio_background.mp3",
    )
    tts = text_to_speech.TextToSpeech(
        client=client,
        utterance_metadata=utterance_metadata,
        output_directory="test_output",
        target_language="en-US",
        preprocessing_output=preprocessing_output,
        use_elevenlabs=True,
        elevenlabs_clone_voices=True,
    )

    tts.dub_all_utterances()

    mock_run_cut_and_save_audio.assert_called_once()
    mock_create_speaker_to_paths_mapping.assert_called_once()
    mock_elevenlabs_run_clone_voices.assert_called_once()

  def test_value_error_when_cloning_without_elevenlabs(self):
    utterance_metadata = [{"for_dubbing": True, "speaker_id": "spk_1"}]
    client = MagicMock()
    preprocessing_output = dict(
        video_file="test_output/test_video.mp4",
        audio_file="test_output/test_audio.mp3",
        audio_vocals_file="test_output/test_audio_vocals.mp3",
        audio_background_file="test_output/test_audio_background.mp3",
    )
    tts = text_to_speech.TextToSpeech(
        client=client,
        utterance_metadata=utterance_metadata,
        output_directory="test_output",
        target_language="en-US",
        preprocessing_output=preprocessing_output,
        use_elevenlabs=False,
        elevenlabs_clone_voices=True,
    )
    with self.assertRaisesRegex(
        ValueError, "Voice cloning requires using ElevenLabs API."
    ):
      tts.dub_all_utterances()


if __name__ == "__main__":
  absltest.main()

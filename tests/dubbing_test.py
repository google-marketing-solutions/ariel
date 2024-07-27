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

"""Tests for utility functions in dubbing.py."""

import tempfile
from absl.testing import absltest
from absl.testing import parameterized
from ariel import dubbing
import tensorflow as tf


class TestIsVideo(parameterized.TestCase):

  @parameterized.named_parameters(
      ("valid_mp4", "my_video.mp4", True),
      ("wav_audio", "my_song.wav", False),
      ("mp3_audio", "another_song.mp3", False),
      ("flac_audio", "high_quality.flac", False),
      ("case_insensitive_mp4", "my_video.MP4", True),
  )
  def test_is_video(self, input_file, expected_result):
    self.assertEqual(dubbing.is_video(input_file=input_file), expected_result)

  @parameterized.named_parameters(
      ("unsupported_format_txt", "document.txt"),
      ("unsupported_format_jpg", "image.jpg"),
      ("unsupported_format_empty", ""),
  )
  def test_unsupported_format_raises_value_error(self, input_file):
    with self.assertRaisesRegex(ValueError, "Unsupported file format"):
      dubbing.is_video(input_file=input_file)


class TestReadSystemSettings(absltest.TestCase):

  def test_txt_file_success(self):
    """Test reading a .txt file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt") as temp_file:
      temp_file.write("This is a test file.")
      temp_file.flush()

      result = dubbing.read_system_settings(temp_file.name)
      self.assertEqual(result, "This is a test file.")

  def test_string_input(self):
    """Test returning a plain string."""
    result = dubbing.read_system_settings("Hello, world!")
    self.assertEqual(result, "Hello, world!")

  def test_unsupported_extension(self):
    """Test raising ValueError for unsupported extensions."""
    with self.assertRaisesRegex(ValueError, "Unsupported file type"):
      dubbing.read_system_settings("invalid.docx")

  def test_nonexistent_file(self):
    """Test raising ValueError for missing files."""
    with self.assertRaisesRegex(
        ValueError,
        "You specified a .txt file that's not part of the Ariel package.",
    ):
      dubbing.read_system_settings("nonexistent.txt")


class TestAssembleUtteranceMetadata(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "Basic Case",
          [
              {"text": "Hello there!", "start": 0.0, "end": 2.5},
              {"text": "How are you?", "start": 3.0, "end": 5.2},
          ],
          "John Doe",
          False,
          {"pitch": -3.0, "speed": 1.2, "volume_gain_db": 10.0},
          None,
          [
              {
                  "text": "Hello there!",
                  "start": 0.0,
                  "end": 2.5,
                  "for_dubbing": True,
                  "assigned_voice": "John Doe",
                  "pitch": -3.0,
                  "speed": 1.2,
                  "volume_gain_db": 10.0,
              },
              {
                  "text": "How are you?",
                  "start": 3.0,
                  "end": 5.2,
                  "for_dubbing": True,
                  "assigned_voice": "John Doe",
                  "pitch": -3.0,
                  "speed": 1.2,
                  "volume_gain_db": 10.0,
              },
          ],
      ),
      (
          "ElevenLabs Case",
          [
              {"text": "This is for ElevenLabs", "start": 0.0, "end": 2.0},
          ],
          "David",
          True,
          None,
          {
              "stability": 0.6,
              "similarity_boost": 0.8,
              "style": 0.2,
              "use_speaker_boost": False,
          },
          [{
              "text": "This is for ElevenLabs",
              "start": 0.0,
              "end": 2.0,
              "for_dubbing": True,
              "assigned_voice": "David",
              "stability": 0.6,
              "similarity_boost": 0.8,
              "style": 0.2,
              "use_speaker_boost": False,
          }],
      ),
  )
  def test_assemble_utterance_metadata(
      self,
      script_with_timestamps,
      assigned_voice,
      use_elevenlabs,
      google_text_to_speech_parameters,
      elevenlabs_text_to_speech_parameters,
      expected_output,
  ):
    result = dubbing.assemble_utterance_metadata_for_dubbing_from_script(
        script_with_timestamps=script_with_timestamps,
        assigned_voice=assigned_voice,
        use_elevenlabs=use_elevenlabs,
        google_text_to_speech_parameters=google_text_to_speech_parameters,
        elevenlabs_text_to_speech_parameters=elevenlabs_text_to_speech_parameters,
    )
    self.assertEqual(result, expected_output)

  def test_missing_key_raises_key_error(self):
    with self.assertRaises(KeyError):
      dubbing.assemble_utterance_metadata_for_dubbing_from_script(
          script_with_timestamps=[
              {"text": "This is incomplete", "start": 1.0},
          ],
          assigned_voice="Jane Smith",
      )


if __name__ == "__main__":
  absltest.main()

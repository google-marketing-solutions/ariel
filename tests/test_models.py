"""Tests for the models module."""

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

import unittest
from models import Speaker, Utterance, Video, RegenerateRequest, RegenerateResponse


class ModelsTest(unittest.TestCase):
  """Test cases for models module."""

  def test_speaker_model(self):
    """Tests Speaker model creation."""
    speaker = Speaker(speaker_id="s1", voice="voice1")
    self.assertEqual(speaker.speaker_id, "s1")
    self.assertEqual(speaker.voice, "voice1")

  def test_utterance_model(self):
    """Tests Utterance model creation and defaults."""
    speaker = Speaker(speaker_id="s1", voice="voice1")
    utterance = Utterance(
        id="u1",
        original_text="Hello",
        translated_text="Hola",
        instructions="Translate to Spanish",
        speaker=speaker,
        original_start_time=0.0,
        original_end_time=1.0,
        translated_start_time=0.0,
        translated_end_time=1.0,
        removed=False
    )

    self.assertEqual(utterance.id, "u1")
    self.assertEqual(utterance.muted, False) # Default value
    self.assertEqual(utterance.audio_url, "") # Default value

  def test_video_model(self):
    """Tests Video model creation and defaults."""
    speaker = Speaker(speaker_id="s1", voice="voice1")
    utterance = Utterance(
        id="u1",
        original_text="Hello",
        translated_text="Hola",
        instructions="Translate to Spanish",
        speaker=speaker,
        original_start_time=0.0,
        original_end_time=1.0,
        translated_start_time=0.0,
        translated_end_time=1.0,
        removed=False
    )
    video = Video(
        video_id="v1",
        original_language="en",
        translate_language="es",
        speakers=[speaker],
        utterances=[utterance]
    )

    self.assertEqual(video.video_id, "v1")
    self.assertEqual(video.prompt_enhancements, "") # Default
    self.assertEqual(video.model_name, "") # Default
    self.assertEqual(video.tts_model_name, "") # Default
    self.assertEqual(len(video.speakers), 1)
    self.assertEqual(len(video.utterances), 1)

  def test_regenerate_request(self):
    """Tests RegenerateRequest model."""
    speaker = Speaker(speaker_id="s1", voice="voice1")
    utterance = Utterance(
        id="u1",
        original_text="Hello",
        translated_text="Hola",
        instructions="",
        speaker=speaker,
        original_start_time=0.0,
        original_end_time=1.0,
        translated_start_time=0.0,
        translated_end_time=1.0,
        removed=False
    )
    video = Video(
        video_id="v1",
        original_language="en",
        translate_language="es",
        speakers=[speaker],
        utterances=[utterance]
    )

    req = RegenerateRequest(video=video, utterance=0)
    self.assertEqual(req.utterance, 0)
    self.assertEqual(req.instructions, "") # Default value

  def test_regenerate_response(self):
    """Tests RegenerateResponse model."""
    resp = RegenerateResponse(
        translated_text="Hola",
        audio_url="path/to/audio.wav",
        duration=1.5
    )
    self.assertEqual(resp.translated_text, "Hola")
    self.assertEqual(resp.duration, 1.5)


if __name__ == "__main__":
  unittest.main()

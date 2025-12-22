"""Tests for generate_audio."""

# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import io
import os
import shutil
import tempfile
from typing import override
import unittest
import unittest.mock
import wave

from generate_audio import _process_audio_part
from generate_audio import generate_audio
from generate_audio import shorten_audio
from generate_audio import strip_silence
from google.api_core import exceptions as api_exceptions
import numpy as np
import soundfile as sf

# Import TestClient and our FastAPI app
from fastapi.testclient import TestClient
from main import app
from main import mount_point
from models import Speaker, Utterance, Video


class TestGenerateAudio(unittest.TestCase):
  """Tests for generating audio."""

  temp_dir: str = ""
  output_path: str = ""
  client: TestClient
  video_id: str = "test_video_id"

  @override
  def setUp(self):
    super().setUp()
    self.temp_dir = tempfile.mkdtemp()
    self.output_path = os.path.join(self.temp_dir, "test_audio.wav")

    # Create a TestClient for our FastAPI app
    self.client = TestClient(app)

    # Ensure the mount_point exists for the test
    os.makedirs(os.path.join(mount_point, self.video_id), exist_ok=True)


  @override
  def tearDown(self):
    super().tearDown()
    shutil.rmtree(self.temp_dir)
    # Clean up the test video directory
    test_video_dir = os.path.join(mount_point, self.video_id)
    if os.path.exists(test_video_dir):
        shutil.rmtree(test_video_dir)


  def create_in_memory_wav(
      self,
      duration_seconds: int,
      sample_rate: int,
      bit_depth: int,
      num_channels: int,
  ) -> bytes:
    """Helper function to create a test audio file.

    Args:
      duration_seconds: the duration of the file.
      sample_rate: the sample rate to use.
      bit_depth: the bit_depth to use.
      num_channels: the number of channels to generate.

    Returns:
      the bytes of the generated file.
    """
    bytes_per_sample = bit_depth // 8
    num_samples = int(duration_seconds * sample_rate)
    pcm_data = b"\x00" * (num_samples * bytes_per_sample * num_channels)

    with io.BytesIO() as wav_buffer:
      with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(bytes_per_sample)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
      return wav_buffer.getvalue()

  def test_process_audio_part(self):
    """Tests _process_audio saves the file correctly and returns the correct duration."""
    # Create a 3 second clip
    duration_seconds = 3
    sample_rate = 24000
    bit_depth = 16  # 16-bit audio
    num_channels = 1
    bytes_per_sample = bit_depth // 8

    wav_data = self.create_in_memory_wav(
        duration_seconds, sample_rate, bit_depth, num_channels
    )

    returned_duration = _process_audio_part(wav_data, self.output_path)
    self.assertAlmostEqual(returned_duration, duration_seconds, places=2)

    self.assertTrue(os.path.exists(self.output_path))
    with wave.open(self.output_path, "rb") as wf:
      self.assertEqual(wf.getnchannels(), num_channels)
      self.assertEqual(wf.getsampwidth(), bytes_per_sample)
      self.assertEqual(wf.getframerate(), sample_rate)

      frames = wf.getnframes()
      file_duration = frames / float(wf.getframerate())
      self.assertAlmostEqual(file_duration, duration_seconds, places=2)

  def test_process_audio_part_empty_data(self):
    wav_data = self.create_in_memory_wav(0, 24000, 16, 1)
    duration = _process_audio_part(wav_data, self.output_path)
    self.assertEqual(duration, 0.0)

    self.assertTrue(os.path.exists(self.output_path))
    with wave.open(self.output_path, "rb") as wf:
      self.assertEqual(wf.getnframes(), 0)

  def test_strip_silence(self):
    """Test strip_silence removes the correct part of the file."""
    sample_rate = 24000
    # Create a 3 second clip with 1s silence, 1s tone, 1s silence
    silence = np.zeros(sample_rate)
    frequency = 440
    t = np.linspace(0.0, 1.0, sample_rate)
    amplitude = np.iinfo(np.int16).max * 0.5
    tone = (amplitude * np.sin(2.0 * np.pi * frequency * t)).astype(np.int16)
    audio_data = np.concatenate((silence, tone, silence)).astype(np.int16)

    sf.write(self.output_path, audio_data, sample_rate)

    new_duration = strip_silence(self.output_path)
    self.assertAlmostEqual(new_duration, 1.0, delta=0.1)

    y, sr = sf.read(self.output_path)
    self.assertAlmostEqual(len(y) / sr, 1.0, delta=0.1)

  def test_strip_silence_no_silence(self):
    """Tests strip_silence doesn't remove anything where there is no silence."""
    sample_rate = 24000
    # Create a 1 second clip with a tone
    frequency = 440
    t = np.linspace(0.0, 1.0, sample_rate)
    amplitude = np.iinfo(np.int16).max * 0.5
    tone = (amplitude * np.sin(2.0 * np.pi * frequency * t)).astype(np.int16)

    sf.write(self.output_path, tone, sample_rate)

    new_duration = strip_silence(self.output_path)
    self.assertAlmostEqual(new_duration, 1.0, delta=0.1)

    y, sr = sf.read(self.output_path)
    self.assertAlmostEqual(len(y) / sr, 1.0, delta=0.1)

  def test_strip_silence_all_silence(self):
    sample_rate = 24000
    # Create a 3 second silent clip
    silence = np.zeros(sample_rate * 3, dtype=np.int16)
    sf.write(self.output_path, silence, sample_rate)

    new_duration = strip_silence(self.output_path)
    self.assertEqual(new_duration, 0.0)

    y, _ = sf.read(self.output_path)
    self.assertEqual(len(y), 0)

  def test_shorten_audio(self):
    """Tests shorten_audio creates a file of the correct length."""
    sample_rate = 24000
    original_duration = 3.0
    target_duration = 1.5

    # Create a 3-second silent clip
    silence = np.zeros(int(sample_rate * original_duration), dtype=np.int16)
    sf.write(self.output_path, silence, sample_rate)

    new_duration = shorten_audio(
        self.output_path, original_duration, target_duration
    )
    self.assertAlmostEqual(new_duration, target_duration, delta=0.05)

    y, sr = sf.read(self.output_path)
    self.assertAlmostEqual(len(y) / sr, target_duration, delta=0.05)

  def test_shorten_audio_zero_length(self):
    """Tests shorten_audio doesn't do anything with empty files."""
    sample_rate = 24000
    original_duration = 0.0
    target_duration = 1.5

    # Create an empty clip
    empty_audio = np.array([], dtype=np.int16)
    sf.write(self.output_path, empty_audio, sample_rate)

    new_duration = shorten_audio(
        self.output_path, original_duration, target_duration
    )
    self.assertEqual(new_duration, 0.0)

    y, _ = sf.read(self.output_path)
    self.assertEqual(len(y), 0)

  def test_shorten_audio_stretch(self):
    """Tests shorten_audio will stretch a file if given a longer target."""
    sample_rate = 24000
    original_duration = 1.5
    target_duration = 3.0

    # Create a 1.5-second silent clip
    silence = np.zeros(int(sample_rate * original_duration), dtype=np.int16)
    sf.write(self.output_path, silence, sample_rate)

    new_duration = shorten_audio(
        self.output_path, original_duration, target_duration
    )
    self.assertAlmostEqual(new_duration, target_duration, delta=0.05)

    y, sr = sf.read(self.output_path)
    self.assertAlmostEqual(len(y) / sr, target_duration, delta=0.05)

  @unittest.mock.patch("generate_audio.texttospeech.TextToSpeechClient")
  def test_generate_audio_full_run(
      self, mock_texttospeech_client: unittest.mock.Mock
  ):
    """End-to-end test of generate_audio."""
    mock_tts_client = mock_texttospeech_client.return_value
    mock_response = unittest.mock.Mock()
    sample_rate = 24000
    duration_seconds = 3

    # Create a 3-second wav file in memory
    wav_data = self.create_in_memory_wav(duration_seconds, sample_rate, 16, 1)

    mock_response.audio_content = wav_data
    mock_tts_client.synthesize_speech.return_value = mock_response

    duration = generate_audio(
        text="Hello, world!",
        prompt="A friendly voice.",
        language="en-US",
        voice_name="echo",
        output_path=self.output_path,
    )

    mock_tts_client.synthesize_speech.assert_called_once()
    self.assertAlmostEqual(duration, duration_seconds, delta=0.1)
    y, sr = sf.read(self.output_path)
    self.assertAlmostEqual(len(y) / sr, duration_seconds, delta=0.1)

  @unittest.mock.patch("generate_audio.texttospeech.TextToSpeechClient")
  def test_generate_audio_with_model_name(self, mock_texttospeech_client):
    """Tests that generate_audio uses the correct model."""
    mock_tts_client = mock_texttospeech_client.return_value
    mock_response = unittest.mock.Mock()
    sample_rate = 24000
    duration_seconds = 3

    # Create a 3-second wav file in memory
    wav_data = self.create_in_memory_wav(duration_seconds, sample_rate, 16, 1)

    mock_response.audio_content = wav_data
    mock_tts_client.synthesize_speech.return_value = mock_response

    model_name = "gemini-2.5-flash-tts"
    duration = generate_audio(
        text="Hello, world!",
        prompt="A friendly voice.",
        language="en-US",
        voice_name="echo",
        output_path=self.output_path,
        model_name=model_name,
    )

    mock_tts_client.synthesize_speech.assert_called_once()
    call_args = mock_tts_client.synthesize_speech.call_args
    self.assertEqual(call_args.kwargs["request"].voice.model_name, model_name)
    self.assertAlmostEqual(duration, duration_seconds, delta=0.1)

  @unittest.mock.patch("generate_audio._process_audio_part")
  @unittest.mock.patch("generate_audio._call_tts")
  def test_generate_audio_io_error(
      self,
      mock_call_tts: unittest.mock.Mock,
      mock_process_audio_part: unittest.mock.Mock,
  ):
    """Tests that generate_audio handles an IOError."""
    mock_response = unittest.mock.Mock()
    mock_response.audio_content = b"some_audio_content"
    mock_call_tts.return_value = mock_response
    mock_process_audio_part.side_effect = IOError("File write error")

    with self.assertLogs(level="ERROR") as cm:
      duration = generate_audio(
          text="Test text.",
          prompt="Test prompt.",
          language="en-US",
          voice_name="test_voice",
          output_path=self.output_path,
      )

      self.assertEqual(mock_call_tts.call_count, 1)
      self.assertEqual(duration, 0.0)
      self.assertIn(
          "An error occurred while processing the generated audio: File write"
          " error",
          cm.output[0],
      )

  @unittest.mock.patch("generate_audio._call_tts")
  def test_generate_audio_api_exception(
      self, mock_call_tts: unittest.mock.Mock
  ):
    """Tests that generate_audio handles a Gemini TTS API exception."""
    mock_call_tts.side_effect = api_exceptions.GoogleAPICallError("API error")

    with self.assertLogs(level="ERROR") as cm:
      duration = generate_audio(
          text="Test text.",
          prompt="A test prompt.",
          language="en-US",
          voice_name="test_voice",
          output_path=self.output_path,
      )

      self.assertEqual(mock_call_tts.call_count, 1)
      self.assertEqual(duration, 0.0)
      self.assertFalse(os.path.exists(self.output_path))
      self.assertIn(
          "An error occurred calling Gemini-TTS: None API error", cm.output[0]
      )

  @unittest.mock.patch("generate_audio._call_tts")
  def test_generate_audio_empty_audio_content(
      self, mock_call_tts: unittest.mock.Mock
  ):
    """Tests that generate_audio handles empty audio_content."""
    mock_response = unittest.mock.Mock()
    mock_response.audio_content = b""
    mock_call_tts.return_value = mock_response

    # Ensure logging.error is called
    with self.assertLogs(level="ERROR") as cm:
      duration = generate_audio(
          text="Test text.",
          prompt="Test prompt.",
          language="en-US",
          voice_name="test_voice",
          output_path=self.output_path,
      )

      # _call_tts should be called 3 times due to retry logic
      self.assertEqual(mock_call_tts.call_count, 3)
      self.assertEqual(duration, 0.0)
      self.assertFalse(os.path.exists(self.output_path))
      self.assertIn(
          "Text-to-speech API returned empty audio content.", cm.output[0]
      )

  @unittest.mock.patch("main._get_dubbed_vocals_path")
  def test_generate_audio_endpoint(self, mock_get_dubbed_vocals_path: unittest.mock.Mock):
    """Tests the /generate_audio endpoint."""
    mock_get_dubbed_vocals_path.return_value = os.path.join(
        mount_point, self.video_id, "dubbed_vocals.wav"
    )

    # Create a dummy audio file for the mocked path
    os.makedirs(os.path.dirname(mock_get_dubbed_vocals_path.return_value), exist_ok=True)
    with open(mock_get_dubbed_vocals_path.return_value, "w") as f:
        f.write("dummy audio content")

    # Create a dummy Video object
    dummy_video = Video(
        video_id=self.video_id,
        original_language="en",
        translate_language="es",
        prompt_enhancements="test prompt",
        speakers=[Speaker(speaker_id="speaker1", voice="voice1")],
        utterances=[Utterance(
            id="utterance1",
            original_text="Hello",
            translated_text="Hola",
            instructions="",
            speaker=Speaker(speaker_id="speaker1", voice="voice1"),
            original_start_time=0.0,
            original_end_time=1.0,
            translated_start_time=0.0,
            translated_end_time=1.0,
            removed=False,
            audio_url="/path/to/audio1.wav"
        )],
        model_name="flash",
        tts_model_name="flash-tts"
    )

    response = self.client.post("/generate_audio", json=dummy_video.model_dump())

    self.assertEqual(response.status_code, 200)
    self.assertIn("audio_url", response.json())
    self.assertIn(f"{mount_point}/{self.video_id}/dubbed_vocals.wav", response.json()["audio_url"])
    mock_get_dubbed_vocals_path.assert_called_once_with(dummy_video, os.path.join(mount_point, self.video_id))


if __name__ == "__main__":
  unittest.main()

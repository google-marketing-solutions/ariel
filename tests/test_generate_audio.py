from typing import override
import unittest
from unittest.mock import Mock, patch
import os
import tempfile
import wave
import shutil
import io
import numpy as np
import soundfile as sf

from generate_audio import (
  _process_audio_part,
  strip_silence,
  shorten_audio,
  generate_audio,
)


class TestGenerateAudio(unittest.TestCase):
  @override
  def setUp(self):
    self.temp_dir = tempfile.mkdtemp()
    self.output_path = os.path.join(self.temp_dir, "test_audio.wav")

  @override
  def tearDown(self):
    shutil.rmtree(self.temp_dir)

  def create_in_memory_wav(
    self,
    duration_seconds: int,
    sample_rate: int,
    bit_depth: int,
    num_channels: int,
  ) -> bytes:
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

    y, sr = sf.read(self.output_path)
    self.assertEqual(len(y), 0)

  def test_shorten_audio(self):
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

    y, sr = sf.read(self.output_path)
    self.assertEqual(len(y), 0)

  def test_shorten_audio_stretch(self):
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

  @patch("generate_audio.texttospeech.TextToSpeechClient")
  def test_generate_audio_full_run(self, MockTextToSpeechClient):
    mock_tts_client = MockTextToSpeechClient.return_value
    mock_response = Mock()
    sample_rate = 24000
    duration_seconds = 3.0

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

  @patch("generate_audio.logging.error")
  @patch("generate_audio.texttospeech.TextToSpeechClient")
  def test_generate_audio_api_error(
    self, MockTextToSpeechClient, mock_logging_error
  ):
    mock_tts_client = MockTextToSpeechClient.return_value
    mock_response = Mock()
    mock_response.audio_content = b""  # Empty audio content
    mock_tts_client.synthesize_speech.return_value = mock_response

    duration = generate_audio(
      text="Hello, world!",
      prompt="A friendly voice.",
      language="en-US",
      voice_name="echo",
      output_path=self.output_path,
    )

    self.assertEqual(duration, 0.0)
    self.assertEqual(mock_tts_client.synthesize_speech.call_count, 3)
    mock_logging_error.assert_called_once_with(
      "An error occurred during audio generation: "
    )


if __name__ == "__main__":
  unittest.main()

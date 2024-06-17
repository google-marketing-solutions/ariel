"""Tests for utility functions in speech_to_text.py."""

from collections import namedtuple
import tempfile
from unittest.mock import MagicMock
from absl.testing import absltest
from ariel import speech_to_text
from faster_whisper import WhisperModel
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np


class TranscribeTests(absltest.TestCase):

  def test_transcribe(self):
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      silence_duration = 5
      fps = 44100
      silence = AudioArrayClip(
          np.zeros((int(fps * silence_duration), 2), dtype=np.int16),
          fps=fps,
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
      fps = 44100
      silence = AudioArrayClip(
          np.zeros((int(fps * silence_duration), 2), dtype=np.int16),
          fps=fps,
      )
      silence.write_audiofile(temporary_file.name)
      mock_model = MagicMock(spec=WhisperModel)
      Segment = namedtuple("Segment", ["text"])
      mock_model.transcribe.return_value = [Segment(text="Test.")], None
      transcribed_audio_chunks = speech_to_text.transcribe_audio_chunks(
          chunk_data_list=[dict(path=temporary_file.name, start=0.0, end=5.0)],
          advertiser_name="Advertiser Name",
          original_language="en",
          model=mock_model,
      )
      self.assertEqual(
          transcribed_audio_chunks,
          [dict(path=temporary_file.name, start=0.0, end=5.0, text="Test.")],
      )


if __name__ == "__main__":
  absltest.main()

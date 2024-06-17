"""Tests for utility functions in audio_processing.py."""

import os
import subprocess
import tempfile
from unittest.mock import MagicMock
from unittest.mock import patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import audio_processing
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np
from pyannote.audio import Pipeline


class BuildDemucsCommandTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "basic",
          {},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems audio.mp3"
          ),
      ),
      (
          "flac",
          {"flac": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --flac"
              " audio.mp3"
          ),
      ),
      (
          "mp3",
          {"mp3": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --mp3"
              " --mp3-bitrate 320 --mp3-preset 2 audio.mp3"
          ),
      ),
      (
          "int24",
          {"int24": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --int24"
              " audio.mp3"
          ),
      ),
      (
          "float32",
          {"float32": True},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --float32"
              " audio.mp3"
          ),
      ),
      (
          "segment",
          {"segment": 60},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --segment"
              " 60 audio.mp3"
          ),
      ),
      (
          "no_split",
          {"split": False},
          (
              "python3 -m demucs.separate -o test --device cpu --shifts 10"
              " --overlap 0.25 --clip_mode rescale -j 0 --two-stems --no-split"
              " audio.mp3"
          ),
      ),
  )
  def test_build_demucs_command(self, kwargs, expected_command):
    self.assertEqual(
        audio_processing.build_demucs_command(
            audio_file="audio.mp3",
            output_directory="test",
            device="cpu",
            **kwargs,
        ),
        expected_command,
    )

  def test_raise_error_int24_float32(self):
    with self.assertRaisesRegex(
        ValueError, "Cannot set both int24 and float32 to True."
    ):
      audio_processing.build_demucs_command(
          audio_file="audio.mp3",
          output_directory="test",
          device="cpu",
          int24=True,
          float32=True,
      )


class TestExecuteDemcusCommand(absltest.TestCase):

  @patch("subprocess.run")
  def test_execute_command_success(self, mock_run):
    mock_run.return_value.stdout = "Command executed successfully"
    mock_run.return_value.stderr = ""
    mock_run.return_value.returncode = 0
    audio_processing.execute_demcus_command(
        command="echo 'Command executed successfully'"
    )
    mock_run.assert_called_once_with(
        "echo 'Command executed successfully'",
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    )

  @patch("subprocess.run")
  def test_execute_command_failure(self, mock_run):
    mock_run.side_effect = subprocess.CalledProcessError(
        1, "command", "Error message"
    )
    audio_processing.execute_demcus_command(command="invalid_command")
    mock_run.assert_called_once_with(
        "invalid_command",
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    )


class CreatePyannoteTimestampsTest(absltest.TestCase):

  def test_create_timestamps_with_silence(self):
    with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:
      silence_duration = 10
      fps = 44100
      silence = AudioArrayClip(
          np.zeros((int(fps * silence_duration), 2), dtype=np.int16),
          fps=fps,
      )
      silence.write_audiofile(temp_file.name)
      mock_pipeline = MagicMock(spec=Pipeline)
      mock_pipeline.return_value.itertracks.return_value = [
          (MagicMock(start=0.0, end=silence_duration), None, None)
      ]
      timestamps = audio_processing.create_pyannote_timestamps(
          vocals_filepath=temp_file.name,
          number_of_speakers=0,
          pipeline=mock_pipeline,
      )
      self.assertEqual(timestamps, [{"start": 0.0, "end": 10}])


class TestCutAndSaveAudio(absltest.TestCase):

  def test_cut_and_save_audio(self):
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      silence_duration = 10
      silence = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence.write_audiofile(temporary_file.name)
      input_data = [{"start": 0.0, "end": 5.0}]
      with tempfile.TemporaryDirectory() as output_folder:
        results = audio_processing.cut_and_save_audio(
            input_data=input_data,
            music_file_path=temporary_file.name,
            output_folder=output_folder,
        )
        expected_file = os.path.join(output_folder, "chunk_0.0_5.0.mp3")
        expected_result = {
            "path": os.path.join(output_folder, "chunk_0.0_5.0.mp3"),
            "start": 0.0,
            "end": 5.0,
        }
        self.assertTrue(
            os.path.exists(expected_file) and results == [expected_result],
            f"File not found or dictionary not as expected: {expected_file}",
        )


if __name__ == "__main__":
  absltest.main()

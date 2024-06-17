"""Tests for utility functions in audio_processing.py."""

import subprocess
from unittest.mock import patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import audio_processing


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
        "echo 'Command executed successfully'"
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
    audio_processing.execute_demcus_command("invalid_command")
    mock_run.assert_called_once_with(
        "invalid_command",
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    )


if __name__ == "__main__":
  absltest.main()
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

"""Tests for utility functions in audio_processing.py."""

import os
import subprocess
import tempfile
import unittest.mock as mock
from unittest.mock import MagicMock
from unittest.mock import patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import audio_processing
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np
from pyannote.audio import Pipeline
from pydub import AudioSegment


class BuildDemucsCommandTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "basic",
          {},
          (
              "python -m demucs.separate -o 'test/audio_processing' --device"
              " cpu --shifts 10 --overlap 0.25 -j 0 --two-stems vocals --mp3"
              " --mp3-bitrate 320 --mp3-preset 2 'audio.mp3'"
          ),
      ),
      (
          "flac",
          {"flac": True, "mp3": False},
          (
              "python -m demucs.separate -o 'test/audio_processing' --device"
              " cpu --shifts 10 --overlap 0.25 -j 0 --two-stems vocals --flac"
              " 'audio.mp3'"
          ),
      ),
      (
          "int24",
          {"int24": True, "mp3": False},
          (
              "python -m demucs.separate -o 'test/audio_processing' --device"
              " cpu --shifts 10 --overlap 0.25 -j 0 --two-stems vocals --int24"
              " 'audio.mp3'"
          ),
      ),
      (
          "float32",
          {"float32": True, "mp3": False},
          (
              "python -m demucs.separate -o 'test/audio_processing' --device"
              " cpu --shifts 10 --overlap 0.25 -j 0 --two-stems vocals"
              " --float32 'audio.mp3'"
          ),
      ),
      (
          "segment",
          {"segment": 60},
          (
              "python -m demucs.separate -o 'test/audio_processing' --device"
              " cpu --shifts 10 --overlap 0.25 -j 0 --two-stems vocals"
              " --segment 60 --mp3 --mp3-bitrate 320 --mp3-preset 2 'audio.mp3'"
          ),
      ),
      (
          "no_split",
          {"split": False},
          (
              "python -m demucs.separate -o 'test/audio_processing' --device"
              " cpu --shifts 10 --overlap 0.25 -j 0 --two-stems vocals"
              " --no-split --mp3 --mp3-bitrate 320 --mp3-preset 2 'audio.mp3'"
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


class TestExtractCommandInfo(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "Standard MP3",
          (
              "python3 -m demucs.separate -o 'out_folder' --mp3 --two-stems"
              " 'audio.mp3'"
          ),
          "out_folder",
          ".mp3",
          "audio",
      ),
      (
          "FLAC Output",
          (
              "python3 -m demucs.separate -o 'results' --flac --shifts 5"
              " 'audio.flac'"
          ),
          "results",
          ".flac",
          "audio",
      ),
      (
          "WAV with Int24",
          "python3 -m demucs.separate -o 'wav_output' --int24 'song.wav'",
          "wav_output",
          ".wav",
          "song",
      ),
      (
          "WAV with Float32",
          "python3 -m demucs.separate -o 'float32_dir' --float32 'music.mp3'",
          "float32_dir",
          ".wav",
          "music",
      ),
  )
  def test_valid_command(
      self, command, expected_folder, expected_ext, expected_input
  ):
    result = audio_processing.extract_command_info(command)
    self.assertEqual(
        result,
        (expected_folder, expected_ext, expected_input),
        f"Failed for command: {command}",
    )


class TestAssembleSplitAudioFilePaths(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "Standard MP3",
          (
              "python3 -m demucs.separate -o 'test/audio_processing' --device"
              " cpu --shifts 10 --overlap 0.25 --clip_mode rescale -j 0"
              " --two-stems --segment 60 'audio.mp3'"
          ),
          "test/audio_processing/htdemucs/audio/vocals.wav",
          "test/audio_processing/htdemucs/audio/no_vocals.wav",
      ),
      (
          "FLAC Output",
          (
              "python3 -m demucs.separate -o 'out_flac/audio_processing' --flac"
              " 'audio.mp3'"
          ),
          "out_flac/audio_processing/htdemucs/audio/vocals.flac",
          "out_flac/audio_processing/htdemucs/audio/no_vocals.flac",
      ),
      (
          "WAV Output (int24)",
          (
              "python3 -m demucs.separate -o 'out_wav/audio_processing' --int24"
              " 'audio.mp3'"
          ),
          "out_wav/audio_processing/htdemucs/audio/vocals.wav",
          "out_wav/audio_processing/htdemucs/audio/no_vocals.wav",
      ),
      (
          "WAV Output (float32)",
          (
              "python3 -m demucs.separate -o 'out_float32/audio_processing'"
              " --float32 'audio.mp3'"
          ),
          "out_float32/audio_processing/htdemucs/audio/vocals.wav",
          "out_float32/audio_processing/htdemucs/audio/no_vocals.wav",
      ),
  )
  def test_assemble_paths(
      self, command, expected_vocals_path, expected_background_path
  ):
    """Tests assembling paths for various Demucs commands and formats."""
    actual_vocals_path, actual_background_path = (
        audio_processing.assemble_split_audio_file_paths(command)
    )
    self.assertEqual(
        [actual_vocals_path, actual_background_path],
        [expected_vocals_path, expected_background_path],
    )


class TestExecuteDemucsCommand(absltest.TestCase):

  @patch("subprocess.run")
  def test_execute_command_success(self, mock_run):
    mock_run.return_value.stdout = "Command executed successfully"
    mock_run.return_value.stderr = ""
    mock_run.return_value.returncode = 0
    audio_processing.execute_demucs_command(
        command="echo 'Command executed successfully'"
    )
    mock_run.assert_called_once_with(
        "echo 'Command executed successfully'",
        shell=True,
        capture_output=True,
        text=True,
        check=True,
    )

  @mock.patch("subprocess.run")
  def test_execute_command_error(self, mock_run):
    """Test if DemucsCommandError is raised when command fails."""
    mock_run.side_effect = subprocess.CalledProcessError(
        1, "demucs.separate", stderr="Some Demucs error message"
    )

    with self.assertRaisesRegex(
        audio_processing.DemucsCommandError,
        r"Error in final attempt to separate audio:.*\nSome Demucs error"
        r" message",
    ):
      audio_processing.execute_demucs_command(
          "python3 -m demucs.separate -o out_folder --mp3 --two-stems audio.mp3"
      )


class TestExecuteVocalNonVocalsSplit(absltest.TestCase):

  @mock.patch("ariel.audio_processing.execute_demucs_command")
  @mock.patch("tensorflow.io.gfile.exists")
  def test_execute_vocals_non_vocals_split_files_exist(
      self, mock_exists, mock_execute_demucs_command
  ):
    mock_exists.side_effect = [True, True]
    audio_file = "test.wav"
    output_directory = "output_dir"
    device = "cpu"
    _, _ = audio_processing.execute_vocals_non_vocals_split(
        audio_file=audio_file, output_directory=output_directory, device=device
    )
    mock_execute_demucs_command.assert_not_called()

  @mock.patch("ariel.audio_processing.execute_demucs_command")
  @mock.patch("tensorflow.io.gfile.exists")
  def test_execute_vocals_non_vocals_split_files_dont_exist(
      self, mock_exists, mock_execute_demucs_command
  ):
    mock_exists.side_effect = [False, False]
    audio_file = "test.wav"
    output_directory = "output_dir"
    device = "cpu"
    audio_processing.execute_vocals_non_vocals_split(
        audio_file=audio_file, output_directory=output_directory, device=device
    )
    mock_execute_demucs_command.assert_called_once()

  @mock.patch("ariel.audio_processing.build_demucs_command")
  @mock.patch("ariel.audio_processing.execute_demucs_command")
  @mock.patch("tensorflow.io.gfile.exists")
  def test_execute_vocals_non_vocals_split_correct_command(
      self, mock_exists, mock_execute_demucs_command, mock_build_demucs_command
  ):
    mock_exists.side_effect = [False, False]
    audio_file = "test.wav"
    output_directory = "output_dir"
    device = "cpu"
    expected_command = (
        "python -m demucs.separate -o 'output_dir/audio_processing' --device"
        " cpu --shifts 10 --overlap 0.25 -j 0 --two-stems vocals 'test.wav'"
    )
    mock_build_demucs_command.return_value = expected_command
    audio_processing.execute_vocals_non_vocals_split(
        audio_file=audio_file, output_directory=output_directory, device=device
    )
    mock_build_demucs_command.assert_called_once_with(
        audio_file=audio_file, output_directory=output_directory, device=device
    )
    mock_execute_demucs_command.assert_called_once_with(
        command=expected_command
    )


class TestSplitAudioTrack(absltest.TestCase):

  @patch("tensorflow.io.gfile.exists")
  @patch("tensorflow.io.gfile.copy")
  @patch("tensorflow.io.gfile.rmtree")
  @patch("ariel.audio_processing.execute_vocals_non_vocals_split")
  @patch("ariel.audio_processing.build_demucs_command")
  @patch("ariel.audio_processing.assemble_split_audio_file_paths")
  def test_split_audio_track(
      self,
      mock_assemble_split_paths,
      mock_build_command,
      mock_execute_split,
      mock_rmtree,
      mock_copy,
      mock_exists,
  ):
    mock_execute_split.return_value = ("vocals_file.wav", "background_file.wav")
    mock_build_command.return_value = "demucs_command"
    mock_assemble_split_paths.return_value = (
        "vocals_file.wav",
        "background_file.wav",
    )
    mock_exists.side_effect = [False, False]
    vocals_path, background_path = audio_processing.split_audio_track(
        audio_file="input.wav",
        output_directory="output_dir",
        device="cpu",
        voice_separation_rounds=2,
    )
    self.assertEqual(
        vocals_path,
        os.path.join(
            "output_dir", audio_processing.AUDIO_PROCESSING, "vocals.wav"
        ),
    )
    self.assertEqual(
        background_path,
        os.path.join(
            "output_dir", audio_processing.AUDIO_PROCESSING, "no_vocals.wav"
        ),
    )

    mock_build_command.assert_called_once_with(
        audio_file="input.wav", output_directory="output_dir", device="cpu"
    )
    mock_copy.assert_any_call("vocals_file.wav", vocals_path)
    mock_copy.assert_any_call("background_file.wav", background_path)
    mock_rmtree.assert_called_once_with(
        os.path.join(
            "output_dir", audio_processing.AUDIO_PROCESSING, "htdemucs"
        )
    )

  @patch("tensorflow.io.gfile.exists")
  def test_split_audio_track_files_exist(self, mock_exists):
    mock_exists.side_effect = [True, True]
    vocals_path, background_path = audio_processing.split_audio_track(
        audio_file="input.wav", output_directory="output_dir", device="cpu"
    )
    self.assertEqual(
        vocals_path,
        os.path.join(
            "output_dir", audio_processing.AUDIO_PROCESSING, "vocals.mp3"
        ),
    )
    self.assertEqual(
        background_path,
        os.path.join(
            "output_dir", audio_processing.AUDIO_PROCESSING, "no_vocals.mp3"
        ),
    )


class CreatePyannoteTimestampsTest(absltest.TestCase):

  def test_create_timestamps_with_silence(self):
    with tempfile.NamedTemporaryFile(suffix=".wav") as temporary_file:
      silence_duration = 10
      silence = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence.write_audiofile(temporary_file.name)
      mock_pipeline = MagicMock(spec=Pipeline)
      mock_pipeline.return_value.itertracks.return_value = [
          (MagicMock(start=0.0, end=silence_duration), None, None)
      ]
      timestamps = audio_processing.create_pyannote_timestamps(
          audio_file=temporary_file.name,
          number_of_speakers=0,
          pipeline=mock_pipeline,
      )
      self.assertEqual(timestamps, [{"start": 0.0, "end": 10}])


class MergeUtterancesTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "merge_within_threshold",
          [
              {
                  "start": 0.0,
                  "end": 1.0,
              },
              {
                  "start": 1.1,
                  "end": 2.0,
              },
              {
                  "start": 2.1,
                  "end": 3.0,
              },
          ],
          0.2,
          [
              {
                  "start": 0.0,
                  "end": 2.0,
              },
              {
                  "start": 2.1,
                  "end": 3.0,
              },
          ],
      ),
      (
          "no_merge_above_threshold",
          [
              {
                  "start": 0.0,
                  "end": 1.0,
              },
              {
                  "start": 1.5,
                  "end": 2.0,
              },
              {
                  "start": 2.1,
                  "end": 3.0,
              },
          ],
          0.1,
          [
              {
                  "start": 0.0,
                  "end": 1.0,
              },
              {
                  "start": 1.5,
                  "end": 2.0,
              },
              {
                  "start": 2.1,
                  "end": 3.0,
              },
          ],
      ),
  )
  def test_merge_utterances(
      self,
      utterance_metadata,
      minimum_merge_threshold,
      expected_merged_utterances,
  ):
    merged = audio_processing.merge_utterances(
        utterance_metadata=utterance_metadata,
        minimum_merge_threshold=minimum_merge_threshold,
    )
    self.assertSequenceEqual(merged, expected_merged_utterances)


class TestCutAndSaveAudio(absltest.TestCase):

  def test_cut_and_save_audio_no_clone(self):
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      silence_duration = 10
      silence = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence.write_audiofile(temporary_file.name)
      with tempfile.TemporaryDirectory() as output_directory:
        os.makedirs(
            os.path.join(output_directory, audio_processing.AUDIO_PROCESSING)
        )
        audio = AudioSegment.from_file(temporary_file.name)
        audio_processing.cut_and_save_audio(
            audio=audio,
            utterance=dict(start=0.1, end=0.2),
            prefix="chunk",
            output_directory=output_directory,
        )
        expected_file = os.path.join(
            output_directory,
            audio_processing.AUDIO_PROCESSING,
            "chunk_0.1_0.2.mp3",
        )
        self.assertTrue(os.path.exists(expected_file))


class TestRunCutAndSaveAudio(absltest.TestCase):

  def test_run_cut_and_save_audio(self):
    with tempfile.NamedTemporaryFile(suffix=".mp3") as temporary_file:
      silence_duration = 10
      silence = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence.write_audiofile(temporary_file.name)
      utterance_metadata = [{"start": 0.0, "end": 5.0}]
      with tempfile.TemporaryDirectory() as output_directory:
        os.makedirs(
            os.path.join(output_directory, audio_processing.AUDIO_PROCESSING)
        )
        _ = audio_processing.run_cut_and_save_audio(
            utterance_metadata=utterance_metadata,
            audio_file=temporary_file.name,
            output_directory=output_directory,
            elevenlabs_clone_voices=False,
        )
        expected_file = os.path.join(
            output_directory,
            audio_processing.AUDIO_PROCESSING,
            "chunk_0.0_5.0.mp3",
        )
        self.assertTrue(os.path.exists(expected_file))


class VerifyAddedAudioChunkTest(absltest.TestCase):

  @patch("ariel.audio_processing.cut_and_save_audio")
  def test_verify_added_audio_chunk(self, mock_cut_and_save_audio):
    with tempfile.TemporaryDirectory() as tmpdir:
      os.makedirs(os.path.join(tmpdir, audio_processing.AUDIO_PROCESSING))
      mock_cut_and_save_audio.side_effect = [
          os.path.join(
              tmpdir, audio_processing.AUDIO_PROCESSING, "chunk_test.mp3"
          ),
      ]
      audio_file_path = os.path.join(tmpdir, "test_audio.mp3")
      AudioSegment.silent(duration=3000).export(audio_file_path, format="mp3")
      utterance = {"start": 0.5, "end": 2.5}
      result = audio_processing.verify_added_audio_chunk(
          audio_file=audio_file_path,
          utterance=utterance,
          output_directory=tmpdir,
      )
      expected_result = {
          **utterance,
          "path": os.path.join(
              tmpdir, audio_processing.AUDIO_PROCESSING, "chunk_test.mp3"
          ),
      }
      self.assertEqual(result, expected_result)


class VerifyModifiedAudioChunkTest(absltest.TestCase):

  @patch("tensorflow.io.gfile.remove")
  @patch("ariel.audio_processing.cut_and_save_audio")
  def test_verify_modified_audio_chunk(
      self, mock_cut_and_save_audio, mock_remove
  ):
    with tempfile.TemporaryDirectory() as tmpdir:
      os.makedirs(os.path.join(tmpdir, audio_processing.AUDIO_PROCESSING))
      mock_cut_and_save_audio.side_effect = [
          os.path.join(
              tmpdir, audio_processing.AUDIO_PROCESSING, "chunk_correct.mp3"
          ),
      ]
      audio_file_path = os.path.join(
          tmpdir, audio_processing.AUDIO_PROCESSING, "test_audio.mp3"
      )
      AudioSegment.silent(duration=3000).export(audio_file_path, format="mp3")
      utterance = {
          "start": 1.0,
          "end": 2.0,
          "path": "wrong_chunk.mp3",
          "for_dubbing": True,
      }
      result = audio_processing.verify_modified_audio_chunk(
          audio_file=audio_file_path,
          utterance=utterance,
          output_directory=tmpdir,
      )
      expected_result = {
          **utterance,
          "path": os.path.join(
              tmpdir, audio_processing.AUDIO_PROCESSING, "chunk_correct.mp3"
          ),
      }
      self.assertEqual(result, expected_result)
      mock_remove.assert_has_calls([
          mock.call("wrong_chunk.mp3"),
      ])
      mock_cut_and_save_audio.assert_any_call(
          audio=AudioSegment.from_file(audio_file_path),
          utterance=utterance,
          prefix="chunk",
          output_directory=tmpdir,
      )


class TestInsertAudioAtTimestamps(absltest.TestCase):

  def test_insert_audio_at_timestamps(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      os.makedirs(
          os.path.join(temporary_directory, audio_processing.AUDIO_PROCESSING)
      )
      background_audio_file = f"{temporary_directory}/test_background.mp3"
      silence_duration = 10
      silence = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence.write_audiofile(background_audio_file)
      audio_chunk_path = f"{temporary_directory}/test_chunk.mp3"
      chunk_duration = 2
      chunk = AudioArrayClip(
          np.zeros((int(44100 * chunk_duration), 2), dtype=np.int16),
          fps=44100,
      )
      chunk.write_audiofile(audio_chunk_path)
      utterance_metadata = [{
          "start": 3.0,
          "end": 5.0,
          "dubbed_path": audio_chunk_path,
          "for_dubbing": True,
      }]
      output_path = audio_processing.insert_audio_at_timestamps(
          utterance_metadata=utterance_metadata,
          background_audio_file=background_audio_file,
          output_directory=temporary_directory,
      )
      self.assertTrue(os.path.exists(output_path))


class MixMusicAndVocalsTest(absltest.TestCase):

  def test_mix_music_and_vocals(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      os.makedirs(os.path.join(temporary_directory, audio_processing._OUTPUT))
      background_audio_path = f"{temporary_directory}/test_background.mp3"
      vocals_audio_path = f"{temporary_directory}/test_vocals.mp3"
      silence_duration = 10
      silence_background = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence_background.write_audiofile(background_audio_path)
      silence_duration = 5
      silence_vocals = AudioArrayClip(
          np.zeros((int(44100 * silence_duration), 2), dtype=np.int16),
          fps=44100,
      )
      silence_vocals.write_audiofile(vocals_audio_path)
      output_audio_path = audio_processing.merge_background_and_vocals(
          background_audio_file=background_audio_path,
          dubbed_vocals_audio_file=vocals_audio_path,
          output_directory=temporary_directory,
          target_language="en-US",
      )
      self.assertTrue(os.path.exists(output_audio_path))


if __name__ == "__main__":
  absltest.main()

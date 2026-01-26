# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law
# or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the process.py file."""

import os
import shutil
import subprocess
import tempfile
from typing_extensions import override
import unittest
import unittest.mock
from models import Speaker
from models import Utterance
import moviepy
import process
import soundfile


class ProcessTest(unittest.TestCase):
  """Test cases for the process module."""

  @override
  def setUp(self):
    """Creates a temporary directory for test outputs."""
    super().setUp()
    self.temp_dir = tempfile.mkdtemp()

  @override
  def tearDown(self):
    """Removes the temporary directory and its contents."""
    super().tearDown()
    shutil.rmtree(self.temp_dir)

  def test_separate_audio_from_video_success(self):
    """Tests that `separate_audio_from_video` successfully separates audio."""

    video_file_path = "tests/test_data/video_with_audio.mp4"

    original_audio_path, vocals_path, background_path = (
        process.separate_audio_from_video(video_file_path, self.temp_dir)
    )

    self.assertTrue(os.path.exists(original_audio_path))
    self.assertTrue(os.path.exists(vocals_path))
    self.assertTrue(os.path.exists(background_path))
    self.assertEqual(original_audio_path, f"{self.temp_dir}/original_audio.wav")
    self.assertEqual(
        vocals_path,
        os.path.join(self.temp_dir, "htdemucs", "original_audio", "vocals.wav"),
    )
    self.assertEqual(
        background_path,
        os.path.join(
            self.temp_dir, "htdemucs", "original_audio", "no_vocals.wav"
        ),
    )

  def test_separate_audio_from_video_no_audio(self):
    """Tests that `separate_audio_from_video` raises an error if no audio."""

    video_file_path = "tests/test_data/no_audio_video.mp4"

    with self.assertRaisesRegex(
        RuntimeError, f"Could not extract audio from {video_file_path}"
    ):

      process.separate_audio_from_video(video_file_path, self.temp_dir)

  def test_separate_audio_from_video_separation_fails(self):
    """Tests that `separate_audio_from_video` raises an error if separation fails."""

    video_file_path = "tests/test_data/video_with_audio.mp4"

    # To simulate separation failure, mock subprocess.run to raise an exception.
    with unittest.mock.patch("process.subprocess.run") as mock_subprocess_run:

      mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, "cmd")

      with self.assertRaises(subprocess.CalledProcessError):
        process.separate_audio_from_video(video_file_path, self.temp_dir)


class MergeVocalsTest(unittest.TestCase):
  """Test cases for the merge_vocals function."""

  @override
  def setUp(self):
    """Creates a temporary directory and audio files for test outputs."""
    super().setUp()
    self.temp_dir = tempfile.mkdtemp()
    self.target_language = "en-US"

    # Create dummy audio files for utterances
    self.audio_path_1 = "tests/test_data/one_second_tone.wav"
    self.audio_path_2 = "tests/test_data/two_seconds_tone.wav"

    # Create a dummy original vocals file for muted tests
    self.original_vocals_dir = os.path.join(
        self.temp_dir, "htdemucs", "original_audio"
    )
    os.makedirs(self.original_vocals_dir, exist_ok=True)
    self.original_vocals_path = os.path.join(
        self.original_vocals_dir, "vocals.wav"
    )
    # A 3-second silent wav file
    os.system(
        "ffmpeg -f lavfi -i anullsrc=r=44100 -t 3 -y"
        + f" {self.original_vocals_path} > /dev/null 2>&1"
    )

  @override
  def tearDown(self):
    """Removes the temporary directory and its contents."""
    super().tearDown()
    shutil.rmtree(self.temp_dir)

  def test_merge_vocals_multiple_utterances(self):
    """Tests merging multiple valid utterances."""
    mock_speaker = Speaker(speaker_id="speaker1", voice="fake-voice")
    dubbed_vocals_metadata = [
        Utterance(
            id="1",
            original_text="Hello",
            translated_text="Hi",
            instructions="",
            speaker=mock_speaker,
            original_start_time=0.0,
            original_end_time=1.0,
            translated_start_time=0.5,
            translated_end_time=1.5,
            removed=False,
            muted=False,
            audio_url=self.audio_path_1,
        ),
        Utterance(
            id="2",
            original_text="World",
            translated_text="World",
            instructions="",
            speaker=mock_speaker,
            original_start_time=1.5,
            original_end_time=2.5,
            translated_start_time=2.0,
            translated_end_time=4.0,
            removed=False,
            muted=False,
            audio_url=self.audio_path_2,
        ),
    ]

    output_path = process.merge_vocals(
        dubbed_vocals_metadata=dubbed_vocals_metadata,
        output_directory=self.temp_dir,
        target_language=self.target_language,
    )

    expected_output_file = os.path.join(self.temp_dir, "vocals_only_en_us.wav")
    self.assertEqual(output_path, expected_output_file)
    self.assertTrue(os.path.exists(expected_output_file))

    info = soundfile.info(expected_output_file)
    self.assertAlmostEqual(info.duration, 4.0, delta=0.1)

  def test_merge_vocals_removed_utterance(self):
    """Tests that removed utterances are skipped."""
    mock_speaker = Speaker(speaker_id="speaker1", voice="fake-voice")
    dubbed_vocals_metadata = [
        Utterance(
            id="1",
            original_text="Hello",
            translated_text="Hi",
            instructions="",
            speaker=mock_speaker,
            original_start_time=0.0,
            original_end_time=1.0,
            translated_start_time=0.0,
            translated_end_time=1.0,
            removed=True,  # This utterance is removed
            muted=False,
            audio_url=self.audio_path_1,
        ),
        Utterance(
            id="2",
            original_text="World",
            translated_text="World",
            instructions="",
            speaker=mock_speaker,
            original_start_time=1.5,
            original_end_time=2.5,
            translated_start_time=1.5,
            translated_end_time=3.5,
            removed=False,
            muted=False,
            audio_url=self.audio_path_2,
        ),
    ]

    output_path = process.merge_vocals(
        dubbed_vocals_metadata=dubbed_vocals_metadata,
        output_directory=self.temp_dir,
        target_language=self.target_language,
    )

    expected_output_file = os.path.join(self.temp_dir, "vocals_only_en_us.wav")
    self.assertEqual(output_path, expected_output_file)
    self.assertTrue(os.path.exists(expected_output_file))

    info = soundfile.info(expected_output_file)
    # The duration should be based on the end time of the second utterance
    self.assertAlmostEqual(info.duration, 3.5, delta=0.1)

  def test_merge_vocals_muted_utterance(self):
    """Tests that muted utterances use the original vocals."""
    mock_speaker = Speaker(speaker_id="speaker1", voice="fake-voice")
    dubbed_vocals_metadata = [
        Utterance(
            id="1",
            original_text="Hello",
            translated_text="Hi",
            instructions="",
            speaker=mock_speaker,
            original_start_time=0.5,
            original_end_time=1.5,
            translated_start_time=0.5,
            translated_end_time=1.5,
            removed=False,
            muted=True,  # This utterance is muted
            audio_url=self.audio_path_1,  # This should be ignored
        )
    ]

    output_path = process.merge_vocals(
        dubbed_vocals_metadata=dubbed_vocals_metadata,
        output_directory=self.temp_dir,
        target_language=self.target_language,
    )

    expected_output_file = os.path.join(self.temp_dir, "vocals_only_en_us.wav")
    self.assertEqual(output_path, expected_output_file)
    self.assertTrue(os.path.exists(expected_output_file))

    info = soundfile.info(expected_output_file)
    # The duration should be based on the utterance's end time
    self.assertAlmostEqual(info.duration, 1.5, delta=0.1)

  def test_merge_vocals_empty_utterances(self):
    """Tests merging with an empty list of utterances."""
    dubbed_vocals_metadata = []

    output_path = process.merge_vocals(
        dubbed_vocals_metadata=dubbed_vocals_metadata,
        output_directory=self.temp_dir,
        target_language=self.target_language,
    )

    expected_output_file = os.path.join(self.temp_dir, "vocals_only_en_us.wav")
    self.assertEqual(output_path, expected_output_file)
    self.assertTrue(os.path.exists(expected_output_file))
    # verify that the file is empty
    self.assertEqual(os.path.getsize(expected_output_file), 0)


class MergeBackgroundAndVocalsTest(unittest.TestCase):
  """Test cases for the merge_background_and_vocals function."""

  @override
  def setUp(self):
    """Creates a temporary directory and audio files for test outputs."""
    super().setUp()
    self.temp_dir = tempfile.mkdtemp()
    self.target_language = "en-US"
    self.background_audio_path = "tests/test_data/two_seconds_tone.wav"
    self.vocals_path = "tests/test_data/one_second_tone.wav"

  @override
  def tearDown(self):
    """Removes the temporary directory and its contents."""
    super().tearDown()
    shutil.rmtree(self.temp_dir)

  def test_merge_background_and_vocals_success(self):
    """Tests that `merge_background_and_vocals` successfully merges audio."""

    output_path = process.merge_background_and_vocals(
        background_audio_file=self.background_audio_path,
        dubbed_vocals_path=self.vocals_path,
        output_directory=self.temp_dir,
        target_language=self.target_language,
    )

    expected_output_file = os.path.join(self.temp_dir, "dubbed_audio_en_us.wav")
    self.assertEqual(output_path, expected_output_file)
    self.assertTrue(os.path.exists(expected_output_file))

    info = soundfile.info(expected_output_file)
    # The duration should be based on the longest audio file, which is 2s.
    self.assertAlmostEqual(info.duration, 2.0, delta=0.1)

  def test_merge_background_and_vocals_invalid_input_file(self):
    """Tests `merge_background_and_vocals` with invalid or missing input files."""
    # Test with a non-existent background file
    with self.assertRaises(IOError):
      process.merge_background_and_vocals(
          background_audio_file="non_existent_file.wav",
          dubbed_vocals_path=self.vocals_path,
          output_directory=self.temp_dir,
          target_language=self.target_language,
      )

    # Test with a non-existent vocals file
    with self.assertRaises(IOError):
      process.merge_background_and_vocals(
          background_audio_file=self.background_audio_path,
          dubbed_vocals_path="non_existent_file.wav",
          output_directory=self.temp_dir,
          target_language=self.target_language,
      )

    # Test with an invalid audio file
    invalid_file = os.path.join(self.temp_dir, "invalid.wav")
    with open(invalid_file, "w") as f:
      f.write("this is not an audio file")

    with self.assertRaises(IOError):
      process.merge_background_and_vocals(
          background_audio_file=invalid_file,
          dubbed_vocals_path=self.vocals_path,
          output_directory=self.temp_dir,
          target_language=self.target_language,
      )

  def test_merge_background_and_vocals_unwritable_output(self):
    """Tests `merge_background_and_vocals` with an unwritable output directory."""
    try:
      # Make the directory read-only
      os.chmod(self.temp_dir, 0o555)

      returned_path = process.merge_background_and_vocals(
          background_audio_file=self.background_audio_path,
          dubbed_vocals_path=self.vocals_path,
          output_directory=self.temp_dir,
          target_language=self.target_language,
      )
      # Since moviepy does not raise an exception, we assert that the file was
      # not created.
      self.assertFalse(
          os.path.exists(returned_path),
          "The audio file should not be created in a read-only directory",
      )
    finally:
      # Change back to writable so tearDown can remove it.
      os.chmod(self.temp_dir, 0o755)


class CombineVideoAndAudioTest(unittest.TestCase):
  """Test cases for the combine_video_and_audio function."""

  @override
  def setUp(self):
    """Creates a temporary directory for test outputs."""
    super().setUp()
    self.temp_dir = tempfile.mkdtemp()
    self.video_path = "tests/test_data/no_audio_video.mp4"
    self.audio_path = "tests/test_data/one_second_tone.wav"

  @override
  def tearDown(self):
    """Removes the temporary directory and its contents."""
    super().tearDown()
    shutil.rmtree(self.temp_dir)

  def test_combine_video_and_audio_success(self):
    """Tests that `combine_video_and_audio` successfully combines video and audio."""
    output_video_path = os.path.join(self.temp_dir, "output.mp4")

    process.combine_video_and_audio(
        video_file_path=self.video_path,
        audio_file_path=self.audio_path,
        output_file_path=output_video_path,
    )

    self.assertTrue(os.path.exists(output_video_path))

    # Verify the output video has audio and correct duration.
    video_clip = moviepy.VideoFileClip(output_video_path)
    self.assertIsNotNone(video_clip.audio)

    input_video_clip = moviepy.VideoFileClip(self.video_path)
    expected_duration = input_video_clip.duration
    input_video_clip.close()

    self.assertAlmostEqual(video_clip.duration, expected_duration, delta=0.2)
    if video_clip.audio:
      self.assertAlmostEqual(
          video_clip.audio.duration, expected_duration, delta=0.2
      )

    video_clip.close()

  def test_combine_video_and_audio_invalid_paths(self):
    """Tests `combine_video_and_audio` with invalid or missing input files."""
    output_video_path = os.path.join(self.temp_dir, "output.mp4")

    with self.assertRaises(IOError):
      process.combine_video_and_audio(
          video_file_path="non_existent_video.mp4",
          audio_file_path=self.audio_path,
          output_file_path=output_video_path,
      )

    with self.assertRaises(IOError):
      process.combine_video_and_audio(
          video_file_path=self.video_path,
          audio_file_path="non_existent_audio.wav",
          output_file_path=output_video_path,
      )


if __name__ == "__main__":

  unittest.main()

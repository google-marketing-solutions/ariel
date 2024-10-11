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

"""Tests for utility functions in translation.py."""

import os
import tempfile
from unittest.mock import MagicMock
from absl.testing import absltest
from absl.testing import parameterized
from ariel import translation
import google.generativeai as genai
import tensorflow as tf


class GenerateScriptTest(parameterized.TestCase):

  @parameterized.named_parameters(
      ("empty_input", [], "<BREAK><BREAK>"),
      (
          "single_utterance",
          [{
              "text": "Hello, world!",
              "start": 0.0,
              "stop": 1.0,
              "speaker_id": "speaker1",
              "ssml_gender": "male",
          }],
          "<BREAK>Hello, world!<BREAK>",
      ),
      (
          "multiple_utterances",
          [
              {
                  "text": "This is",
                  "start": 0.0,
                  "stop": 1.0,
                  "speaker_id": "speaker1",
                  "ssml_gender": "male",
              },
              {
                  "text": "a test.",
                  "start": 1.0,
                  "stop": 2.0,
                  "speaker_id": "speaker2",
                  "ssml_gender": "female",
              },
          ],
          "<BREAK>This is<BREAK>a test.<BREAK>",
      ),
      (
          "empty_string",
          [
              {
                  "text": "This is",
                  "start": 0.0,
                  "stop": 1.0,
                  "speaker_id": "speaker1",
                  "ssml_gender": "male",
              },
              {
                  "text": "",
                  "start": 1.0,
                  "stop": 2.0,
                  "speaker_id": "speaker2",
                  "ssml_gender": "female",
              },
          ],
          "<BREAK>This is<BREAK><BREAK>",
      ),
  )
  def test_generate_script(self, utterance_metadata, expected_script):
    self.assertEqual(
        translation.generate_script(utterance_metadata=utterance_metadata),
        expected_script,
    )


class TranslateScriptTest(absltest.TestCase):

  def test_translate_script(self):
    mock_model = MagicMock(spec=genai.GenerativeModel)
    mock_chat_session = MagicMock()
    mock_chat_session.send_message.return_value = MagicMock(text="Test.")
    mock_model.start_chat.return_value = mock_chat_session
    translation_output = translation.translate_script(
        script="Test.",
        advertiser_name="Advertiser Name",
        translation_instructions="Translate to Polish.",
        target_language="pl-PL",
        model=mock_model,
    )
    self.assertEqual(translation_output, "Test.")


class AddTranslationsTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "valid_input",
          [
              {
                  "text": "Hello",
                  "start": 0.0,
                  "stop": 1.0,
                  "speaker_id": "speaker1",
                  "ssml_gender": "male",
              },
              {
                  "text": "World",
                  "start": 1.0,
                  "stop": 2.0,
                  "speaker_id": "speaker2",
                  "ssml_gender": "female",
              },
          ],
          "Bonjour<BREAK>Le Monde",
          [
              {
                  "text": "Hello",
                  "start": 0.0,
                  "stop": 1.0,
                  "speaker_id": "speaker1",
                  "ssml_gender": "male",
                  "translated_text": "Bonjour",
              },
              {
                  "text": "World",
                  "start": 1.0,
                  "stop": 2.0,
                  "speaker_id": "speaker2",
                  "ssml_gender": "female",
                  "translated_text": "Le Monde",
              },
          ],
      ),
      (
          "do_not_translate",
          [
              {
                  "text": "Hello",
                  "start": 0.0,
                  "stop": 1.0,
                  "speaker_id": "speaker1",
                  "ssml_gender": "male",
              },
              {
                  "text": "World",
                  "start": 1.0,
                  "stop": 2.0,
                  "speaker_id": "speaker2",
                  "ssml_gender": "female",
              },
          ],
          "<DO NOT TRANSLATE><BREAK>Le Monde",
          [
              {
                  "text": "World",
                  "start": 1.0,
                  "stop": 2.0,
                  "speaker_id": "speaker2",
                  "ssml_gender": "female",
                  "translated_text": "Le Monde",
              },
          ],
      ),
  )
  def test_add_translations(
      self, utterance_metadata, translated_script, expected_translated_metadata
  ):
    updated_metadata = translation.add_translations(
        utterance_metadata=utterance_metadata,
        translated_script=translated_script,
    )
    self.assertEqual(updated_metadata, expected_translated_metadata)

  def test_add_translations_with_mismatched_length(self):
    utterance_metadata = [
        {
            "text": "Hello",
            "start": 0.0,
            "stop": 1.0,
            "speaker_id": "speaker1",
            "ssml_gender": "male",
        },
    ]
    translated_script = "Bonjour<BREAK>Le Monde<BREAK>Another Segment"
    with self.assertRaisesRegex(
        translation.GeminiTranslationError,
        "The utterance metadata must be of the same length",
    ):
      translation.add_translations(
          utterance_metadata=utterance_metadata,
          translated_script=translated_script,
      )


class SaveSRTSubtitlesTest(absltest.TestCase):

  def test_create_srt_subtitles(self):
    with tempfile.TemporaryDirectory() as tmpdir:
      utterance_metadata = [
          {
              "start": 1.81971875,
              "end": 3.8109687500000002,
              "translated_text": "It's good to catch the last train.",
          },
          {
              "start": 6.13971875,
              "end": 8.14784375,
              "translated_text": "Just like understanding words.",
          },
      ]

      translation.save_srt_subtitles(
          utterance_metadata=utterance_metadata, output_directory=tmpdir
      )

      expected_srt_content = (
          "1\n"
          "00:00:01,819 --> 00:00:03,810\n"
          "It's good to catch the last train.\n\n"
          "2\n"
          "00:00:06,139 --> 00:00:08,147\n"
          "Just like understanding words.\n\n"
      )

      srt_file_path = os.path.join(tmpdir, "translated_subtitles.srt")
      with tf.io.gfile.GFile(srt_file_path, "r") as f:
        actual_srt_content = f.read()

      self.assertEqual(actual_srt_content, expected_srt_content)


if __name__ == "__main__":
  absltest.main()

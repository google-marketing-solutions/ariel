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

from unittest.mock import MagicMock
from absl.testing import absltest
from absl.testing import parameterized
from ariel import translation
import google.generativeai as genai


class GenerateScriptTest(parameterized.TestCase):

  @parameterized.named_parameters(
      ("empty_input", [], ""),
      (
          "single_utterance",
          [{
              "text": "Hello, world!",
              "start": 0.0,
              "stop": 1.0,
              "speaker_id": "speaker1",
              "ssml_gender": "male",
          }],
          "Hello, world!",
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
          "This is <BREAK> a test.",
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
        ValueError, "The utterance metadata must be of the same length"
    ):
      translation.add_translations(
          utterance_metadata=utterance_metadata,
          translated_script=translated_script,
      )


class MergeUtterancesTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "merge_within_threshold",
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "path": "a.wav",
                  "translated_text": "Hello",
              },
              {
                  "start": 1.1,
                  "end": 2.0,
                  "path": "b.wav",
                  "translated_text": "world",
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "path": "c.wav",
                  "translated_text": "!",
              },
          ],
          0.2,
          [
              {
                  "start": 0.0,
                  "end": 2.0,
                  "translated_text": "Hello world",
                  "path": ("a.wav", "b.wav"),
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "translated_text": "!",
                  "path": "c.wav",
              },
          ],
      ),
      (
          "no_merge_above_threshold",
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "path": "a.wav",
                  "translated_text": "Hello",
              },
              {
                  "start": 1.5,
                  "end": 2.0,
                  "path": "b.wav",
                  "translated_text": "world",
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "path": "c.wav",
                  "translated_text": "!",
              },
          ],
          0.1,
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "path": "a.wav",
                  "translated_text": "Hello",
              },
              {
                  "start": 1.5,
                  "end": 2.0,
                  "path": "b.wav",
                  "translated_text": "world",
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "path": "c.wav",
                  "translated_text": "!",
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
    merged = translation.merge_utterances(
        utterance_metadata=utterance_metadata,
        minimum_merge_threshold=minimum_merge_threshold,
    )
    self.assertSequenceEqual(merged, expected_merged_utterances)


if __name__ == "__main__":
  absltest.main()

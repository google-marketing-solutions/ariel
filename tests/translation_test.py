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
        transcript="Test.",
        company_name="Advertiser Name",
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
      self, utterance_metadata, text_string, expected_translated_metadata
  ):
    updated_metadata = translation.add_translations(
        utterance_metadata, text_string
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
    text_string = "Bonjour<BREAK>Le Monde<BREAK>Another Segment"
    with self.assertRaisesRegex(
        ValueError, "The utterance metadata must be of the same length"
    ):
      translation.add_translations(utterance_metadata, text_string)


class MergeUtterancesTest(parameterized.TestCase):

  @parameterized.named_parameters(
      (
          "merge_within_threshold",
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "a.wav",
                  "translated_text": "Hello",
              },
              {
                  "start": 1.1,
                  "end": 2.0,
                  "chunk_path": "b.wav",
                  "translated_text": "world",
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "chunk_path": "c.wav",
                  "translated_text": "!",
              },
          ],
          0.2,
          [
              {
                  "start": 0.0,
                  "end": 2.0,
                  "translated_text": "Hello world",
                  "chunk_path": ("a.wav", "b.wav"),
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "translated_text": "!",
                  "chunk_path": "c.wav",
              },
          ],
      ),
      (
          "no_merge_above_threshold",
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "a.wav",
                  "translated_text": "Hello",
              },
              {
                  "start": 1.5,
                  "end": 2.0,
                  "chunk_path": "b.wav",
                  "translated_text": "world",
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "chunk_path": "c.wav",
                  "translated_text": "!",
              },
          ],
          0.1,
          [
              {
                  "start": 0.0,
                  "end": 1.0,
                  "chunk_path": "a.wav",
                  "translated_text": "Hello",
              },
              {
                  "start": 1.5,
                  "end": 2.0,
                  "chunk_path": "b.wav",
                  "translated_text": "world",
              },
              {
                  "start": 2.1,
                  "end": 3.0,
                  "chunk_path": "c.wav",
                  "translated_text": "!",
              },
          ],
      ),
  )
  def test_merge_utterances(
      self, utterances, timestamp_threshold, expected_merged_utterances
  ):
    merged = translation.merge_utterances(utterances, timestamp_threshold)
    self.assertSequenceEqual(merged, expected_merged_utterances)


if __name__ == "__main__":
  absltest.main()
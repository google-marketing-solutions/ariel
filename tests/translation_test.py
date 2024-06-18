"""Tests for utility functions in translation.py."""

from unittest.mock import MagicMock
from absl.testing import absltest
from absl.testing import parameterized
from ariel import translation
import google.generativeai as genai


class GenerateScriptTest(parameterized.TestCase):

  @parameterized.named_parameters(
      ('empty_input', [], ''),
      (
          'single_utterance',
          [{
              'text': 'Hello, world!',
              'start': 0.0,
              'stop': 1.0,
              'speaker_id': 'speaker1',
              'ssml_gender': 'male',
          }],
          'Hello, world!',
      ),
      (
          'multiple_utterances',
          [
              {
                  'text': 'This is',
                  'start': 0.0,
                  'stop': 1.0,
                  'speaker_id': 'speaker1',
                  'ssml_gender': 'male',
              },
              {
                  'text': 'a test.',
                  'start': 1.0,
                  'stop': 2.0,
                  'speaker_id': 'speaker2',
                  'ssml_gender': 'female',
              },
          ],
          'This is <BREAK> a test.',
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
    mock_chat_session.send_message.return_value = MagicMock(text='Test.')
    mock_model.start_chat.return_value = mock_chat_session
    translation_output = translation.translate_script(
        transcript='Test.',
        company_name='Advertiser Name',
        translation_instructions='Translate to Polish.',
        target_language='pl-PL',
        model=mock_model,
    )
    self.assertEqual(translation_output, 'Test.')


if __name__ == '__main__':
  absltest.main()

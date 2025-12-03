"""Tests for translate.py."""
import unittest
from unittest.mock import MagicMock
from translate import translate_text


class TestTranslate(unittest.TestCase):
  """Tests for translation functions."""

  def test_translate_text_success(self):
    """Tests a proper, error free call."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Hola Mundo"
    mock_response.usage_metadata.total_token_count = 10
    mock_client.models.generate_content.return_value = mock_response

    original_lang = "English"
    target_lang = "Spanish"
    text = "Hello World"
    instructions = "Keep it simple."

    # Execution
    result = translate_text(
        genai_client=mock_client,
        original_lang=original_lang,
        target_lang=target_lang,
        text=text,
        model_name="gemini-2.5-flash",
        instructions=instructions,
    )

    self.assertEqual(result, "Hola Mundo")

    mock_client.models.generate_content.assert_called_once()
    call_args = mock_client.models.generate_content.call_args
    self.assertEqual(call_args.kwargs["model"], "gemini-2.5-flash")

    prompt_arg = call_args.kwargs["contents"][0]
    self.assertIn("Translate the text from English to Spanish", prompt_arg)
    self.assertIn("Hello World", prompt_arg)
    self.assertIn("Keep it simple.", prompt_arg)

  def test_translate_text_failure(self):
    """Tests the case when translate_text returns empty content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = ""  # Simulate empty response
    mock_response.usage_metadata.total_token_count = 10
    mock_client.models.generate_content.return_value = mock_response

    original_lang = "English"
    target_lang = "Spanish"
    text = "Hello World"
    instructions = "Keep it simple."

    result = translate_text(
        genai_client=mock_client,
        original_lang=original_lang,
        target_lang=target_lang,
        text=text,
        model_name="gemini-2.5-flash",
        instructions=instructions,
    )

    self.assertEqual(result, "TRANSLATION FAILED")
    mock_client.models.generate_content.assert_called_once()
    call_args = mock_client.models.generate_content.call_args
    self.assertEqual(call_args.kwargs["model"], "gemini-2.5-flash")


if __name__ == "__main__":
  unittest.main()

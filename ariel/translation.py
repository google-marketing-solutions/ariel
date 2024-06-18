"""A translation module of Ariel package from the Google EMEA gTech Ads Data Science."""

from typing import Final, Mapping, Sequence
import google.generativeai as genai

_TRANSLATION_PROMPT: Final[str] = (
    "You're hired by a company called: {}. The received transcript is: {}."
    " Specific instructions: {}. The target language is: {}."
)


def generate_script(
    *, utterance_metadata: Sequence[Mapping[str, str | float]]
) -> str:
  """Generates a script string from a list of utterance metadata.

  Args:
    utterance_metadata: The sequence of mappings, where each mapping represents
      utterance metadata with 'text', 'start', 'stop', 'speaker_id',
      'ssml_gender' keys. The value associated with 'text' can be either a
      string or a float.

  Returns:
    A string representing the script, with "<BREAK>" inserted
    between chunks.
  """
  script = " <BREAK> ".join(str(item["text"]) for item in utterance_metadata)
  return script.rstrip(" <BREAK> ")


def translate_script(
    *,
    transcript: str,
    company_name: str,
    translation_instructions: str,
    target_language: str,
    model: genai.GenerativeModel,
) -> str:
  """Translates the provided transcript to the target language using a Generative AI model.

  Args:
      transcript: The transcript to translate.
      company_name: The name of the company.
      translation_instructions: Specific instructions for the translation.
      target_language: The target language for the translation.
      model: The GenerativeModel to use for translation.

  Returns:
      The translated script.
  """

  prompt = _TRANSLATION_PROMPT.format(
      company_name, transcript, translation_instructions, target_language
  )
  translation_chat_session = model.start_chat()
  response = translation_chat_session.send_message(prompt)
  translation_chat_session.rewind()
  return response.text

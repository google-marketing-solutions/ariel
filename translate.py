# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from google import genai
import configuration


def translate_text(
  genai_client: genai.Client,
  original_lang: str,
  target_lang: str,
  text: str,
  instructions: str = "",
) -> str:
  """Translates text from the original to the target language.

  Uses Google Gemini to translate the text. Gemini was chosen to be able to
  proivde detailed instructions on how the translation should be done.

  Args:
    original_lang: the language the text is in.
    target_lang: the language to translate to.
    text: the text to translate.
    instructions: additional instructions to include to steer the translation. Defaults to 'Nothing'
  """

  config = configuration.get_config()
  prompt = f"""
  # Translation Job
  ## Instructions
  Translate the text from {original_lang} to {target_lang}. Return only the translated text.
  {instructions}
  ## Original text
  {text}
  """

  response = genai_client.models.generate_content(
    model=config.gemini_model,
    contents=[prompt],
  )

  return response.text or "TRANSLATION FAILED"

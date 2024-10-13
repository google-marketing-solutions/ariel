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

"""A translation module of Ariel package from the Google EMEA gTech Ads Data Science."""

import datetime
import os
import re
from typing import Final, Mapping, Sequence
import tensorflow as tf
from vertexai.generative_models import GenerativeModel

_TRANSLATION_PROMPT: Final[str] = (
    "You're hired by a company called: {}. The received transcript is: {}."
    " Specific instructions: {}. The target language is: {}."
)
_BREAK_MARKER: Final[str] = "<BREAK>"
_DONT_TRANSLATE_MARKER: Final[str] = "<DO NOT TRANSLATE>"


def generate_script(*, utterance_metadata, key: str = "text") -> str:
  """Generates a script string from a list of utterance metadata.

  Args:
    utterance_metadata: The sequence of mappings, where each mapping represents
      utterance metadata with "text", "start", "end", "speaker_id",
      "ssml_gender", "for_dubbing" keys.
    key: The key to use when searching for the strings for the script.

  Returns:
    A string representing the script, with "<BREAK>" inserted
    between chunks.
  """
  trimmed_lines = [
      item[key].strip() if item[key] else "" for item in utterance_metadata
  ]
  return _BREAK_MARKER + _BREAK_MARKER.join(trimmed_lines) + _BREAK_MARKER


def translate_script(
    *,
    script: str,
    advertiser_name: str,
    translation_instructions: str,
    target_language: str,
    model: GenerativeModel,
) -> str:
  """Translates the provided transcript to the target language using a Generative AI model.

  Args:
      script: The transcript to translate.
      advertiser_name: The name of the advertiser.
      translation_instructions: Specific instructions for the translation.
      target_language: The target language for the translation.
      model: The GenerativeModel to use for translation.

  Returns:
      The translated script.
  """
  prompt = _TRANSLATION_PROMPT.format(
      advertiser_name, script, translation_instructions, target_language
  )
  response = model.generate_content(prompt)
  return response.text


class GeminiTranslationError(Exception):
  """Error when Gemini can't translate script correctly."""

  pass


def add_translations(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    translated_script: str,
) -> Sequence[Mapping[str, str | float]]:
  """Updates the "translated_text" field of each utterance metadata with the corresponding text segment.

  Args:
      utterance_metadata: The sequence of mappings, where each mapping
        represents utterance metadata with "text", "start", "end", "speaker_id",
        "ssml_gender", "path", "for_dubbing" and optionally "vocals_path" keys.
      translated_script: The string containing the translated text segments,
        separated by _BREAK_MARKER.

  Returns:
      A list of updated utterance metadata with the "translated_text" field
      populated.

  Raises:
      ValueError: If the number of utterance metadata and text segments do not
      match.
  """
  stripped_translation = re.sub(
      rf"^\s*{_BREAK_MARKER}\s*|\s*{_BREAK_MARKER}\s*$", "", translated_script
  )
  text_segments = stripped_translation.split(_BREAK_MARKER)
  if len(utterance_metadata) != len(text_segments):
    raise GeminiTranslationError(
        "The utterance metadata must be of the same length as the text"
        f" segments. Currently they are: {len(utterance_metadata)} and"
        f" {len(text_segments)}."
    )
  updated_utterance_metadata = []
  for metadata, translated_text in zip(utterance_metadata, text_segments):
    if translated_text != _DONT_TRANSLATE_MARKER:
      updated_utterance_metadata.append(
          {**metadata, "translated_text": translated_text}
      )
    else:
      continue
  return updated_utterance_metadata


def save_srt_subtitles(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    output_directory: str,
) -> str:
  """Returns a path to an SRT subtitle file from utterance metadata.

  Args:
    utterance_metadata: A list of dictionaries, where each dictionary contains
      information about an utterance, including 'start', 'end', and
      'translated_text'.
    output_directory: The directory where the SRT file will be saved.
  """
  srt_content = ""
  for i, utterance in enumerate(utterance_metadata):
    start_time = str(datetime.timedelta(seconds=utterance["start"]))[:-3]
    end_time = str(datetime.timedelta(seconds=utterance["end"]))[:-3]
    start_time = start_time.replace(".", ",").zfill(12)
    end_time = end_time.replace(".", ",").zfill(12)
    srt_content += f"{i+1}\n"
    srt_content += (
        f"{start_time.replace('.', ',')} --> {end_time.replace('.', ',')}\n"
    )
    srt_content += f"{utterance['translated_text']}\n\n"
  srt_file_path = os.path.join(output_directory, "translated_subtitles.srt")
  with tf.io.gfile.GFile(srt_file_path, "w") as subtitles_file:
    subtitles_file.write(srt_content)
  return srt_file_path

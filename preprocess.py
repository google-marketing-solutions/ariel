"""Functions related to pre-processing the video with Gemini."""

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
import logging

from google import genai
from google.genai import types
from numpy import number

from models import VoiceData

GEMINI_PROMPT = """Analyse the attached video. Using the response schema,
provide the primary language of the spoken text and a list of voices matched
to the speakers in the order they speak in the video. If a speaker speaks more
than once, only include their voice for the first instance. Match each voice
in the video to a voice available for use with the gemini-2.5-pro-tts API so
that the tone, pitch, and energy are as close as possible. Only use voices
documented as being available for use with gemini-2.5-pro-tts."""


def get_gemini_config() -> dict[str, str|float|type[VoiceData]]:
  """Returns the configuration for the Gemini model."""
  return {
      "response_mime_type": "application/json",
      "response_schema": VoiceData,
      "temperature": 0.2,  # Low temperature to keep the results deterministic
  }


def extract_video_details(
    gcs_path: str, gemini_client: genai.Client, model_string: str
) -> VoiceData:
  """Uses Gemini to extract the details of the given video.

  The language, number of speakers, and a TTS voice that is close the
  original speaker's voice for each speaker is extracted.

  Args:
    gcs_path: the path to the video file on GCS.
    gemini_client: the genai.Client to use when prompting Gemini.
    model_string: the model string for the Gemini model to use.

  Returns:
    A VoiceData object with the extracted metadata.
  """
  video_part = types.Part.from_uri(file_uri=gcs_path, mime_type="video/mp4")

  gemini_response = gemini_client.models.generate_content(
      model=model_string,
      contents=[video_part, GEMINI_PROMPT],
      config=get_gemini_config(),
  )

  data: VoiceData = gemini_response.parsed
  return data

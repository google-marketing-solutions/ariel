"""Functions used to transcribe a video."""

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
from typing import cast

import google.api_core.exceptions
import google.genai
from models import ProcessResponse
from models import Speaker
from models import Utterance
import pydantic


def transcribe_video(
    gcs_video_path: str,
    translate_language: str,
    duration: float,
    genai_client: google.genai.Client,
    gemini_model: str,
) -> tuple[str, list[Speaker], list[Utterance]]:
  """Transcribes and translates a video file using the Gemini model.

  This function sends a video stored in Google Cloud Storage to the Gemini
  model for analysis. Gemini transcribes the spoken dialogue, analyzes its
  tone, and translates the text into the specified target language.
  It extracts detailed information about the video's content, including the
  primary spoken language, a list of identified speakers, and a chronological
  list of transcribed and translated utterances with associated metadata.

  Args:
    gcs_video_path: The GCS URI of the video file to be transcribed.
    translate_language: The target language for translating the video, specified
      as a BCP-47 language code (e.g., "es-ES").
    duration: The total duration of the video in seconds. This is used by
      Gemini to ensure all timestamps fall within the video's length.
    genai_client: An initialized `google.genai.Client` instance.
    gemini_model: The specific Gemini model to use for transcription and
      translation.

  Returns:
    A tuple containing three elements:
    - primary_language (str): The BCP-47 language code of the primary
      spoken language detected in the original video.
    - speaker_list (list[Speaker]): A list of `Speaker` objects, each
      representing a unique speaker identified in the video, with their ID,
      name, gender, and assigned Gemini-TTS voice.
    - utterances (list[Utterance]): A chronological list of `Utterance`
      objects, each containing the original text, translated text, timestamps,
      speaker assignment, and other detailed instructions for text-to-speech.

  Raises:
    google.api_core.exceptions.GoogleAPICallError: If the call to the Gemini API
      fails.
    pydantic.ValidationError: If the response received from the Gemini API
      does not conform to the `ProcessResponse` schema.
  """
  system_instruction = """
    You are an expert audio-visual localization system. Your task is to analyze
    a provided video, transcribe its spoken dialogue, analyze the prosody and
    tone, and translate the text into a target language.

    You must extract the following information and structure it strictly
    according to the provided JSON schema:
    1. Primary Language: Identify the primary spoken language in the video and
       output its BCP-47 language code.
    2. Speaker List: Create a top-level list of all unique speakers in the
       video. Assign a unique `speaker_id`, a `speaker_name`, and `gender`.
       Assign a compatible Gemini-TTS voice name to the `voice` field (e.g.,
       'Achird', 'Aoede', 'Puck'). Do not use regional codes.
    3. Sentence-by-Sentence Transcription: Transcribe the video strictly
       sentence by sentence into `original_text`.
    4. Timestamps: Provide `original_start_time` and `original_end_time` in
       seconds (precision: 2 decimal places).
    5. Speaker Assignment: Assign the correct speaker object to each utterance,
       matching the speakers defined in your top-level Speaker List.
    6. Speaking Instructions: In `speaking_instructions`, write detailed
       instructions for a TTS engine describing tone, pacing, rhythm, pitch,
       inflection, pauses, and emphasis.
    7. Translation Instructions: In `translation_instructions`, describe
       formality, jargon, and cultural context.
    8. Translation: Translate the `original_text` into the Target Language and
       place it in `translated_text`.

    Important Constraints:
    - Only populate fields that can be known *before* generating the translated
      speech.
    - For `translated_start_time` and `translated_end_time`, set to 0.0.
    - For `speaking_rate`, set to 1.0.
    - For `removed` and `muted`, set to False.
    - For `audio_url`, leave as an empty string "".
    - Ensure all timestamps fall within the provided video duration.
    """

  video_part = google.genai.types.Part.from_uri(
      file_uri=gcs_video_path, mime_type="video/mp4"
  )

  user_prompt = f"""
    Please process the attached video based on the following parameters:
    - Video Duration: {duration} seconds
    - Target Language: {translate_language}
    """

  gemini_config = google.genai.types.GenerateContentConfig(
      system_instruction=system_instruction,
      temperature=0.2,
      response_mime_type="application/json",
      response_schema=ProcessResponse,
  )

  logging.info("Sending %s to Gemini for transcription.", gcs_video_path)
  process_response = None
  try:
    response = genai_client.models.generate_content(
        model=gemini_model,
        contents=[video_part, user_prompt],
        config=gemini_config,
    )

    process_response = ProcessResponse.model_validate_json(
        cast(str, response.text)
    )
  except google.api_core.exceptions.GoogleAPICallError as ge:
    logging.exception("Error getting transcription from Gemini: %s", ge)
  except pydantic.ValidationError as ve:
    logging.exception(
        "Error processing the transcription response from Gemini: %s", ve
    )
    raise ve

  if process_response:
    original_language = process_response.primary_language
    speaker_list = process_response.speakers
    utterances = process_response.utterances

    return original_language, speaker_list, utterances

  else:
    return "", [], []

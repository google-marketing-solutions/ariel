# Copyright 2025 Google LLC
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

"""Dubble module for managing the Gen AI interactions."""
import concurrent.futures
import dataclasses
import json
import mimetypes
import os
import pathlib
import sys
import traceback
from typing import Any, Dict, List, Optional
from dubble import av
from dubble.configuration import DubbleConfig
from dubble.dubble import DubbingError
from dubble.dubble import DubbleTTSData
from google import genai
from google.api_core import exceptions as api_exceptions
from google.api_core.exceptions import Cancelled, InvalidArgument
from google.cloud import texttospeech
from google.genai import errors
from google.genai import types
import numpy as np
import pandas as pd


API_VERSION = 'v1'


class GenAIInvoker:
  """Base class for all classes that interact with the Gemini API client."""

  genai_client = None
  tts_client = None

  def __init__(self, config: DubbleConfig) -> None:
    """Initializes the GenAI client if it hasn't been initialized already.

    Args:
      config (DubbleConfig): The configuration object containing the Gemini API
        key.

    Returns:
      None
    """

    if not GenAIInvoker.genai_client:
      GenAIInvoker.genai_client = genai.Client(
          vertexai=True,
          project=config.gcp_project,
          location=config.gcp_project_location,
          http_options=types.HttpOptions(api_version=API_VERSION),
      )
    if not GenAIInvoker.tts_client:
      GenAIInvoker.tts_client = texttospeech.TextToSpeechClient()


class VoiceSelector(GenAIInvoker):
  """Handles voice selection."""

  voices_df = None

  def __init__(self, config: DubbleConfig) -> None:
    """Creates the Embeddings for the voices."""
    super().__init__(config)
    self.voices_df = pd.DataFrame(self.__prepare_voices_for_embeddings())
    self.voices_df.columns = ['gender', 'tone', 'pitch', 'voice_name']
    self.voices_df['embeddings'] = self.voices_df.apply(
        lambda row: self.__embed(self.__get_text_for_embeddings(row), config),
        axis=1,
    )

  def __embed(self, text: str, config: DubbleConfig) -> List[float]:
    """Generates a vector embedding for a given text using the configured model.

    Args:
      text (str): The text string to embed (e.g., 'tone=calm, pitch=low').
      config (DubbleConfig): The configuration object specifying the embedding
        model.

    Returns:
      List[float]: The list of floating-point values representing the embedding
      vector.
    """
    response = self.genai_client.models.embed_content(
        model=config.embedding_model,
        contents=text,
        config=types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT'),
    )

    return response.embeddings[0].values

  def __get_text_for_embeddings(self, line: Dict[str, str]) -> str:
    """Formats voice description metadata into a single string for embedding.

    Args:
      line (Dict[str, str]): A dictionary containing 'tone' and 'pitch'
        information.

    Returns:
      str: The formatted string (e.g., "tone=calm, pitch=low").
    """
    line = {k.lower(): v.lower() for k, v in line.items()}
    return f"tone={line['tone']}, pitch={line['pitch']}"

  def __find_best_voice(
      self, voices_df: pd.DataFrame, query: Dict[str, Any], config: DubbleConfig
  ) -> str:
    """Best matching voice by computing the cosine similarity (via dot product).

    Args:
      voices_df (pd.DataFrame): DataFrame containing all available voices and
        their embeddings.
      query (Dict[str, Any]): Dictionary containing the target speaker's
        'gender', 'tone', and 'pitch'.
      config (DubbleConfig): The configuration object needed for the embedding
        call.

    Returns:
      str: The name of the voice that is the closest match to the query
      description.
    """
    df = voices_df[voices_df['gender'] == query['gender']]

    query_embedding = self.__embed(
        self.__get_text_for_embeddings(query), config
    )

    dot_products = np.dot(np.stack(df['embeddings']), query_embedding)
    max_idx = np.argmax(dot_products)

    return df.iloc[max_idx]['voice_name']

  def __prepare_voices_for_embeddings(self) -> List[Dict[str, Any]]:
    """Converts the global VOICE_OPTIONS dictionary into a list of dictionaries.

    Returns:
      List[Dict[str, Any]]: A list where each dictionary contains voice
      attributes and the 'voice_name'.
    """
    result_list = []
    for name, attributes in DubbleConfig.VOICE_OPTIONS.items():
      attributes['voice_name'] = name
      result_list.append(attributes)

    return result_list

  def find_best_voices(
      self, dubbing_data: List[DubbleTTSData], config: DubbleConfig
  ) -> List[DubbleTTSData]:
    """Matches each utterance's voice description to the best available voice.

    Args:
      dubbing_data (List[DubbleTTSData]): List of utterance data objects to be
        processed.
      config (DubbleConfig): Configuration object containing voice options and
        embedding settings.

    Returns:
      List[DubbleTTSData]: The updated list of utterance data objects, with
      'suggested_voice' populated.
    """

    columns_of_interest = ['gender', 'tone', 'pitch']

    for utterance in dubbing_data:
      # Extract relevant voice description fields from the utterance
      voice_desc = {
          key: dataclasses.asdict(utterance)[key] for key in columns_of_interest
      }
      voice_desc = {k.lower(): v.lower() for k, v in voice_desc.items()}
      suggested_voice = self.__find_best_voice(
          self.voices_df, voice_desc, config
      )

      utterance.voice_name = suggested_voice

    return dubbing_data


class DubbleLLM(GenAIInvoker):
  """Handles all LLM interactions for diarization, translation, and TTS generation."""

  def diarization(self, config: DubbleConfig) -> List[DubbleTTSData]:
    """Performs speech diarization and transcription by submitting the audio file.

    Args:
      config (DubbleConfig): The configuration object containing paths, model
        settings, and prompt templates.

    Returns:
      List[DubbleTTSData]: A list of DubbleTTSData objects parsed from the
                           LLM's structured output.
    """
    try:

      file_path = pathlib.Path(config.vocals_path)
      audio_bytes = None
      mime_type, _ = mimetypes.guess_type(file_path)
      if not mime_type:
        mime_type = 'audio/wav'  # Default if it can't be guessed

      with open(file_path, 'rb') as f:
        audio_bytes = f.read()

      prompt = config.prompt_library['diarization'].format(
          BRAND_NAME=config.brand_name,
          ORIGINAL_LANGUAGE=config.original_language,
      )

      response = self.genai_client.models.generate_content(
          model=config.analysis_model,
          contents=[
              prompt,
              types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
          ],
          config=types.GenerateContentConfig(
              temperature=config.analysis_temperature
          ),
      )

      cleaned_response = (
          response.text.strip()
          .replace('```json', '')
          .replace('```', '')
          .strip()
      )
      dubbing_data = json.loads(cleaned_response)

      return [DubbleTTSData.from_dict(item, config) for item in dubbing_data]
    except (ValueError, Exception) as e:
      traceback.print_exc(file=sys.stdout)
      raise Exception(e) from e

  def translate_utterance(
      self, utterance: DubbleTTSData, config: DubbleConfig
  ) -> DubbleTTSData:
    """Translates a single utterance using the LLM.

    Designed to be called in parallel.

    Args:
      utterance (DubbleTTSData): The data object containing the original text
        and timestamps.
      config (DubbleConfig): The configuration object with translation settings.

    Returns:
      DubbleTTSData: The utterance object updated with the translated text.
    """

    if not utterance.original_text:
      utterance.translated_text = ''
      return utterance

    duration = float(utterance.end) - float(utterance.start)

    translation_prompt = config.prompt_library['translation'].format(
        ORIGINAL_LANGUAGE=utterance.source_language,
        TARGET_LANGUAGE=utterance.target_language,
        DURATION=duration,
        ORIGINAL_TEXT=utterance.original_text,
    )

    try:
      response = self.__call_llm_for_translation_generation(
          translation_prompt, config
      )
      # Assuming response is a ContentPart and has a text attribute
      utterance.translated_text = response.text.strip()
    except api_exceptions.GoogleAPIError:
      utterance.translated_text = '#TRANSLATION_ERROR#'
      traceback.print_exc(file=sys.stdout)
    return utterance

  def translate_utterances(
      self, utterances: List[DubbleTTSData], config: DubbleConfig
  ) -> List[DubbleTTSData]:
    """Translates a list of utterances in parallel using a ThreadPoolExecutor.

    Args:
      utterances (List[DubbleTTSData]): A list of utterance data objects to
        translate.
      config (DubbleConfig): The configuration object for translation and
        concurrency.

    Returns:
      List[DubbleTTSData]: The list of utterance data objects, updated with
      their stranslated text.
    """

    config_list = [config] * len(utterances)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=config.max_concurrent_threads
    ) as executor:
      results = list(
          executor.map(self.translate_utterance, utterances, config_list)
      )

    translated_utterances = results

    return translated_utterances

  def generate_timed_speech_for_utterance(
      self, generation_id: str, utterance: DubbleTTSData, config: DubbleConfig
  ) -> Optional[Any]:
    """Generates Text-to-Speech audio for a single utterance.

    Args:
      generation_id (str): A unique identifier for the current generation run
        (used in filenames).
      utterance (DubbleTTSData): The data object containing the text, duration,
        and voice settings.
      config (DubbleConfig): The configuration object for TTS, refinement
        prompts, and duration limits.

    Returns:
      Optional[Any]: The post-processed audio clip object (e.g., moviepy
      AudioFileClip) if successful,
                     or None if generation fails after all refinement attempts.

    :raises DubbingError: if there is any error
    """

    original_duration = utterance.end - utterance.start
    current_translation = utterance.translated_text
    selected_clip_duration = float('inf')
    selected_audio_clip = None
    audio_file_path = None

    for attempt in range(config.max_refinement_attempts + 1):

      if utterance.tts_prompt:
        final_prompt_template = utterance.tts_prompt.strip()

      try:
        # Assumes utterance is dataclass and asdict works
        tts_prompt = final_prompt_template.format_map(
            dataclasses.asdict(utterance)
        )
      except (KeyError, IndexError):
        tts_prompt = DubbleConfig.DEFAULT_TTS_PROMPT_TEMPLATE.format_map(
            dataclasses.asdict(utterance)
        )

      try:
        audio_file_path = f'clip_{generation_id}_attempt_{attempt}.wav'

        llm_response = self.__call_llm_for_tts_generation(
            tts_prompt, utterance, config
        )
        audio_clip = av.get_audio_file_from_llm_bytes_response(
            audio_file_path, llm_response
        )

        generated_duration = audio_clip.duration
        if (
            generated_duration <= original_duration
            or attempt == config.max_refinement_attempts
        ):
          selected_audio_clip = audio_clip
          break

        else:
          if generated_duration < selected_clip_duration:
            selected_audio_clip = audio_clip
            selected_clip_duration = generated_duration

          percentage_over = (
              (generated_duration - original_duration) / original_duration
          ) * 100

          refinement_prompt = config.prompt_library[
              'translation_refinement'
          ].format(
              ORIGINAL_LANGUAGE=utterance.source_language,
              TARGET_LANGUAGE=utterance.target_language,
              ORIGINAL_TEXT=utterance.original_text,
              CURRENT_TRANSLATION=current_translation,
              GENERATED_DURATION=generated_duration,
              ORIGINAL_DURATION=original_duration,
              PERCENTAGE_OVER=percentage_over,
          )

          # Call LLM to refine translation
          response = self.__call_llm_for_translation_generation(
              refinement_prompt, config
          )
          current_translation = response.text.strip()
          utterance.translated_text = current_translation

      except (api_exceptions.GoogleAPIError, IOError) as e:
        traceback.print_exc(file=sys.stdout)
        raise DubbingError(str(e)) from e
      except Exception as e:  # pylint: disable=broad-except
        traceback.print_exc(file=sys.stdout)
        raise DubbingError(str(e)) from e

    return (
        av.post_process_audio_clip(
            selected_audio_clip, audio_file_path, utterance, config
        ),
        utterance,
    )

  def __call_llm_for_translation_generation(
      self, prompt: str, config: DubbleConfig
  ) -> genai.types.Part:
    """Internal helper to call the LLM for translation/text generation tasks.

    Args:
      prompt (str): The prompt to send to the LLM.
      config (DubbleConfig): Configuration object for model and temperature
        settings.

    Returns:
      genai.types.Part: The content part from the LLM response containing the
      generated text.

    Raises:
      DubbingError: if the model response contains no candidates.
    """

    response = self.genai_client.models.generate_content(
        model=config.analysis_model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            temperature=config.translation_temperature
        ),
    )

    try:
      return response.candidates[0].content.parts[0]
    except errors.APIError as ae:
      raise DubbingError(
          f"""LLM response for Text generation did not contain any candidates.
           {ae.message}"""
      ) from ae
    except (AttributeError, IndexError, TypeError) as e:
      raise DubbingError(
          f"""LLM response for Text generation did not contain any candidates.
           {e}"""
      ) from e

  def __call_llm_for_tts_generation(
      self,
      prompt: str,
      utterance: DubbleTTSData,
      config: DubbleConfig,
      num_retries=3,
      former_error_message='',
  ) -> genai.types.Part:
    """Synthesizes speech from the input text and saves it to a WAV file.

    Args:
        prompt: Styling instructions on how to synthesize the content in the
          text field.
        utterance: The text to synthesize.
        config: The path to save the generated audio file. Defaults to
          "output.mp3".
        num_retries: The number of times to retry the TTS generation on certain
          failures.
        former_error_message: An error message from a previous failed attempt,
          used for logging in subsequent retries.

    Returns:
      genai.types.Part: The content part from the LLM response containing the
      audio data.

    Raises:
      DubbingError: if the model returns no candidates
    """

    if num_retries == 0:
      raise DubbingError(f"""LLM response for Text generation failed.
                         Check your logs, or try again. {former_error_message}
           """)

    num_retries = num_retries - 1

    try:

      synthesis_input = texttospeech.SynthesisInput(
          text=utterance.translated_text,
          prompt=prompt,
          #   custom_pronunciations=custom_pronunciations_container
      )

      voice = texttospeech.VoiceSelectionParams(
          language_code=utterance.target_language,
          name=utterance.voice_name,
          model_name=config.tts_model,
      )

      audio_config = texttospeech.AudioConfig(
          audio_encoding=texttospeech.AudioEncoding.LINEAR16
      )

      response = self.tts_client.synthesize_speech(
          input=synthesis_input, voice=voice, audio_config=audio_config
      )
      return response.audio_content

    except Cancelled as ce:
      return self.__call_llm_for_tts_generation(
          prompt, utterance, config, num_retries, ce.message
      )
    except InvalidArgument as iae:
      if 'harmful' in iae.message:
        return self.__call_llm_for_tts_generation(
            prompt, utterance, config, num_retries, iae.message
        )
      else:
        raise DubbingError(f"""LLM response for Text generation failed.
           {iae}""") from iae

    except errors.APIError as ae:
      raise DubbingError(f"""LLM response for Text generation failed.
           {ae}""") from ae

    except (AttributeError, IndexError, TypeError, ValueError) as e:
      raise DubbingError(f"""LLM response for Text generation failed.
           {e}""") from e

    except Exception as ex:
      raise DubbingError(f"""LLM response for Text generation failed.
           {ex}""") from ex

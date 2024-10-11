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

"""A main file executing an end-to-end dubbing prcoesses of Ariel package from the Google EMEA gTech Ads Data Science."""

import ast
from typing import Sequence
from absl import app
from absl import flags
from ariel.dubbing import Dubber
from ariel.dubbing import get_safety_settings

FLAGS = flags.FLAGS


_INPUT_FILE = flags.DEFINE_string(
    "input_file",
    None,
    "Path to the input video or audio file.",
    required=True,
)
_OUTPUT_DIRECTORY = flags.DEFINE_string(
    "output_directory",
    None,
    "Directory to save output files.",
    required=True,
)
_ADVERTISER_NAME = flags.DEFINE_string(
    "advertiser_name",
    None,
    "Name of the advertiser.",
    required=True,
)
_ORIGINAL_LANGUAGE = flags.DEFINE_string(
    "original_language",
    None,
    "Original language of the ad (ISO 3166-1 alpha-2 country code).",
    required=True,
)
_TARGET_LANGUAGE = flags.DEFINE_string(
    "target_language",
    None,
    "Target language for dubbing (ISO 3166-1 alpha-2 country code).",
    required=True,
)
_NUMBER_OF_SPEAKERS = flags.DEFINE_integer(
    "number_of_speakers",
    1,
    "Number of speakers in the ad.",
)
_GEMINI_TOKEN = flags.DEFINE_string(
    "gemini_token",
    None,
    "Gemini API token.",
)
_HUGGING_FACE_TOKEN = flags.DEFINE_string(
    "hugging_face_token",
    None,
    "Hugging Face API token.",
)
_NO_DUBBING_PHRASES = flags.DEFINE_list(
    "no_dubbing_phrases",
    [],
    "Phrases to exclude in the dubbing process, they orignal utterance will be"
    " used instead.",
)
_DIARIZATION_INSTRUCTIONS = flags.DEFINE_string(
    "diarization_instructions",
    None,
    "Specific instructions for speaker diarization.",
)
_TRANSLATION_INSTRUCTIONS = flags.DEFINE_string(
    "translation_instructions",
    None,
    "Specific instructions for translation.",
)
_MERGE_UTTERANCES = flags.DEFINE_bool(
    "merge_utterances",
    True,
    "Merge utterances with timestamps closer than the threshold.",
)
_MINIMUM_MERGE_THRESHOLD = flags.DEFINE_float(
    "minimum_merge_threshold",
    0.001,
    "Threshold for merging utterances in seconds.",
)
_PREFERRED_VOICES = flags.DEFINE_list(
    "preferred_voices",
    [],
    "Preferred voice names for text-to-speech (e.g., ['Wavenet'] for Google's"
    " TTS or ['Calllum'] for ElevenLabs).",
)
_ASSIGNED_VOICES_OVERRIDE = flags.DEFINE_string(
    "assigned_voices_override",
    None,
    "A mapping between unique speaker IDs and the"
    " full name of their assigned voices. E.g. {'speaker_01':"
    " 'en-US-Casual-K'} or {'speaker_01': 'Charlie'}.",
)
_KEEP_VOICE_ASSIGNMENTS = flags.DEFINE_bool(
    "keep_voice_assignments",
    False,
    "Whether the voices assigned on the first run"
    " should be used again when utilizing the same class instance. It helps"
    " prevents repetitive voice assignment and cloning.",
)
_ADJUST_SPEED = flags.DEFINE_bool(
    "adjust_speed",
    False,
    "Whether to adjust the duration of the dubbed audio files to match the"
    " duration of the source audio files.",
)
_VOCALS_VOLUME_ADJUSTMENT = flags.DEFINE_float(
    "vocals_volume_adjustment",
    5.0,
    "By how much the vocals audio volume should be adjusted",
)
_BACKGROUND_VOLUME_ADJUSTMENT = flags.DEFINE_float(
    "background_volume_adjustment",
    0.0,
    "By how much the background audio volume should be adjusted.",
)
_CLEAN_UP = flags.DEFINE_bool(
    "clean_up",
    False,
    "Delete intermediate files after dubbing.",
)
_GEMINI_MODEL_NAME = flags.DEFINE_string(
    "gemini_model_name",
    "gemini-1.5-flash",
    "Name of the Gemini model to use.",
)
_TEMPERATURE = flags.DEFINE_float(
    "temperature",
    1.0,
    "Controls randomness in generation.",
)
_TOP_P = flags.DEFINE_float(
    "top_p",
    0.95,
    "Nucleus sampling threshold.",
)
_TOP_K = flags.DEFINE_integer(
    "top_k",
    64,
    "Top-k sampling parameter.",
)
_GEMINI_SAFETY_SETTINGS = flags.DEFINE_string(
    "gemini_safety_settings",
    "medium",
    "The indicator of what kind of Gemini safety settings should"
    " be used in the dubbing process. Can be"
    " 'low', 'medium', 'high', or 'none'",
)
_MAX_OUTPUT_TOKENS = flags.DEFINE_integer(
    "max_output_tokens",
    8192,
    "Maximum number of tokens in the generated response.",
)
_ELEVENLABS_TOKEN = flags.DEFINE_string(
    "elevenlabs_token",
    None,
    "ElevenLabs API token.",
)
_ELEVENLABS_CLONE_VOICES = flags.DEFINE_bool(
    "elevenlabs_clone_voices",
    False,
    "Whether to clone source voices. It requires using ElevenLabs API.",
)
_ELEVENLABS_MODEL = flags.DEFINE_string(
    "elevenlabs_model",
    "eleven_multilingual_v2",
    "The ElevenLabs model to use in the Text-To-Speech process.",
)
_ELEVENLABS_REMOVE_CLONED_VOICES = flags.DEFINE_bool(
    "elevenlabs_remove_cloned_voices",
    False,
    "Whether to remove all the voices that"
    " were cloned with ELevenLabs during the dubbing process.",
)
_WITH_VERIFICATION = flags.DEFINE_bool(
    "with_verification",
    True,
    "Verify, and optionally edit, the utterance metadata in the dubbing"
    " process.",
)


def main(argv: Sequence[str]) -> None:
  """Parses command-line arguments and runs the dubbing process."""
  if len(argv) > 1:
    raise app.UsageError("Too many command-line arguments.")

  dubber = Dubber(
      input_file=_INPUT_FILE.value,
      output_directory=_OUTPUT_DIRECTORY.value,
      advertiser_name=_ADVERTISER_NAME.value,
      original_language=_ORIGINAL_LANGUAGE.value,
      target_language=_TARGET_LANGUAGE.value,
      number_of_speakers=_NUMBER_OF_SPEAKERS.value,
      gemini_token=_GEMINI_TOKEN.value,
      hugging_face_token=_HUGGING_FACE_TOKEN.value,
      no_dubbing_phrases=_NO_DUBBING_PHRASES.value,
      diarization_instructions=_DIARIZATION_INSTRUCTIONS.value,
      translation_instructions=_TRANSLATION_INSTRUCTIONS.value,
      merge_utterances=_MERGE_UTTERANCES.value,
      minimum_merge_threshold=_MINIMUM_MERGE_THRESHOLD.value,
      preferred_voices=_PREFERRED_VOICES.value,
      assigned_voices_override=ast.literal_eval(_ASSIGNED_VOICES_OVERRIDE),
      keep_voice_assignments=_KEEP_VOICE_ASSIGNMENTS.value,
      adjust_speed=_ADJUST_SPEED.value,
      vocals_volume_adjustment=_VOCALS_VOLUME_ADJUSTMENT.value,
      background_volume_adjustment=_BACKGROUND_VOLUME_ADJUSTMENT.value,
      clean_up=_CLEAN_UP.value,
      gemini_model_name=_GEMINI_MODEL_NAME.value,
      temperature=_TEMPERATURE.value,
      top_p=_TOP_P.value,
      top_k=_TOP_K.value,
      max_output_tokens=_MAX_OUTPUT_TOKENS.value,
      safety_settings=get_safety_settings(_GEMINI_SAFETY_SETTINGS.value),
      use_elevenlabs=False if _ELEVENLABS_TOKEN.value == "".strip() else True,
      elevenlabs_token=_ELEVENLABS_TOKEN.value,
      elevenlabs_clone_voices=_ELEVENLABS_CLONE_VOICES.value,
      elevenlabs_model=_ELEVENLABS_MODEL.value,
      elevenlabs_remove_cloned_voices=_ELEVENLABS_REMOVE_CLONED_VOICES.value,
      with_verification=_WITH_VERIFICATION.value,
  )
  dubber.dub_ad()


if __name__ == "__main__":
  flags.mark_flag_as_required("input_file")
  flags.mark_flag_as_required("output_directory")
  flags.mark_flag_as_required("advertiser_name")
  flags.mark_flag_as_required("original_language")
  flags.mark_flag_as_required("target_language")
  app.run(main)

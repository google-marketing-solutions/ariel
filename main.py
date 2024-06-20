"""A main file executing an end-to-end dubbing prcoesses of Ariel package from the Google EMEA gTech Ads Data Science."""

import os
from absl import flags
from ariel.dubbing import Dubber

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
    None,
    "Preferred voice names for text-to-speech (e.g., 'Wavenet').",
)
_CLEAN_UP = flags.DEFINE_bool(
    "clean_up",
    False,
    "Delete intermediate files after dubbing.",
)
_PYANNOTE_MODEL = flags.DEFINE_string(
    "pyannote_model",
    "pyannote/speaker-diarization-3.1",
    "Name of the PyAnnote diarization model.",
)
_DIARIZATION_SYSTEM_INSTRUCTIONS = flags.DEFINE_string(
    "diarization_system_instructions",
    None,
    "System instructions for diarization.",
)
_TRANSLATION_SYSTEM_INSTRUCTIONS = flags.DEFINE_string(
    "translation_system_instructions",
    None,
    "System instructions for translation.",
)
_HUGGING_FACE_TOKEN = flags.DEFINE_string(
    "hugging_face_token",
    None,
    "Hugging Face API token.",
)
_GEMINI_TOKEN = flags.DEFINE_string(
    "gemini_token",
    None,
    "Gemini API token.",
)
_MODEL_NAME = flags.DEFINE_string(
    "model_name",
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
_MAX_OUTPUT_TOKENS = flags.DEFINE_integer(
    "max_output_tokens",
    8192,
    "Maximum number of tokens in the generated response.",
)
_RESPONSE_MIME_TYPE = flags.DEFINE_string(
    "response_mime_type",
    "text/plain",
    "MIME type of the generated response.",
)


def main():
  """Parses command-line arguments and runs the dubbing process."""
  flags.mark_flag_as_required("input_file")
  flags.mark_flag_as_required("output_directory")
  flags.mark_flag_as_required("advertiser_name")
  flags.mark_flag_as_required("original_language")
  flags.mark_flag_as_required("target_language")
  flags.parse_flags()
  if not os.path.exists(_OUTPUT_DIRECTORY.value):
    os.makedirs(_OUTPUT_DIRECTORY.value)
  dubber = Dubber(
      input_file=_INPUT_FILE.value,
      output_directory=_OUTPUT_DIRECTORY.value,
      advertiser_name=_ADVERTISER_NAME.value,
      original_language=_ORIGINAL_LANGUAGE.value,
      target_language=_TARGET_LANGUAGE.value,
      number_of_speakers=_NUMBER_OF_SPEAKERS.value,
      diarization_instructions=_DIARIZATION_INSTRUCTIONS.value,
      translation_instructions=_TRANSLATION_INSTRUCTIONS.value,
      merge_utterances=_MERGE_UTTERANCES.value,
      minimum_merge_threshold=_MINIMUM_MERGE_THRESHOLD.value,
      preferred_voices=_PREFERRED_VOICES.value,
      clean_up=_CLEAN_UP.value,
      pyannote_model=_PYANNOTE_MODEL.value,
      diarization_system_instructions=_DIARIZATION_SYSTEM_INSTRUCTIONS.value,
      translation_system_instructions=_TRANSLATION_SYSTEM_INSTRUCTIONS.value,
      hugging_face_token=_HUGGING_FACE_TOKEN.value,
      gemini_token=_GEMINI_TOKEN.value,
      model_name=_MODEL_NAME.value,
      temperature=_TEMPERATURE.value,
      top_p=_TOP_P.value,
      top_k=_TOP_K.value,
      max_output_tokens=_MAX_OUTPUT_TOKENS.value,
      response_mime_type=_RESPONSE_MIME_TYPE.value,
  )
  dubber.dub_ad()


if __name__ == "__main__":
  main()

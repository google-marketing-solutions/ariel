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

"""Dubble module for managing the library configuration."""

import dataclasses
import json
from typing import Any, Dict, Optional


@dataclasses.dataclass
class DubbleConfig:
  """Input data for the bulk process.

  Attributes
  ----------
  prompt_library: list of details of each product not yet processed


  Methods

  to_dict:
      Returns a dict reprentation of the attributes.
  """

  prompt_library: Dict[str, Any]

  SYNC_MODES = [
      'Natural Duration',
      'Trim to Fit',
      'Align to End',
      'Speed Up to Fit',
  ]

  VOICE_OPTIONS = {
      'Zephyr': {'gender': 'female', 'tone': 'Bright', 'pitch': 'Higher'},
      'Puck': {'gender': 'male', 'tone': 'Upbeat', 'pitch': 'Middle'},
      'Charon': {'gender': 'male', 'tone': 'Informative', 'pitch': 'Lower'},
      'Kore': {'gender': 'female', 'tone': 'Firm', 'pitch': 'Middle'},
      'Fenrir': {
          'gender': 'female',
          'tone': 'Excitable',
          'pitch': 'Lower middle',
      },
      'Leda': {'gender': 'female', 'tone': 'Youthful', 'pitch': 'Higher'},
      'Orus': {'gender': 'male', 'tone': 'Firm', 'pitch': 'Lower middle'},
      'Aoede': {'gender': 'female', 'tone': 'Breezy', 'pitch': 'Middle'},
      'Callirrhoe': {
          'gender': 'female',
          'tone': 'Easy-going',
          'pitch': 'Middle',
      },
      'Autonoe': {'gender': 'female', 'tone': 'Bright', 'pitch': 'Middle'},
      'Enceladus': {'gender': 'male', 'tone': 'Breathy', 'pitch': 'Lower'},
      'Iapetus': {'gender': 'male', 'tone': 'Clear', 'pitch': 'Lower middle'},
      'Umbriel': {
          'gender': 'male',
          'tone': 'Easy-going',
          'pitch': 'Lower middle',
      },
      'Algieba': {'gender': 'male', 'tone': 'Smooth', 'pitch': 'Lower'},
      'Despina': {'gender': 'female', 'tone': 'Smooth', 'pitch': 'Middle'},
      'Erinome': {'gender': 'female', 'tone': 'Clear', 'pitch': 'Middle'},
      'Algenib': {'gender': 'male', 'tone': 'Gravelly', 'pitch': 'Lower'},
      'Rasalgethi': {
          'gender': 'male',
          'tone': 'Informative',
          'pitch': 'Middle',
      },
      'Laomedeia': {'gender': 'female', 'tone': 'Upbeat', 'pitch': 'Higher'},
      'Achernar': {'gender': 'female', 'tone': 'Soft', 'pitch': 'Higher'},
      'Alnilam': {'gender': 'male', 'tone': 'Firm', 'pitch': 'Lower middle'},
      'Schedar': {'gender': 'male', 'tone': 'Even', 'pitch': 'Lower middle'},
      'Gacrux': {'gender': 'female', 'tone': 'Mature', 'pitch': 'Middle'},
      'Pulcherrima': {'gender': 'female', 'tone': 'Forward', 'pitch': 'Middle'},
      'Achird': {'gender': 'male', 'tone': 'Friendly', 'pitch': 'Lower middle'},
      'Zubenelgenubi': {
          'gender': 'female',
          'tone': 'Casual',
          'pitch': 'Lower middle',
      },
      'Vindemiatrix': {'gender': 'female', 'tone': 'Gentle', 'pitch': 'Middle'},
      'Sadachbia': {'gender': 'male', 'tone': 'Lively', 'pitch': 'Lower'},
      'Sadaltager': {
          'gender': 'male',
          'tone': 'Knowledgeable',
          'pitch': 'Middle',
      },
      'Sulafat': {'gender': 'female', 'tone': 'Warm', 'pitch': 'Middle'},
  }

  DEFAULT_PROMPT_DIARIZATION = """Note that '{BRAND_NAME}' is the name of the brand for this vocal track from a video advertisement.
        The original audio is in {ORIGINAL_LANGUAGE}.

        Based on the attached audio file, perform speaker diarization and analyze the speech.
        For each utterance in the audio:
        1.  **Identify the speaker** and assign a consistent label, like 'SPEAKER_01', 'SPEAKER_02', etc.
        2.  Provide the start and end timestamps in seconds. **An utterance should be a distinct segment of speech, typically a sentence or a complete phrase, separated by a noticeable pause.**
        3.  Transcribe the voice from the original language ({ORIGINAL_LANGUAGE}).
        4.  Describe the voice in a way that can be used to configure a Text-to-Speech (TTS) system.

        5. Focus on these characteristics for the voice description:
        * `gender` (string): Male, Female.
        * `age` (string): e.g., Young Adult, Middle-aged, Senior.
        * `pitch` (string): e.g., Low, Lower-middle, Medium, Higher-middle, High.
        * `tone` (string): Select the most fitting from the list (e.g., Energetic, Calm, Authoritative, Friendly, Bright, Upbeat, Informative, Firm, Excitable, Youthful, Breezy, Easy-going, Breathy, Clear, Smooth, Gravelly, Soft, Mature, Forward, Casual, Gentle, Lively, Knowledgeable, Warm, Even).
        * `vocal_style_prompt` (string): A free-form, narrative description of the vocal performance. This prompt should capture the nuanced style, emotion, and delivery of the speaker. For example: 'A friendly and enthusiastic young adult male voice, speaking with a clear and confident tone, as if explaining a new product to an excited customer.' or 'A calm, mature female voice with a smooth, reassuring delivery, like a trusted advisor offering gentle guidance.'**

        Return the result as a valid JSON array, where each object contains 'speaker_id', 'start', 'end', 'original_text', 'gender', 'age', 'pitch', 'tone', and 'vocal_style_prompt'.
        Do not include any text, code block formatting, or markdown outside of the JSON array itself."""

  DEFAULT_PROMPT_TRANSLATION = """Translate the following text from {ORIGINAL_LANGUAGE} to {TARGET_LANGUAGE}.
        This is a time-constrained translation. The goal is to create a translated text that can be spoken naturally in approximately {DURATION:.2f} seconds.
        Prioritize preserving the core message with natural pacing over a literal, word-for-word translation. Use concise phrasing where necessary to fit the timing.
        Return only the translated text, with no extra commentary or formatting.

        Original text: "{ORIGINAL_TEXT}"
        """

  DEFAULT_PROMPT_TRANSLATION_REFINEMENT = """The following text from {ORIGINAL_LANGUAGE}, when translated to {TARGET_LANGUAGE}, is too long to fit its time slot.
        Original text: "{ORIGINAL_TEXT}"\nPrevious, too-long translation: "{CURRENT_TRANSLATION}"
        (This took {GENERATED_DURATION:.2f}s to say, but needs to fit in {ORIGINAL_DURATION:.2f}s, meaning it is {PERCENTAGE_OVER:.0f}% too long).
        Please provide a more concise version of the translation that preserves the core meaning but can be spoken more quickly.
        Return only the new, shorter translated text."""

  DEFAULT_TTS_PROMPT_TEMPLATE = """Read with {vocal_style_prompt}."""

  # Models
  analysis_model: str
  embedding_model: str
  tts_model: str

  # Temperature Controls
  analysis_temperature: float
  translation_temperature: float
  tts_temperature: float

  # Speed Cap Control
  feature_speed_up_enable: bool
  max_speed_up_ratio: float

  # Brand and API Key
  brand_name: str
  gcp_project: str
  gcp_project_location: str

  # Translation Refinement
  feature_refinement_enable: bool
  max_refinement_attempts: int

  # Default Merge Strategy
  prompt_edit: bool

  # Concurrency
  max_concurrent_threads: int

  # Language and Context
  original_language: str
  target_language: str

  # Input/Output
  vocals_path: str
  background_path: str
  video_file_path: str
  video_file_path_input: str
  script: str
  output_bucket: str
  prompt_library: dict[str, str]
  music_volume: float
  speech_volume: float

  # Helper function to assign value or default
  def get_value(self, param: Any, default: Any) -> Any:
    """Returns param if not None, otherwise returns default."""
    return param if param is not None else default

  def __init__(
      self,
      # Models
      analysis_model: Optional[str] = None,
      embedding_model: Optional[str] = None,
      tts_model: Optional[str] = None,
      # Temperature Controls
      analysis_temperature: Optional[float] = None,
      translation_temperature: Optional[float] = None,
      tts_temperature: Optional[float] = None,
      # Speed Cap Control
      feature_speed_up_enable: Optional[bool] = None,
      max_speed_up_ratio: Optional[float] = None,
      brand_name: Optional[str] = None,
      gcp_project: Optional[str] = None,
      gcp_project_location: Optional[str] = None,
      # Translation Refinement
      feature_refinement_enable: Optional[bool] = None,
      max_refinement_attempts: Optional[int] = None,
      # Prompt Strategy
      prompt_edit: Optional[bool] = None,
      # Concurrency
      max_concurrent_threads: Optional[int] = None,
      # Language and Context
      original_language: Optional[str] = None,
      target_language: Optional[str] = None,
      # Input/Output
      background_path: Optional[str] = None,
      vocals_path: Optional[str] = None,
      video_file_path: Optional[str] = None,
      video_file_path_input: Optional[str] = None,
      script: Optional[str] = None,
      output_bucket: Optional[str] = None,
      output_local_path: Optional[str] = None,
      prompt_library: Optional[dict[str, str]] = None,
      music_volume: Optional[float] = 0.6,
      speech_volume: Optional[float] = 0.5,
  ):

    # --- Models ---
    self.analysis_model = self.get_value(
        analysis_model, 'models/gemini-2.5-pro'
    )
    self.embedding_model = self.get_value(
        embedding_model, 'gemini-embedding-001'
    )
    self.tts_model = self.get_value(
        tts_model, 'models/gemini-2.5-pro-preview-tts'
    )

    # --- Temperature Controls ---
    self.analysis_temperature = self.get_value(analysis_temperature, 0.2)
    self.translation_temperature = self.get_value(translation_temperature, 0.4)
    self.tts_temperature = self.get_value(tts_temperature, 1.0)

    # --- Speed Cap Control ---
    self.feature_speed_up_enable = self.get_value(feature_speed_up_enable, True)
    self.max_speed_up_ratio = self.get_value(max_speed_up_ratio, 1.2)

    # --- Brand and API Key ---
    self.brand_name = self.get_value(brand_name, '')
    self.gcp_project = self.get_value(gcp_project, '')
    self.gcp_project_location = self.get_value(gcp_project_location, '')

    # --- Translation Refinement (Using the defaults in your template) ---
    self.feature_refinement_enable = self.get_value(
        feature_refinement_enable, False
    )
    self.max_refinement_attempts = self.get_value(max_refinement_attempts, 0)

    # --- Prompt Strategy ---
    self.prompt_edit = self.get_value(prompt_edit, True)

    # --- Concurrency ---
    self.max_concurrent_threads = self.get_value(max_concurrent_threads, 1)

    # --- Language and Context ---
    self.original_language = self.get_value(original_language, 'es-ES')
    self.target_language = self.get_value(target_language, 'en-US')

    # --- Input/Output ---
    self.vocals_path = self.get_value(vocals_path, '')
    self.background_path = self.get_value(background_path, '')
    self.video_file_path = self.get_value(video_file_path, '')
    self.video_file_path_input = self.get_value(video_file_path_input, '')
    self.script = self.get_value(script, '')
    self.prompt_library = self.get_value(
        prompt_library,
        {
            'diarization': DubbleConfig.DEFAULT_PROMPT_DIARIZATION,
            'translation': DubbleConfig.DEFAULT_PROMPT_TRANSLATION,
            'translation_refinement': (
                DubbleConfig.DEFAULT_PROMPT_TRANSLATION_REFINEMENT
            ),
            'tts_prompt_template': DubbleConfig.DEFAULT_TTS_PROMPT_TEMPLATE,
        },
    )

    self.output_bucket = self.get_value(output_bucket, '')
    self.output_local_path = self.get_value(output_local_path, '.')
    self.music_volume = self.get_value(music_volume, 0.6)
    self.speech_volume = self.get_value(speech_volume, 0.5)

  def to_json(self) -> str:
    """Returns a JSON string representation of the ProcessedImage."""

    return json.dumps(dataclasses.asdict(self))

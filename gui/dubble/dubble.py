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

"""The module of Dubble package containing class definition for data exchange."""

import dataclasses
import json
from typing import Any
from dubble.configuration import DubbleConfig


class DubbingError(Exception):
  """A class to manage the exceptions within the library."""

  pass


@dataclasses.dataclass
class DubbleTTSData:
  """A class to pass the TTS data between objects and functions."""

  speaker_id: str
  start: float
  end: float
  source_language: str
  target_language: str
  original_text: str
  translated_text: str
  tts_prompt: str
  special_instructions: str
  voice_name: str
  sync_mode: str
  gender: str
  age: str
  pitch: str
  tone: str
  vocal_style_prompt: str
  suggested_voice: str

  @classmethod
  def from_dict(
      cls, data: dict[str, Any], config: DubbleConfig
  ) -> 'DubbleTTSData':
    """Creates a DubbleTTSData instance from a dictionary of data.

    Args:
        data: A dictionary containing initial values for the segment attributes.
          Default values are used if a key is missing.
        config: A DubbleConfig instance containing the default values for the
          segment attributes.

    Returns:
        A new DubbleTTSData instance.
    """
    speaker_id = data.get('speaker_id', 'SPEAKER_01')
    start = float(data.get('start', -1.0))
    end = float(data.get('end', -1.0))
    source_language = (
        config.original_language
        if not data.get('source_language', None)
        else data.get('source_language', None)
    )
    target_language = (
        config.target_language
        if not data.get('target_language', None)
        else data.get('target_language', None)
    )
    original_text = data.get('original_text', '')
    translated_text = data.get('translated_text', '')
    tts_prompt = data.get('tts_prompt', config.DEFAULT_TTS_PROMPT_TEMPLATE)
    special_instructions = data.get('special_instructions', '')
    voice_name = data.get('voice_name', 'Zephyr')
    sync_mode = data.get('sync_mode', 'Natural Duration')
    gender = data.get('gender', 'Male')
    age = data.get('age', 'Young')
    pitch = data.get('pitch', '')
    tone = data.get('tone', '')
    vocal_style_prompt = data.get('vocal_style_prompt', '')
    suggested_voice = data.get('suggested_voice', '')

    return cls(
        speaker_id=speaker_id,
        start=start,
        end=end,
        source_language=source_language,
        target_language=target_language,
        original_text=original_text,
        translated_text=translated_text,
        tts_prompt=tts_prompt,
        special_instructions=special_instructions,
        voice_name=voice_name,
        sync_mode=sync_mode,
        gender=gender,
        age=age,
        pitch=pitch,
        tone=tone,
        vocal_style_prompt=vocal_style_prompt,
        suggested_voice=suggested_voice,
    )

  def to_json(self) -> str:
    """Returns a JSON string representation of the TTS Data."""

    return json.dumps(dataclasses.asdict(self))

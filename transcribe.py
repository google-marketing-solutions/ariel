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

import dataclasses
import json
import logging

from faster_whisper import WhisperModel
import google.genai
from google.genai import types
from pydantic import TypeAdapter
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_fixed



@dataclasses.dataclass
class TranscribeSegment:
  """Represents one spoken segment in a transcription.

  Attributes:
    speaker_id: a unique ID for the speaker.
    gender: the gender of the speaker.
    transcript: the transcription of the spoken text.
    tone: a textual description of the tone used.
    start_time: the time in seconds from the start of the clip when the segment
      starts.
    end_time: the time in seconds from the start of the clip when the segment
      ends.
  """

  speaker_id: str
  gender: str
  transcript: str
  tone: str
  start_time: float
  end_time: float

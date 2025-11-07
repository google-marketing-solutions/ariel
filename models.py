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
"""The models used with FastAPI for data interchange."""

from pydantic import BaseModel

class Speaker(BaseModel):
    """A speaker in a video.

  This tracks a speaker in a video, with which speaker in the video it
  represents and a Chirp voice that will be used when using text-to-speech.

  Attributes:
    speaker_number: the number of the speaker in order that they appear (i.e.
        first == 1, second == 2)
    voice: the Chirp voice to used with text-to-speech for this speaker's
        utterances.
  """

    speaker_id: str
    voice: str


class Utterance(BaseModel):
    """One spoken utterance from a video.

  This is used to represent all of the information about an utterance to be
  translated.

  Attributes:
    id: a unique to the file id for this utterance.
    original_text: a transcription of the original audio.
    translated_text: the text translation to be used.
    speaker: the speaker to use when generating audio.
    start_time: the time in the output video the utterance should start.
    end_time: the time in the output video that the utterance will end.
    is_dirty: whether the audio for this utterance has been generated. Defaults
        to true, but will be changed if the text is updated.
    audio_url: a URL pointing to the generated audio for the translation.
  """

    id: str
    original_text: str
    translated_text: str
    instructions: str
    speaker: Speaker
    original_start_time: float
    original_end_time: float
    translated_start_time: float
    translated_end_time: float
    removed: bool
    audio_url: str = ""


class Video(BaseModel):
    """Represents a video to be translated.

  Attributes:
    video_id: a unique id representing a single video and translation.
    original_language: the language the of the voice over in the video.
    translate_language: the language to translate the video to.
    prompt_enhancements: additional information to provide Gemini when
        translating the transcription.
    speakers: the speakers to use in the final translated video.
    utterances: a list of the individual utterances for the video.
  """

    video_id: str
    original_language: str
    translate_language: str
    prompt_enhancements: str
    speakers: list[Speaker]
    utterances: list[Utterance]

  
class RegenerateRequest(BaseModel):
  """Used to request a new text translation.

  Attributes:
    video: the video being processed
    utterance: the index of the utterance to retranslate
    instructions: additional instructions to guide the translation (defaults to
        empty)
  """

  video: Video
  utterance: int
  instructions: str = ""


class RegenerateResponse(BaseModel):
  """Used to respond to a translation request.

  Attributes:
    translated_text: the translated text.
  """

  translated_text: str
  audio_url: str
  duration: float

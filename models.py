"""The models used with FastAPI for data interchange."""

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

from pydantic import BaseModel


class Speaker(BaseModel):
  """A speaker in a video.

  This tracks a speaker in a video, with which speaker in the video it
  represents and a Chirp voice that will be used when using text-to-speech.

  Attributes:
    speaker_id: a unique id for the speaker in a video.
    voice: the TTS voice to used with text-to-speech for this speaker's
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
    instructions: additional instructions to pass to Gemini.
    speaker: the speaker to use when generating audio.
    original_start_time: the time in the original video the utterance started.
    original_end_time: the time in the original video that the utterance ended.
    translated_start_time: the time in the translated video that the utterance
        will start.
    translated_end_time: the time in the translated video the utterance will
        end.
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
    model_name: either flash or pro, which signals which version of Gemini to
        use.
    tts_mo
  """

  video_id: str
  original_language: str
  translate_language: str
  prompt_enhancements: str
  speakers: list[Speaker]
  utterances: list[Utterance]
  model_name: str = ""
  tts_model_name: str = ""


class RegenerateRequest(BaseModel):
  """Used to request a new text translation and audio generation.

  Attributes:
    video: the video being processed
    utterance: the index of the utterance to re-translate
    instructions: additional instructions to guide the translation (defaults to
      empty)
  """

  video: Video
  utterance: int
  instructions: str = ""


class RegenerateResponse(BaseModel):
  """Used to respond to a regenerate request.

  Attributes:
    translated_text: the translated text.
    audio_url: a URL pointed to the updated audio file.
    duration: the duration of the updated audio file.
  """

  translated_text: str
  audio_url: str
  duration: float

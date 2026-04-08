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

import datetime
from enum import StrEnum

from pydantic import BaseModel
from pydantic import Field


class GenderEnum(StrEnum):
  """Represents the gender of a Speaker."""

  MALE = "male"
  FEMALE = "female"
  NEUTRAL = "neutral"


class Speaker(BaseModel):
  """A speaker in a video.

  This tracks a speaker in a video, with which speaker in the video it
  represents and a TTS voice that will be used when using text-to-speech.

  Attributes:
    speaker_id: A unique id for the speaker in a video.
    voice: The TTS voice to used with text-to-speech for this speaker's
      utterances.
    speaker_name: A human readable name for the speaker.
    gender: The speaker's gender.
  """

  speaker_id: str = Field(
      description=(
          "A unique ID for the speaker in the video, created sequentially in"
          " the order the speakers speak."
      )
  )
  voice: str = Field(
      description=(
          "The name of the Gemini-TTS voice (e.g., 'Achird', 'Aoede'). Do not"
          " use regional codes like 'en-US-Neural2'."
      )
  )
  speaker_name: str = Field(
      description="A human readable name for the speaker."
  )
  gender: GenderEnum = Field(
      description=(
          "The gender of the speaker. Must be one of the predefined options."
      )
  )


class Utterance(BaseModel):
  """One spoken utterance from a video.

  This is used to represent all of the information about an utterance to be
  translated.

  Attributes:
    id: A unique to the file id for this utterance.
    original_text: A transcription of the original audio.
    translated_text: The text translation to be used.
    translation_instructions: Additional instructions for translation.
    speaker: The TTS speaker to use when generating audio.
    speaking_instructions: Additional instructions on how to speak.
    original_start_time: The time in the original video the utterance started.
    original_end_time: The time in the original video that the utterance ended.
    translated_start_time: The time in the translated video that the utterance
      will start.
    translated_end_time: The time in the translated video the utterance will
      end.
    speaking_rate: A factor (between 0.25 and 2.0) to send to Gemini TTS for how
      quickly to speak.
    removed: If True, no audio is used for the utterance.
    muted: If True, the original audio is used for the utterance.
    audio_url: A URL pointing to the generated audio for the translation.
  """

  id: str = Field(description="A unique to the file id for this utterance.")
  original_text: str = Field(
      description="A transcription of the original audio."
  )
  translated_text: str = Field(description="The text translation to be used.")
  translation_instructions: str = Field(
      default="", description="Additional instructions for translation."
  )
  speaker: Speaker = Field(
      description="The TTS speaker to use when generating audio."
  )
  speaking_instructions: str = Field(
      default="", description="Additional instructions on how to speak."
  )
  original_start_time: float = Field(
      description="The time in the original video the utterance started."
  )
  original_end_time: float = Field(
      description="The time in the original video that the utterance ended."
  )
  translated_start_time: float = Field(
      description=(
          "The time in the translated video that the utterance will start."
      )
  )
  translated_end_time: float = Field(
      description="The time in the translated video the utterance will end."
  )
  speaking_rate: float = Field(
      default=1.0,
      description=(
          "A factor (between 0.25 and 2.0) to send to Gemini TTS for how"
          " quickly to speak."
      ),
      ge=0.25,
      le=2.0,
  )
  removed: bool = Field(
      default=False, description="If True, no audio is used for the utterance."
  )
  muted: bool = Field(
      default=False,
      description="If True, the original audio is used for the utterance.",
  )
  audio_url: str = Field(
      default="",
      description="A URL pointing to the generated audio for the translation.",
  )


class ProcessResponse(BaseModel):
  """Wrapper class to capture the entire video analysis including the BCP-47 code."""

  primary_language: str = Field(
      description="The BCP-47 code of the primary spoken language in the video."
  )
  speakers: list[Speaker] = Field(
      description="A list of the unique speakers identified in the video."
  )
  utterances: list[Utterance] = Field(
      description=(
          "A list of all transcribed and translated utterances, ordered"
          " chronologically."
      )
  )


class Video(BaseModel):
  """Represents a video to be translated.

  Attributes:
    video_id: A unique id representing a single video and translation.
    original_language: The language the of the voice over in the video.
    translate_language: The language to translate the video to.
    prompt_enhancements: Additional information to provide Gemini when
      translating the transcription.
    speakers: The speakers to use in the final translated video.
    utterances: A list of the individual utterances for the video.
    model_name: The Gemini model used to transcribe and translate the video.
    tts_model_name: The model used for Text-to-speech
  """

  video_id: str
  original_language: str
  translate_language: str
  prompt_enhancements: str = ""
  speakers: list[Speaker]
  utterances: list[Utterance]
  model_name: str
  tts_model_name: str


class RegenerateRequest(BaseModel):
  """Used to request a new text translation and audio generation.

  Attributes:
    video: The video being processed
    utterance: The index of the utterance to re-translate
    instructions: Additional instructions to guide the translation (defaults to
      empty)
    speaking_rate: The factor to speed up the default speaking rate by.
  """

  video: Video = Field(description="The video being processed")
  utterance: int = Field(
      description="The index of the utterance to re-translate"
  )
  instructions: str = Field(
      default="",
      description=(
          "Additional instructions to guide the translation (defaults to empty)"
      ),
  )
  speaking_rate: float = Field(
      default=1.0,
      description="The factor to speed up the default speaking rate by.",
  )


class RegenerateResponse(BaseModel):
  """Used to respond to a regenerate request.

  Attributes:
    translated_text: The translated text.
    audio_url: A URL pointed to the updated audio file.
    duration: The duration of the updated audio file.
  """

  translated_text: str = Field(description="The translated text.")
  audio_url: str = Field(description="A URL pointed to the updated audio file.")
  duration: float = Field(description="The duration of the updated audio file.")


class GenerateVideoRequest(BaseModel):
  """Used to request the completed video.

  Attributes:
    video: The video to generate.
    original_video_url: The URL to the original video.
  """

  video: Video = Field(description="The video to generate.")
  original_video_url: str = Field(
      default="", description="The URL to the original video."
  )


class VideoMetadata(BaseModel):
  """Represents the stored for a video project.

  Attributes:
    name: The file name of the translated video.
    url: The URL to edit the project.
    original_video_url: The URL where the original video is saved.
    download_url: The URL to download the translated video.
    created_at: When the project was created.
    original_language: The language of the original video.
    translate_langiage: The language the video was translated to.
    duration: The duration of the translated video (may be longer than the
      original).
    speakers: The list of speakers in the video.
    video_id: The UUID used to identify the project.
    has_metadata: True if the metadata JSON file has been saved.
  """

  name: str = Field(description="The file name of the translated video.")
  url: str = Field(description="The URL to edit the project.")
  original_video_url: str = Field("The URL where the original video is saved.")
  download_url: str = Field(
      description="The URL to download the translated video."
  )
  created_at: datetime.datetime = Field(
      description="When the project was created."
  )
  original_language: str = Field(
      description="The language of the original video."
  )
  translate_language: str = Field(
      description="The language the video was translated to."
  )
  duration: float = Field(
      description=(
          "The duration of the translated video (may be longer than the"
          " original)."
      )
  )
  speakers: list[Speaker] = Field(
      description="The list of speakers in the video."
  )
  video_id: str = Field(description="The UUID used to identify the project.")
  has_metadata: bool = Field(
      description="True if the metadata JSON file has been saved."
  )

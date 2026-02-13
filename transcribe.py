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


# Load the fasterwhisper model only once to save on processing time.
logging.info("Loading Whisper model...")
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
logging.info("Whisper model loaded.")

VOICE_OPTIONS = {
    "Zephyr": {"gender": "female", "tone": "Bright", "pitch": "Higher"},
    "Puck": {"gender": "male", "tone": "Upbeat", "pitch": "Middle"},
    "Charon": {"gender": "male", "tone": "Informative", "pitch": "Lower"},
    "Kore": {"gender": "female", "tone": "Firm", "pitch": "Middle"},
    "Fenrir": {
        "gender": "female",
        "tone": "Excitable",
        "pitch": "Lower middle",
    },
    "Leda": {"gender": "female", "tone": "Youthful", "pitch": "Higher"},
    "Orus": {"gender": "male", "tone": "Firm", "pitch": "Lower middle"},
    "Aoede": {"gender": "female", "tone": "Breezy", "pitch": "Middle"},
    "Callirrhoe": {
        "gender": "female",
        "tone": "Easy-going",
        "pitch": "Middle",
    },
    "Autonoe": {"gender": "female", "tone": "Bright", "pitch": "Middle"},
    "Enceladus": {"gender": "male", "tone": "Breathy", "pitch": "Lower"},
    "Iapetus": {"gender": "male", "tone": "Clear", "pitch": "Lower middle"},
    "Umbriel": {
        "gender": "male",
        "tone": "Easy-going",
        "pitch": "Lower middle",
    },
    "Algieba": {"gender": "male", "tone": "Smooth", "pitch": "Lower"},
    "Despina": {"gender": "female", "tone": "Smooth", "pitch": "Middle"},
    "Erinome": {"gender": "female", "tone": "Clear", "pitch": "Middle"},
    "Algenib": {"gender": "male", "tone": "Gravelly", "pitch": "Lower"},
    "Rasalgethi": {
        "gender": "male",
        "tone": "Informative",
        "pitch": "Middle",
    },
    "Laomedeia": {"gender": "female", "tone": "Upbeat", "pitch": "Higher"},
    "Achernar": {"gender": "female", "tone": "Soft", "pitch": "Higher"},
    "Alnilam": {"gender": "male", "tone": "Firm", "pitch": "Lower middle"},
    "Schedar": {"gender": "male", "tone": "Even", "pitch": "Lower middle"},
    "Gacrux": {"gender": "female", "tone": "Mature", "pitch": "Middle"},
    "Pulcherrima": {"gender": "female", "tone": "Forward", "pitch": "Middle"},
    "Achird": {"gender": "male", "tone": "Friendly", "pitch": "Lower middle"},
    "Zubenelgenubi": {
        "gender": "female",
        "tone": "Casual",
        "pitch": "Lower middle",
    },
    "Vindemiatrix": {"gender": "female", "tone": "Gentle", "pitch": "Middle"},
    "Sadachbia": {"gender": "male", "tone": "Lively", "pitch": "Lower"},
    "Sadaltager": {
        "gender": "male",
        "tone": "Knowledgeable",
        "pitch": "Middle",
    },
    "Sulafat": {"gender": "female", "tone": "Warm", "pitch": "Middle"},
}


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


def annotate_transcript(
    client: google.genai.Client,
    model_name: str,
    gcs_uri: str,
    num_speakers: int,
    script: str,
    mime_type: str,
) -> list[TranscribeSegment]:
  """Annotates an audio transcription using Gemini.

  Gemini is provided an audio file and it's transcription and asked to annotate
  the transcription with the speaker, the start and end times of each utterance,
  the gender of the speaker, and the tone of voice used.

  Args:
    client: the genai Client to use when querying Gemini.
    model_name: the Gemini model string to use.
    gcs_uri: the URI of the audio file on GCS.
    num_speakers: the number of speakers in the audio.
    script: the transcript of the audio.
    mime_type: the mime-type of the audio (e.g. audio/wav).

  Returns:
    a list of annotated transcription segments.
  """
  prompt = f"""
    I am providing you an audio file alongside its transcript with timestamps.

    Your Task:
    Identify different speakers in the audio and attempt to infer their gender.
    There are {num_speakers} speakers. If you detect more, assume they are the same person.

    For each sentence, make sure to use the provided start and end times from
    the transcript. This is ABSOLUTELY CRITICAL. Output them exactly as they were provided.

    For each utterance of the transcript, describe the tone of voice used in a short sentence.
    When assigning speaker_id, use the format "speaker_x", where x is the number
    of the speaker in the order they are first heard in the video, starting at 1.

    Transcript:
    {script}
    """
  media = types.Part.from_uri(file_uri=gcs_uri, mime_type=mime_type)

  @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
  def call_gemini():
    return client.models.generate_content(
        model=model_name,
        contents=[media, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker_id": {"type": "string"},
                        "gender": {"type": "string"},
                        "transcript": {"type": "string"},
                        "tone": {"type": "string"},
                        "start_time": {"type": "number", "format": "float"},
                        "end_time": {"type": "number", "format": "float"},
                    },
                    "required": [
                        "speaker_id",
                        "gender",
                        "transcript",
                        "tone",
                        "start_time",
                        "end_time",
                    ],
                },
            },
        ),
    )

  response = call_gemini()
  logging.info(
      "Gemini Token Count for transcribe_media: %s",
      response.usage_metadata.total_token_count,
  )
  response_json = json.loads(response.text)
  return TypeAdapter(list[TranscribeSegment]).validate_python(response_json)


def transcribe_media(audio_file_path: str, language: str) -> str:
  """Uses fasterwhisper to transcribe the given audio.

  The returned transcription is a single string with a segment per line. Each
  line starts with "[Xs -> Ys]" where X is the start time and Y the end time of
  the segment.

  Args:
    audio_file_path: the local path to the file to transcribe.
    language: the language of the audio. This shoud be the language code
        (e.g. en or en-US)

  Returns:
    A transcript of the audio file.
  """

  # openwhisper only uses the language part of a language code.
  if "-" in language:
    language = language.split("-")[0]

  segments, _ = whisper_model.transcribe(
      audio_file_path, language=language, task="transcribe", beam_size=7
  )

  transcript: list[str] = []
  for segment in segments:
    transcript.append(f"[{segment.start}s -> {segment.end}s]  {segment.text}")

  return "\n".join(transcript)


def match_voice(
    client: google.genai.Client,
    model_name: str,
    segments: list[TranscribeSegment],
) -> dict[str, str]:
  """Matches speakers to voices from VOICE_OPTIONS using a generative model.

  Args:
    client: The Gemini API client.
    model_name: The name of the generative model to use.
    segments: A list of transcription segments.

  Returns:
    A dictionary mapping speaker IDs to voice names.
  """
  speaker_info = {}
  for segment in segments:
    if segment.speaker_id not in speaker_info:
      speaker_info[segment.speaker_id] = {
          "gender": segment.gender,
          "tones": [],
      }
    speaker_info[segment.speaker_id]["tones"].append(segment.tone)

  voice_map = {}
  for speaker_id, info in speaker_info.items():
    prompt = f"""
        Based on the speaker's gender and vocal tones, select the most fitting voice from the provided options.
        Ensure that a voice option is only used for a single speaker and not for multiple speakers at the same time.


        **Speaker Profile:**
        - **Gender:** {info['gender']}
        - **Vocal Tones:** {', '.join(list(set(info['tones'])))}

        **Voice Options:**
        ```json
        {json.dumps(VOICE_OPTIONS, indent=2)}
        ```

        Analyze the voice options and choose the one that best aligns with the speaker's profile.
        Your response must be a single JSON object with a single key, "voice_name",
        containing the name of the selected voice.
        """

    response = client.models.generate_content(
        model=model_name,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema={
                "type": "object",
                "properties": {"voice_name": {"type": "string"}},
                "required": ["voice_name"],
            },
        ),
    )
    logging.info(
        "Gemini Token Count for match_voice: %s",
        response.usage_metadata.total_token_count,
    )
    response_json = json.loads(response.text)
    voice_map[speaker_id] = response_json["voice_name"]

  return voice_map

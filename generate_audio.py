"""Functions used to generate audio using Gemini TTS."""

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
import io
import logging
import wave

from google.api_core import exceptions as api_exceptions
from google.api_core.retry import Retry
from google.cloud import texttospeech
import librosa
import numpy as np
import soundfile


def _process_audio_part(audio_data: bytes, path: str) -> float:
  """Processes the audio part, extracts metadata, and saves the audio to a file.

  Args:
    audio_data: the bytes of the wav file.
    path: the path to save the file to.

  Returns:
    the duration of the file.
  """
  with io.BytesIO(audio_data) as wav_file:
    with wave.open(wav_file, "rb") as wav:
      num_frames = wav.getnframes()
      frame_rate = wav.getframerate()

    with open(path, "wb") as out_file:
      out_file.write(wav_file.getbuffer())

  duration = num_frames / frame_rate
  return duration


def generate_audio(
    text: str,
    prompt: str,
    language: str,
    voice_name: str,
    output_path: str,
    model_name: str = "gemini-2.5-pro-tts",
) -> float:
  """Uses Gemini TTS to generate audio for the given text.

  Args:
   text: the text to have spoken.
   prompt: additional instructions for the generation.
   language: the language to be spoken in ISO format (e.g. en-US)
   voice_name: the name of the Gemini voice to use.
   output_path: where to save the generated audio file.
   model_name: the Gemini model to use. Defaults to gemini-2.5-pro-tts.

  Returns:
   the duration of the generated file.
  """
  try:
    tts_client = texttospeech.TextToSpeechClient()
    synth_input = texttospeech.SynthesisInput(text=text, prompt=prompt)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language, name=voice_name, model_name=model_name
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )
    advanced_options = texttospeech.AdvancedVoiceOptions()
    # TODO: b/456676630 - add configuration flag for relaxing safety filters
    # advanced_options.relax_safety_filters = True
    request = texttospeech.SynthesizeSpeechRequest(
        input=synth_input,
        voice=voice,
        audio_config=audio_config,
        advanced_voice_options=advanced_options,
    )

    # we try TTS 3 times before failing. Normally, if a second attempt doesn't
    # result in audio being generated, it never will with the current text.
    response = None
    for _ in range(3):
      response = _call_tts(tts_client, request)
      if response.audio_content:
        break

    logging.info("Gemini TTS Character Count for generate_audio: %s", len(text))
    if not response:
      logging.error("Text-to-speech API returned empty audio content.")
      return 0.0

    duration = _process_audio_part(response.audio_content, output_path)
    return duration
  except (
      api_exceptions.GoogleAPICallError,
      api_exceptions.RetryError,
      IOError,
      wave.Error,
  ) as e:
    logging.error("An error occurred during audio generation: %s", e)
    return 0.0


def _call_tts(
    tts_client: texttospeech.TextToSpeechClient,
    request: texttospeech.SynthesizeSpeechRequest,
) -> texttospeech.SynthesizeSpeechResponse:
  """Makes the actual call to Gemini TTS.

  Args:
    tts_client: the genai Client to use when calling TTS.
    request: the request to send to TTS.

  Returns:
    The response from TTS.
  """
  retry_config = Retry(initial=1, maximum=10, multiplier=2, deadline=60)
  response = tts_client.synthesize_speech(request=request, retry=retry_config)
  return response


def strip_silence(path: str) -> float:
  """Removes the silence from the start and end of an audio file.

  Args:
    path: the path to the file to strip.

  Returns:
    the duration of the stripped audio.
  """
  y, sr = librosa.load(path)
  yt, _ = librosa.effects.trim(y)

  # If the audio is all silence, librosa.effects.trim doesn't shorten it.
  # So if the length is the same, and the audio is all zeros, then we
  # should return an empty array.
  if len(y) == len(yt) and np.all(y == 0):
    yt = np.array([])

  soundfile.write(path, yt, sr)
  return librosa.get_duration(y=yt, sr=sr)


def shorten_audio(
    path: str, original_duration: float, target_duration: float
) -> float:
  """Shortens audio to a given duration.

  The audio file provided will be shortened to the target duration. This can
  cause echos and other artifacts.

  Args:
    path: the path to the audio file.
    original_duration: the duration of the original audio.
    target_duration: the duration to shorten the audio to.

  Returns:
    the duration of the shortened audio.
  """
  y, sr = librosa.load(path)
  if original_duration == 0:
    y_sped_up = np.array([])
  else:
    rate = original_duration / target_duration
    y_sped_up = librosa.effects.time_stretch(y, rate=rate)

  soundfile.write(path, y_sped_up, sr)

  return librosa.get_duration(y=y_sped_up, sr=sr)

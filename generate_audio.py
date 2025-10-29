import librosa
import logging
import re
import soundfile  # pyright: ignore[reportMissingTypeStubs]
import wave
from google.genai import types, Client
from tenacity import retry, stop_after_attempt, wait_fixed


def _process_audio_part(audio_part: types.Part, path: str) -> float:
  """Processes the audio part, extracts metadata, and saves the audio as a WAV."""
  # Parse the mime_type string "audio/L16;codec=pcm;rate=24000"
  mime_type = audio_part.inline_data.mime_type or "no mime type"
  match = re.search(r"L(\d+);codec=(?:\w+);rate=(\d+)", mime_type)
  if not match:
    raise ValueError(f"Could not parse mime_type: {mime_type}")
  bit_depth = int(match.group(1))
  sample_rate = int(match.group(2))
  pcm_data = audio_part.inline_data.data
  with wave.open(path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(bit_depth // 8)
    wf.setframerate(sample_rate)
    wf.writeframes(pcm_data)

    num_frames = wf.getnframes()

  duration = num_frames / sample_rate
  return duration


def generate_audio(
  client: Client,
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

  prompt = f"""Say the text in the TEXT section using the instructions in the INSTRUCTIONS section.
  The language being spoken is {language}.
  ## INSTRUCTIONS
  {prompt}

  ## TEXT
  {text}
  """

  voice_config = types.VoiceConfig(
    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
  )

  duration = 0.0

  @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
  def call_gemini():
    return client.models.generate_content(
      model=model_name,
      contents=prompt,
      config=types.GenerateContentConfig(
        # safety_settings=safety_settings,
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=voice_config),
      ),
    )

  response = call_gemini()

  ## Gemini sometimes just fails to return the object we're expecting.
  if (
    response.candidates[0]
    and response.candidates[0].content
    and response.candidates[0].content.parts
  ):
    audio_part = response.candidates[0].content.parts[0]
    _process_audio_part(audio_part, output_path)
    duration = strip_silence(output_path)
  else:
    logging.error(
      f"Generating Audio failed with the following response from Gemini: {response}"
    )

  return duration


import numpy as np


def strip_silence(path: str) -> float:
  """Removes the silence from the start and end of an audio file.

  Args:
    path: the path to the file to strip
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
  """Shortens audio"""
  y, sr = librosa.load(path)
  if original_duration == 0:
    y_sped_up = np.array([])
  else:
    rate = original_duration / target_duration
    y_sped_up = librosa.effects.time_stretch(y, rate=rate)

  soundfile.write(path, y_sped_up, sr)

  return librosa.get_duration(y=y_sped_up, sr=sr)

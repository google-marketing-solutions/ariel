import io
import librosa
import logging
import numpy as np
import soundfile  # pyright: ignore[reportMissingTypeStubs]
import wave
from google.cloud import texttospeech
from google.api_core.retry import Retry


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
  # """Uses Gemini TTS to generate audio for the given text.

  # Args:
  #   text: the text to have spoken.
  #   prompt: additional instructions for the generation.
  #   language: the language to be spoken in ISO format (e.g. en-US)
  #   voice_name: the name of the Gemini voice to use.
  #   output_path: where to save the generated audio file.
  #   model_name: the Gemini model to use. Defaults to gemini-2.5-pro-tts.

  # Returns:
  #   the duration of the generated file.
  # """
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

    if not response:
      logging.error("Text-to-speech API returned empty audio content.")
      return 0.0

    duration = _process_audio_part(response.audio_content, output_path)
    return duration
  except Exception as e:
    logging.error(f"An error occurred during audio generation: {e}")
    return 0.0


def _call_tts(
  tts_client: texttospeech.TextToSpeechClient,
  request: texttospeech.SynthesizeSpeechRequest,
) -> texttospeech.SynthesizeSpeechResponse:
  retry_config = Retry(initial=1, maximum=10, multiplier=2, deadline=60)
  response = tts_client.synthesize_speech(request=request, retry=retry_config)
  return response


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

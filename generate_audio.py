import base64
import io
import logging
import re
import subprocess
import wave
from google.genai import types
from google.cloud import texttospeech
from tenacity import retry, stop_after_attempt, wait_fixed


def pcm_to_wav_base64(
  pcm_data: bytes,
  sample_rate: int,
  bit_depth: int,
) -> tuple[str, float]:
  """Converts raw PCM audio data to a base64 encoded WAV string."""
  with io.BytesIO() as wav_file:
    with wave.open(wav_file, "wb") as wf:
      wf.setnchannels(1)
      wf.setsampwidth(bit_depth // 8)
      wf.setframerate(sample_rate)
      wf.writeframes(pcm_data)

      num_frames = wf.getnframes()

    wav_bytes = wav_file.getvalue()

  base64_wav = base64.b64encode(wav_bytes).decode("utf-8")
  duration = num_frames / sample_rate
  return base64_wav, duration


def _process_audio_part(audio_part) -> tuple[str, float]:
  """Processes the audio part, extracts metadata, and converts to base64 WAV."""
  # Parse the mime_type string "audio/L16;codec=pcm;rate=24000"
  mime_type = audio_part.inline_data.mime_type

  match = re.search(r"L(\d+);codec=(?:\w+);rate=(\d+)", mime_type)
  if not match:
    raise ValueError(f"Could not parse mime_type: {mime_type}")
  bit_depth = int(match.group(1))
  sample_rate = int(match.group(2))

  return pcm_to_wav_base64(
    audio_part.inline_data.data, sample_rate=sample_rate, bit_depth=bit_depth
  )


def _get_mp3_duration(file_path: str) -> float:
  """Gets the duration of an mp3 file in seconds.

  Args:
    file_path: the path to the mp3 to probe.

  Return:
    the duration of the file in seconds.
  """
  ffprobe_command = [
    "ffprobe",
    "-v",
    "error",
    "-show_entries",
    "format=duration",
    "-of",
    "default=noprint_wrappers=1:nokey=1",
    file_path,
  ]

  try:
    duration_result = subprocess.run(
      ffprobe_command, capture_output=True, text=True, check=True
    )
    duration = duration_result.stdout.strip()
    return float(duration)
  except subprocess.CalledProcessError as er:
    logging.error(f"Error running ffprobe to get mp3 duration: {er}")
    raise er
  except FileNotFoundError as fne:
    logging.error("ffprobe not found. Please ensure it's in the path.")
    raise fne


def generate_audio(
  text: str,
  prompt: str,
  language: str,
  voice_name: str,
  output_path: str,
  model_name: str = "gemini-2.5-pro-tts",
) -> float:
  # voice_config = types.VoiceConfig(
  #     prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name))

  # @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
  # def call_gemini():
  #     return client.models.generate_content(
  #         model=model_name,
  #         contents=prompt,
  #         config=types.GenerateContentConfig(
  #             response_modalities=["AUDIO"],
  #             speech_config=types.SpeechConfig(voice_config=voice_config),
  #         ))

  # response = call_gemini()

  # # Gemini sometimes just fails to return the object we're expecting.
  # if response.candidates[0] and response.candidates[0].content and response.candidates[0].content.parts:
  #     audio_part = response.candidates[0].content.parts[0]
  #     return _process_audio_part(audio_part)
  # else:
  #     logging.error(f"Generating Audio failed with the following response from Gemini: {response}")

  # return "", 0.0
  client = texttospeech.TextToSpeechClient()
  synth_input = texttospeech.SynthesisInput(
      text=text, prompt=prompt
  )
  voice = texttospeech.VoiceSelectionParams(
    language_code=language, name=voice_name, model_name=model_name
  )
  audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3
  )
  try:
    response = client.synthesize_speech(
        input=synth_input, voice=voice, audio_config=audio_config
    )
  except Exception as e:
      print(f"Error generating audio for text: >>{text}<< and prompt >>{prompt}<<")
      raise e
  with open(output_path, "wb") as out_file:
    out_file.write(response.audio_content)

  return _get_mp3_duration(output_path)

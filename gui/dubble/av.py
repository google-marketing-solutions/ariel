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

"""Dubble module to process audio and video tasks."""

import os
import struct
import subprocess
from typing import Any, Dict, List
from dubble.configuration import DubbleConfig
from dubble.dubble import DubbingError
from dubble.dubble import DubbleTTSData
from moviepy.editor import AudioFileClip
from moviepy.editor import CompositeAudioClip
from moviepy.editor import concatenate_audioclips
from moviepy.editor import VideoFileClip

# Default settings for sampling the audio with good quality
BITS_PER_SAMPLE = 16
RATE = 24000


def separate_audio_from_video(config: DubbleConfig) -> DubbleConfig:
  """Separates the music and vocals from the input video file.

  Args:
    config (DubbleConfig): The configuration object containing
      `video_file_path`.

  Returns:
    DubbleConfig: The updated configuration object with `vocals_path` and
                  `background_path` set.

  Raises:
    RuntimeError: If the audio separation process fails to produce the expected
      output files.
  """

  original_audio_name = "original_audio"
  original_audio_extension = "wav"
  video = VideoFileClip(config.video_file_path)
  audio = video.audio
  original_audio_path = f"{config.output_local_path}/{original_audio_name}.{original_audio_extension}"
  audio.write_audiofile(original_audio_path, codec='pcm_s16le')
  command = (
      f"python3 -m demucs --two-stems=vocals -n htdemucs --out {config.output_local_path}"
      f" {original_audio_path}"
  )
  subprocess.run(command, shell=True, check=True)

  base_htdemucs_path = os.path.join(config.output_local_path, "htdemucs", original_audio_name)
  vocals_path = os.path.join(base_htdemucs_path, "vocals.wav")
  background_path = os.path.join(base_htdemucs_path, "no_vocals.wav")

  if os.path.exists(vocals_path) and os.path.exists(background_path):
    config.vocals_path = vocals_path
    config.background_path = background_path
    return config
  else:
    raise RuntimeError(
        'Audio separation failed. Could not find output files in the expected'
        f' path: {vocals_path}'
    )


def parse_audio_mime_type(mime_type: str) -> Dict[str, int | None]:
  """Parses an audio MIME type string to extract sample rate and bits per sample.

  Args:
    mime_type (str): The MIME type string (e.g., 'audio/L16;rate=24000').

  Returns:
    Dict[str, int | None]: A dictionary containing 'bits_per_sample' and 'rate'.
  """
  bits_per_sample = BITS_PER_SAMPLE
  rate = RATE
  parts = mime_type.split(';')
  for param in parts:
    param = param.strip()
    if param.lower().startswith('rate='):
      try:
        rate = int(param.split('=', 1)[1])
      except (ValueError, IndexError):
        pass
    elif param.startswith('audio/L'):
      try:
        bits_per_sample = int(param.split('L', 1)[1])
      except (ValueError, IndexError):
        pass
  return {'bits_per_sample': bits_per_sample, 'rate': rate}


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
  """Wraps raw audio data with a WAV file header based on the MIME type parameter.

  Args:
    audio_data (bytes): The raw audio data (PCM samples).
    mime_type (str): The MIME type string used to determine format parameters.

  Returns:
    bytes: The complete WAV file content as bytes.

  WAV Header Field Breakdown ('<4sI4s4sIHHIIHH4sI'):
    -----------------------
    - '<': Denotes little-endian byte order.

    -- RIFF Chunk Descriptor --
    - '4s': b'RIFF'          (Chunk ID: Identifies the RIFF container)
    - 'I':  36 + data_size  (Chunk Size: Total file size minus 8 bytes)
    - '4s': b'WAVE'          (Format: Specifies WAVE format)

    -- "fmt " Sub-chunk --
    - '4s': b'fmt '          (Sub-chunk ID: Marks the format specification
    block)
    - 'I':  16              (Sub-chunk Size: 16 bytes for PCM)
    - 'H':  1               (Audio Format: 1 for uncompressed PCM)
    - 'H':  1               (Number of Channels: 1 for mono)
    - 'I':  sample_rate     (Sample Rate: Samples per second)
    - 'I':  sample_rate * 2 (Byte Rate: SampleRate * NumChannels *
    BitsPerSample/8)
    - 'H':  2               (Block Align: NumChannels * BitsPerSample/8)
    - 'H':  bits_per_sample (Bits Per Sample: e.g., 16)

    -- "data" Sub-chunk --
    - '4s': b'data'          (Sub-chunk ID: Marks the beginning of the audio
    data)
    - 'I':  data_size       (Sub-chunk Size: Size of the raw audio data in
    bytes)
  """
  parameters = parse_audio_mime_type(mime_type)
  bits_per_sample, sample_rate = (
      parameters['bits_per_sample'],
      parameters['rate'],
  )
  data_size = len(audio_data)
  header = struct.pack(
      '<4sI4s4sIHHIIHH4sI',
      b'RIFF',
      36 + data_size,
      b'WAVE',
      b'fmt ',
      16,
      1,
      1,
      sample_rate,
      sample_rate * 2,
      2,
      bits_per_sample,
      b'data',
      data_size,
  )
  return header + audio_data


def assemble_final_video(
    timed_vocal_clips: List[AudioFileClip], config: DubbleConfig
) -> str:
  """Assembles the final video by combining the original video and audio files.

  Args:
    timed_vocal_clips (List[AudioFileClip]): A list of moviepy AudioFileClip
      objects representing the new, time-aligned dubbed vocals.
    config (DubbleConfig): The configuration object containing video and
      background audio paths.

  Returns:
    str: The filename of the final output video.
  Raises:
    DubbingError: If the audio and video merge process fails to produce the
    expected output files.
  """

  try:

    if timed_vocal_clips and os.path.exists(config.background_path):

      for clip in timed_vocal_clips:
        clip.end = clip.start + clip.duration
        clip.volumex(config.speech_volume)
      background_clip = AudioFileClip(config.background_path)
      original_video_clip = VideoFileClip(config.video_file_path)

      final_audio = CompositeAudioClip(
          [background_clip.volumex(config.music_volume)] + [vocal_clip.volumex(config.speech_volume) for vocal_clip in timed_vocal_clips]
      )
      final_audio.duration = min(
          final_audio.duration, original_video_clip.duration
      )
      final_video = original_video_clip.set_audio(final_audio)

      output_filename = f'{os.path.splitext(config.video_file_path)[0]}_dubbed_{config.target_language}.mp4'

      final_video.write_videofile(
          output_filename, codec='libx264', audio_codec='aac'
      )
      return output_filename
    else:
      raise DubbingError(Exception('No vocals clip found or path not found.'))

  except Exception as e:
    raise DubbingError(str(e)) from e


def post_process_audio_clip(
    audio_clip: AudioFileClip,
    audio_file_path: str,
    utterance: DubbleTTSData,
    config: DubbleConfig,
) -> AudioFileClip:
  """Applies final time-alignment to the audio clip.

  Args:
    audio_clip (AudioFileClip): The generated audio clip (moviepy object).
    audio_file_path (str): The file path where the audio clip is saved.
    utterance (DubbleTTSData): The data object containing start/end times and
      sync mode.
    config (DubbleConfig): The configuration object containing speed limits.

  Returns:
    AudioFileClip: The time-adjusted audio clip object, ready for composition.
  """
  original_duration = utterance.end - utterance.start

  if (
      utterance.sync_mode == 'Speed Up to Fit'
      and audio_clip.duration > original_duration
      and original_duration > 0
  ):
    speed_ratio = min(
        audio_clip.duration / original_duration, config.max_speed_up_ratio
    )
    # Uses FFmpeg to perform the speed adjustment in place
    subprocess.run(
        f'ffmpeg -y -i {audio_file_path} -filter:a "atempo={speed_ratio:.2f}"'
        f' -vn {audio_file_path}',
        shell=True,
        check=True,
        capture_output=True,
    )
    # Reload the modified audio clip
    audio_clip = AudioFileClip(audio_file_path)

  if utterance.sync_mode == 'Trim to Fit':
    return audio_clip.set_start(utterance.start).set_end(utterance.end)
  elif utterance.sync_mode == 'Align to End':
    return audio_clip.set_start(max(0, utterance.end - audio_clip.duration))
  else:
    return audio_clip.set_start(utterance.start)


def get_audio_file_from_llm_bytes_response(
    save_path: str, bytes: bytes
) -> AudioFileClip:
  """Saves the bytes as wav file, and loads it as a moviepy AudioFileClip.

  Args:
    save_path (str): The local file path where the WAV audio should be saved.
    bytes (bytes): in linear16 format.

  Returns:
    AudioFileClip: The loaded moviepy audio clip object.
  """

  with open(save_path, 'wb') as f:
    f.write(bytes)

  clip = AudioFileClip(save_path)

  os.remove(save_path)

  return clip

def get_audio_file_from_llm_parts_response(
    save_path: str, llm_response: Any
) -> AudioFileClip:
  """Converts raw audio data from the LLM response object into a WAV file.

  saves it to disk, and loads it as a moviepy AudioFileClip.

  Args:
    save_path (str): The local file path where the WAV audio should be saved.
    llm_response (Any): The LLM response part object (e.g., genai.types.Part)
      containing `inline_data.data` (raw audio bytes) and
      `inline_data.mime_type`.

  Returns:
    AudioFileClip: The loaded moviepy audio clip object.
  """

  wav_data = convert_to_wav(
      llm_response.inline_data.data, llm_response.inline_data.mime_type
  )

  with open(save_path, 'wb') as f:
    f.write(wav_data)

  clip = AudioFileClip(save_path)

  os.remove(save_path)

  return clip

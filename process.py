"""Functions used to process the video during dubbing."""

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

import os
import pathlib
from audio_separator.separator import Separator
from models import Utterance
import moviepy


def separate_audio_from_video(
    video_file_path: str, output_local_path: str
) -> tuple[str, str, str]:
  """Separates the music and vocals from the input video file.

  Args:
    video_file_path: Path to the input video file containing both speech and
      music.
    output_local_path: Path to save the separated audio files.

  Returns:
    A tuple with the following three strings:
       - original_audio_path: Path to the original audio file.
       - vocals_path: Path to the separated vocals speech file. The file will be
           named "vocals"
       - background_path: Path to the separated music file. The file will be
           named background.

  Raises:
    RuntimeError: when the audio cannot be extracted.
  """
  original_audio_name = "original_audio"
  original_audio_extension = "wav"
  video = moviepy.VideoFileClip(video_file_path)
  audio = video.audio
  original_audio_path = (
      f"{output_local_path}/{original_audio_name}.{original_audio_extension}"
  )
  if not audio:
    raise RuntimeError(f"Could not extract audio from {video_file_path}")
  audio.write_audiofile(original_audio_path, codec="pcm_s16le")

  separator = Separator(output_dir=output_local_path)
  output_file_names = {"Vocals": "vocals", "Instrumental": "background"}
  separator.load_model(model_filename="5_HP-Karaoke-UVR.pth")
  output_files: list[str] = separator.separate(
      original_audio_path, output_file_names
  )

  return (
      original_audio_path,
      os.path.join(output_local_path, output_files[0]),
      os.path.join(output_local_path, output_files[1]),
  )


def merge_background_and_vocals(
    *,
    background_audio_file: str,
    dubbed_vocals_path: str,
    output_directory: str,
    target_language: str,
    dubbed_audio_filename: str = "dubbed_audio",
    output_format: str = "wav",
) -> str:
  """Mixes background music and vocals tracks, normalizes the volume, and exports the result.

  Args:
    background_audio_file: Path to the background audio file.
    dubbed_vocals_path: Path to the dubbed vocals audio file.
    output_directory: The base directory where the output file will be saved.
    target_language: The language to dub the ad into. It must be ISO 3166-1
      alpha-2 country code.
    dubbed_audio_filename: The base name for the output audio file.
    output_format: The file format for the output audio file (e.g., 'mp3').

  Returns:
    The path to the output audio file with merged dubbed vocals.
  """

  background_audio = moviepy.AudioFileClip(background_audio_file)
  background_audio = background_audio.with_start(0)
  dubbed_vocals = moviepy.AudioFileClip(dubbed_vocals_path)

  # Create a silent track with the same duration as the background audio
  audio_parts: list[moviepy.AudioClip] = [background_audio, dubbed_vocals]

  combined_audio: moviepy.CompositeAudioClip = moviepy.CompositeAudioClip(
      audio_parts
  )
  target_language_suffix = "_" + target_language.replace("-", "_").lower()
  dubbed_audio_file = os.path.join(
      output_directory,
      dubbed_audio_filename + target_language_suffix + "." + output_format,
  )
  combined_audio.write_audiofile(dubbed_audio_file)
  return dubbed_audio_file


def merge_vocals(
    *,
    dubbed_vocals_metadata: list[Utterance],
    output_directory: str,
    target_language: str,
    dubbed_audio_filename: str = "vocals_only",
    output_format: str = "wav",
) -> str:
  """Merges dubbed vocal tracks into a single audio file.

  Args:
    dubbed_vocals_metadata: A list of dictionaries, each containing the path to
      a dubbed vocal chunk and its start time.
    output_directory: The base directory where the output file will be saved.
    target_language: The language to dub the ad into. It must be ISO 3166-1
      alpha-2 country code.
    dubbed_audio_filename: The base name for the output audio file.
    output_format: The file format for the output audio file (e.g., 'mp3').

  Returns:
    The path to the output audio file with merged dubbed vocals.
  """
  audio_parts: list[moviepy.AudioClip] = []
  max_end_time = 0
  for utterance in dubbed_vocals_metadata:
    if utterance.removed or not utterance.audio_url:
      continue
    max_end_time = max(max_end_time, utterance.translated_end_time)

  target_language_suffix = "_" + target_language.replace("-", "_").lower()
  target_file = os.path.join(
      output_directory,
      dubbed_audio_filename + target_language_suffix + "." + output_format,
  )

  # Create a silent track with the same duration as the background audio
  if max_end_time == 0:
    # If there are no utterances, create an empty audio file and return
    target_path = pathlib.Path(target_file)
    target_path.touch()
    return target_file
  silent_audio = moviepy.AudioClip(
      frame_function=lambda t: [0, 0], duration=max_end_time
  )
  audio_parts.append(silent_audio)

  # Overlay each vocal chunk at its start time
  for utterance in dubbed_vocals_metadata:
    if utterance.removed:
      continue

    vocal_chunk = None
    if utterance.muted:
      original_vocals_path = os.path.join(
          output_directory, "htdemucs", "original_audio", "vocals.wav"
      )
      vocal_chunk = moviepy.AudioFileClip(original_vocals_path)
      vocal_chunk = vocal_chunk.subclipped(
          utterance.original_start_time, utterance.original_end_time
      )
    elif utterance.audio_url:
      vocal_chunk = moviepy.AudioFileClip(utterance.audio_url)

    if vocal_chunk:
      vocal_chunk = vocal_chunk.with_start(
          float(utterance.translated_start_time)
      )
      audio_parts.append(vocal_chunk)

  combined_audio: moviepy.CompositeAudioClip = moviepy.CompositeAudioClip(
      audio_parts
  )
  combined_audio.write_audiofile(target_file)
  return target_file


def combine_video_and_audio(
    video_file_path: str,
    audio_file_path: str,
    output_file_path: str,
):
  """Combines a video file with an audio file to create the final video.

  Args:
    video_file_path: Path to the original video file (video stream only).
    audio_file_path: Path to the dubbed audio file.
    output_file_path: Path to save the final dubbed video.
  """
  video_clip = moviepy.VideoFileClip(video_file_path)
  audio_clip = moviepy.AudioFileClip(audio_file_path)

  # Set the audio of the video clip to the new dubbed audio (Updated method)
  final_clip = video_clip.with_audio(audio_clip)

  # Write the final video file
  final_clip.write_videofile(
      output_file_path, codec="libx264", audio_codec="aac"
  )

  # Close the clips to free up resources
  video_clip.close()
  audio_clip.close()
  final_clip.close()

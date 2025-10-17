import os
import subprocess

from moviepy import AudioFileClip, VideoFileClip
from pydub import AudioSegment
from models import Utterance


def separate_audio_from_video(video_file_path: str, output_local_path: str):
  """Separates the music and vocals from the input video file.

  Args:
    video_file_path: Path to the input video file containing both speech and
      music.
    output_local_path: Path to save the separated audio files.


  Returns:
    vocals_path: Path to the separated vocals speech file.
    background_path: Path to the separated music file.


  Raises:
    RuntimeError: If the audio separation process fails to produce the expected
      output files.
  """
  # TODO(): Add support for multiple splitting rounds like in v1.
  original_audio_name = "original_audio"
  original_audio_extension = "wav"
  video = VideoFileClip(video_file_path)
  audio = video.audio
  original_audio_path = (
    f"{output_local_path}/{original_audio_name}.{original_audio_extension}"
  )
  if not audio:
    raise RuntimeError(f"Could not extract audio from {video_file_path}")
  audio.write_audiofile(original_audio_path, codec="pcm_s16le")

  command = (
    f"python3 -m demucs --two-stems=vocals -n htdemucs --out {output_local_path}"
    f" {original_audio_path}"
  )
  subprocess.run(command, shell=True, check=True)

  # base_filename = os.path.splitext(os.path.basename(original_audio_path))[0]
  base_htdemucs_path = os.path.join(
    output_local_path, "htdemucs", original_audio_name
  )
  vocals_path = os.path.join(base_htdemucs_path, "vocals.wav")
  background_path = os.path.join(base_htdemucs_path, "no_vocals.wav")

  if os.path.exists(vocals_path) and os.path.exists(background_path):
    vocals_path = vocals_path
    background_path = background_path
    return vocals_path, background_path
  else:
    raise RuntimeError(
      "Audio separation failed. Could not find output files in the expected" +
      f" path: {vocals_path}"
    )


def merge_background_and_vocals(
  *,
  background_audio_file: str,
  dubbed_vocals_metadata: list[Utterance],
  output_directory: str,
  target_language: str,
  vocals_volume_adjustment: float = 0.0,
  background_volume_adjustment: float = 0.0,
  dubbed_audio_filename: str = "dubbed_audio",
  output_format: str = "mp3",
) -> str:
  """Mixes background music and vocals tracks, normalizes the volume, and exports the result.

  Args:
      background_audio_file: Path to the background audio file.
      dubbed_vocals_metadata: A list of dictionaries, each containing the path
        to a dubbed vocal chunk and its start time.
      output_directory: The base directory where the output file will be saved.
      target_language: The language to dub the ad into. It must be ISO 3166-1
        alpha-2 country code.
      vocals_volume_adjustment: By how much the vocals audio volume should be
        adjusted, in dB.
      background_volume_adjustment: By how much the background audio volume
        should be adjusted, in dB.
      output_subdirectory: The name of the subdirectory within the output
        directory to save the file.
      dubbed_audio_filename: The base name for the output audio file.
      output_format: The file format for the output audio file (e.g., 'mp3').


  Returns:
    The path to the output audio file with merged dubbed vocals and original
    background audio.
  """

  background_audio = AudioSegment.from_file(background_audio_file)
  background_audio += background_volume_adjustment

  # Create a silent track with the same duration as the background audio
  combined_vocals = AudioSegment.silent(duration=len(background_audio))

  # Overlay each vocal chunk at its start time
  for utterance in dubbed_vocals_metadata:
    vocal_chunk = AudioSegment.from_file(utterance.audio_url)
    start_time_ms = int(utterance.translated_start_time * 1000)
    combined_vocals = combined_vocals.overlay(
      vocal_chunk, position=start_time_ms
    )

  combined_vocals += vocals_volume_adjustment
  mixed_audio = background_audio.overlay(combined_vocals)
  target_language_suffix = "_" + target_language.replace("-", "_").lower()
  dubbed_audio_file = os.path.join(
    output_directory,
    dubbed_audio_filename + target_language_suffix + "." + output_format,
  )
  mixed_audio.normalize()
  mixed_audio.export(dubbed_audio_file, format=output_format)
  return dubbed_audio_file


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
  video_clip = VideoFileClip(video_file_path)
  audio_clip = AudioFileClip(audio_file_path)

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

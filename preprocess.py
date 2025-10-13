import os
import subprocess

from moviepy import VideoFileClip


def separate_audio_from_video(video_file_path: str, output_local_path: str) -> tuple[str, str]:
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

  original_audio_name = "original_audio"
  original_audio_extension = "wav"
  video = VideoFileClip(video_file_path)
  audio = video.audio
  original_audio_path = f"{output_local_path}/{original_audio_name}.{original_audio_extension}"
  audio.write_audiofile(original_audio_path, codec='pcm_s16le')

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
        'Audio separation failed. Could not find output files in the expected' +
        f' path: {vocals_path}'
    )

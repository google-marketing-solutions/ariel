"""A speech-to-text module of Ariel package from the Google EMEA gTech Ads Data Science."""

from typing import Final, Mapping, Sequence
from faster_whisper import WhisperModel
import torch

_DEFAULT_MODEL: Final[str] = "large-v3"
_DEVICE: Final[str] = "gpu" if torch.cuda.is_available() else "cpu"
_COMPUTE_TYPE: Final[str] = "float16" if _DEVICE == "gpu" else "int8"
_DEFAULT_TRANSCRIPTION_MODEL: Final[WhisperModel] = WhisperModel(
    model_size_or_path=_DEFAULT_MODEL,
    device=_DEVICE,
    compute_type=_COMPUTE_TYPE,
)


def transcribe(
    *,
    vocals_filepath: str,
    advertiser_name: str,
    original_language: str,
    model: WhisperModel = _DEFAULT_TRANSCRIPTION_MODEL,
) -> str:
  """Transcribes an audio.

  Args:
      vocals_filepath: The path to the audio file ot be transcribed.
      advertiser_name: The name of the advertiser to use as a hotword.
      original_language: The original language of the audio. It's either ISO
        639-1 or ISO 3166-1 alpha-2 country code.
      model: The pre-initialized transcription model.

  Returns:
      The transcribed text.
  """
  segments, _ = model.transcribe(
      vocals_filepath,
      language=original_language.split("-")[0],
      hotwords=advertiser_name,
  )
  return " ".join(segment.text for segment in segments)


def transcribe_audio_chunks(
    *,
    chunk_data_list: Sequence[Mapping[str, float | str]],
    advertiser_name: str,
    original_language: str,
    model: WhisperModel = _DEFAULT_TRANSCRIPTION_MODEL,
) -> Sequence[Mapping[str, float | str]]:
  """Transcribes each audio chunk in the provided list and returns a new list with transcriptions added.

  Args:
      chunk_data_list: A sequence of mappings, each containing information about
        a single audio chunk, including the 'path' key.
      advertiser_name: The name of the advertiser.
      original_language: The original language of the audio.
      model: The pre-initialized transcription model.

  Returns:
      A new sequence of mappings, where each mapping is a copy of the original
      with an added 'text' key containing the transcription.
  """
  transcribed_chunk_data = []
  for item in chunk_data_list:
    new_item = item.copy()
    new_item["text"] = transcribe(
        vocals_filepath=item["path"],
        advertiser_name=advertiser_name,
        original_language=original_language,
        model=model,
    )
    transcribed_chunk_data.append(new_item)
  return transcribed_chunk_data

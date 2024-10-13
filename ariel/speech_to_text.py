# Copyright 2024 Google LLC
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

"""A speech-to-text module of Ariel package from the Google EMEA gTech Ads Data Science."""

import re
from typing import Final, Mapping, Sequence
from absl import logging
from faster_whisper import WhisperModel
from google.cloud import storage
from vertexai.generative_models import GenerativeModel
from vertexai.generative_models import Part

_DIARIZATION_PROMPT: Final[str] = (
    "You got the video / audio attached. The transcript is: {}. The number of"
    " speakers in the video / audio is: {}. You must provide only {}"
    " annotations, each for one dictionary in the transcript. And the specific"
    " instructions are: {}."
)
_MIME_TYPE_MAPPING: Final[Mapping[str, str]] = {
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
}


def transcribe(
    *,
    vocals_filepath: str,
    advertiser_name: str,
    original_language: str,
    model: WhisperModel,
) -> str:
  """Transcribes an audio.

  Args:
      vocals_filepath: The path to the audio file ot be transcribed.
      advertiser_name: The name of the advertiser to use as a hotword.
      original_language: The original language of the audio. It's either ISO
        639-1 or ISO 3166-1 alpha-2 country code, e.g. 'en-US'.
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


def is_substring_present(
    *, utterance: str, no_dubbing_phrases: Sequence[str]
) -> bool:
  """Checks if any phrase from a list of strings is present within a given utterance,

  after normalizing both for case-insensitivity and punctuation removal.

  This function is particularly useful for identifying specific phrases that
  should not be dubbed in a subsequent response.

  Args:
      utterance: The input text to search within.
      no_dubbing_phrases: A sequence of strings representing the phrases that
        should not be dubbed. It is critical to provide these phrases in a
        format as close as possible to how they might appear in the utterance
        (e.g., include punctuation, capitalization if relevant).

  Returns:
      True if none of the `no_dubbing_phrases` are found (after normalization)
      within the `utterance`, False otherwise.

  Example:
      >>> is_substring_present("Hello, how are you today?", ["how are you"])
      False
      >>> is_substring_present("That's great news!", ["great news!"])
      False

  Important Note:
      The accuracy of this function heavily depends on the specificity of the
      `no_dubbing_phrases`. If you want to catch variations like "How are you?"
      and "how are you doing?", it's best to include both in the list.
  """
  if not no_dubbing_phrases:
    return True
  for phrase in no_dubbing_phrases:
    normalized_utterance = re.sub(r"[^\w\s]", "", utterance.lower())
    normalized_target = re.sub(r"[^\w\s]", "", phrase.lower())
    if normalized_target in normalized_utterance:
      return False
  return True


def transcribe_audio_chunks(
    *,
    utterance_metadata: Sequence[Mapping[str, float | str]],
    advertiser_name: str,
    original_language: str,
    model: WhisperModel,
    no_dubbing_phrases: Sequence[str],
) -> Sequence[Mapping[str, float | str]]:
  """Transcribes each audio chunk in the provided list and returns a new list with transcriptions added.

  Args:
      utterance_metadata: A sequence of mappings, each containing information
        about a single audio chunk, including the 'path' key.
      advertiser_name: The name of the advertiser.
      original_language: The original language of the audio.
      model: The pre-initialized transcription model.
      no_dubbing_phrases: A sequence of strings representing the phrases that
        should not be dubbed. It is critical to provide these phrases in a
        format as close as possible to how they might appear in the utterance
        (e.g., include punctuation, capitalization if relevant).

  Returns:
      A new sequence of mappings, where each mapping is a copy of the original
      with an added 'text' key containing the transcription and 'for_dubbing'
      key indicating if the phrase should be dubbed or not.
  """

  updated_utterance_metadata = []
  for item in utterance_metadata:
    new_item = item.copy()
    transcribed_text = transcribe(
        vocals_filepath=item["path"],
        advertiser_name=advertiser_name,
        original_language=original_language,
        model=model,
    )
    new_item["text"] = transcribed_text
    new_item["for_dubbing"] = is_substring_present(
        utterance=transcribed_text, no_dubbing_phrases=no_dubbing_phrases
    )
    updated_utterance_metadata.append(new_item)
  return updated_utterance_metadata


def create_gcs_bucket(
    *, gcp_project_id: str, gcs_bucket_name: str, gcp_region: str
) -> None:
  """Creates a new GCS bucket in the specified region.

  Args:
    gcp_project_id: The ID of the Google Cloud project.
    gcs_bucket_name: The name of the bucket to create.
    gcp_region: The region to create the bucket in.
  """
  storage_client = storage.Client(project=gcp_project_id)
  bucket = storage_client.bucket(gcs_bucket_name)
  bucket.create(location=gcp_region)
  logging.info(f"Bucket {gcs_bucket_name} created in {gcp_region}.")


def upload_file_to_gcs(
    *, gcp_project_id: str, gcs_bucket_name: str, file_path: str
) -> str:
  """Returns a GCS file path after upload.

  Args:
    gcp_project_id: The ID of the Google Cloud project.
    gcs_bucket_name: The name of the bucket to upload to.
    file_path: The local path to the input file.
  """
  storage_client = storage.Client(project=gcp_project_id)
  bucket = storage_client.bucket(gcs_bucket_name)
  destination_blob_name = file_path.split("/")[-1]
  blob = bucket.blob(destination_blob_name)
  blob.upload_from_filename(file_path)
  output_gcs_file_path = f"gs://{gcs_bucket_name}/{destination_blob_name}"
  logging.info(f"File uploaded to {output_gcs_file_path}")
  return output_gcs_file_path


def remove_gcs_bucket(*, gcp_project_id: str, gcs_bucket_name: str) -> None:
  """Removes a GCS bucket.

  Args:
    gcp_project_id: The ID of the Google Cloud project.
    gcs_bucket_name: The name of the bucket to remove.
  """
  storage_client = storage.Client(project=gcp_project_id)
  bucket = storage_client.bucket(gcs_bucket_name)
  bucket.delete(force=True)


def process_speaker_diarization_response(
    *, response: str
) -> list[tuple[str, str]]:
  """Processes a speaker diarization response string and returns a list of speaker-timestamp tuples.

  Args:
      response: The speaker diarization response string.

  Returns:
      A list of tuples, where each tuple contains a speaker and their
      corresponding timestamp.
  """

  input_list = [
      item.strip()
      for item in response.replace("(", "")
      .replace(")", "")
      .replace("\n", "")
      .split(",")
  ]
  tuples_list = [
      (speaker, timestamp)
      for speaker, timestamp in zip(input_list[::2], input_list[1::2])
      if speaker and timestamp
  ]

  return tuples_list


def diarize_speakers(
    *,
    gcs_input_path: str,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    number_of_speakers: int,
    model: GenerativeModel,
    diarization_instructions: str | None = None,
) -> Sequence[tuple[str, str]]:
  """Diarizes speakers in a video/audio using a Gemini generative model.

  Args:
      gcs_input_path: The path to the MP4 video or MP3 audio file on Google
        Cloud Storage (GCS).
      utterance_metadata: The transcript of the input file, represented as a
        sequence of mappings with keys "start", "end" "text", "path",
        "for_dubbing" and optionally "vocals_path".
      number_of_speakers: The number of speakers in the input file.
      model: The pre-configured Gemini GenerativeModel instance.
      diarization_instructions: The specific instructions for diarization.

  Returns:
      A sequence of tuples representing speaker annotations, where each tuple
      contains the speaker name and the start time of the speaker
      segment.
  """
  prompt = _DIARIZATION_PROMPT.format(
      utterance_metadata,
      number_of_speakers,
      len(utterance_metadata),
      diarization_instructions or "",
  )
  file_extension = "." + gcs_input_path.split(".")[-1]
  mime_type = _MIME_TYPE_MAPPING[file_extension]
  response = model.generate_content([
      Part.from_uri(gcs_input_path, mime_type=mime_type),
      prompt,
  ])
  return process_speaker_diarization_response(response=response.text)


class GeminiDiarizationError(Exception):
  """Error when Gemini can't diarize speakers correctly."""

  pass


def add_speaker_info(
    utterance_metadata: Sequence[Mapping[str, str | float]],
    speaker_info: Sequence[tuple[str, str]],
) -> Sequence[Mapping[str, str | float]]:
  """Adds speaker information to each utterance metadata.

  Args:
      utterance_metadata: The sequence of utterance metadata dictionaries. Each
        dictionary represents utterance metadata of audio and contains the
        "start", "end" "text", "path", "for_dubbing" and optionally
        "vocals_path" keys.
      speaker_info: The sequence of tuples containing (speaker_id, gender)
        information. The order of tuples in this list should correspond to the
        order of utterance_metadata.

  Returns:
      The sequence of updated utterance metadata dictionaries with speaker
      information added.
      Each dictionary will include the "speaker_id" and "ssml_gender" keys.

  Raises:
      ValueError: If the lengths of "utterance_metadata" and "speaker_info" do
      not match.
  """
  if len(utterance_metadata) != len(speaker_info):
    raise GeminiDiarizationError(
        "The length of 'utterance_metadata' and 'speaker_info' must be the"
        " same."
    )
  updated_utterance_metadata = []
  for utterance, (speaker_id, ssml_gender) in zip(
      utterance_metadata, speaker_info
  ):
    new_utterance = utterance.copy()
    new_utterance["speaker_id"] = speaker_id
    new_utterance["ssml_gender"] = ssml_gender
    updated_utterance_metadata.append(new_utterance)
  return updated_utterance_metadata

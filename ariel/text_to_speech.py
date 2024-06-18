"""A text-to-speech module of of Ariel package from the Google EMEA gTech Ads Data Science."""

from typing import Final, Mapping, Sequence
from google.cloud import texttospeech

_SSML_MALE: Final[str] = "Male"
_SSML_FEMALE: Final[str] = "Female"
_SSML_NEUTRAL: Final[str] = "Neutral"
_PREFERRED_VOICES: Final[Sequence[str]] = (
    "Journey",
    "Studio",
    "Wavenet",
    "Polyglot",
    "News",
    "Neural2",
    "Standard",
)


def list_available_voices(
    language_code: str, client: texttospeech.TextToSpeechClient
) -> Mapping[str, str]:
  """Lists available voices for a given language code.

  Args:
      language_code: The language code to list voices for. It must be ISO 3166-1
        alpha-2 country code.
      client: A TextToSpeechClient object.

  Returns:
      A dictionary mapping voice names to their genders.
  """

  request = texttospeech.ListVoicesRequest(language_code=language_code)
  response = client.list_voices(request=request)
  return {
      voice.name: (
          _SSML_MALE
          if voice.ssml_gender == texttospeech.SsmlVoiceGender.MALE
          else _SSML_FEMALE
          if voice.ssml_gender == texttospeech.SsmlVoiceGender.FEMALE
          else _SSML_NEUTRAL
      )
      for voice in response.voices
  }


def assign_voices(
    *,
    utterance_metadata: Sequence[Mapping[str, str | float]],
    target_language: str,
    client: texttospeech.TextToSpeechClient,
    preferred_voices: Sequence[str] = _PREFERRED_VOICES,
    fallback_no_preferred_category_match: bool = False,
) -> Mapping[str, str | None]:
  """Assigns voices to speakers based on preferred voices and available voices.

  Args:
      utterance_metadata: A sequence of utterance metadata, each represented as a
        dictionary with keys: 'start', 'end', 'chunk_path', 'translated_text',
        'speaker_id' and 'ssml_gender'.
      target_language: The target language (ISO 3166-1 alpha-2).
      client: A TextToSpeechClient object.
      preferred_voices: An optional list of preferred voice names.
      fallback_no_preferred_category_match: If True, assigns None if no voice
        matches preferred category.

  Returns:
      A mapping of unique speaker IDs to assigned voice names, or None if no
      preferred voice was available or fallback_no_preferred_category_match is
      True.
  """

  unique_speaker_mapping = {
      item["speaker_id"]: item["ssml_gender"] for item in utterance_metadata
  }
  if preferred_voices is None:
    return {speaker_id: None for speaker_id in unique_speaker_mapping}
  available_voices = list_available_voices(
      language_code=target_language, client=client
  )
  available_voices_names = list(available_voices.keys())
  grouped_available_preferred_voices = {}
  for preferred_voice in preferred_voices:
    available_preferred_voices = [
        voice for voice in available_voices_names if preferred_voice in voice
    ]
    grouped_available_preferred_voices.update(
        {preferred_voice: available_preferred_voices}
    )
  already_assigned_voices = {"Male": set(), "Female": set()}
  voice_assignment = {}
  for speaker_id, ssml_gender in unique_speaker_mapping.items():
    preferred_category_matched = False
    for (
        preferred_category_voices
    ) in grouped_available_preferred_voices.values():
      if not preferred_category_voices:
        continue
      for preferred_voice in preferred_category_voices:
        if (
            ssml_gender == available_voices[preferred_voice]
            and preferred_voice not in already_assigned_voices[ssml_gender]
        ):
          voice_assignment[speaker_id] = preferred_voice
          already_assigned_voices[ssml_gender].add(preferred_voice)
          preferred_category_matched = True
          break
      if speaker_id in voice_assignment:
        break
    if not preferred_category_matched and fallback_no_preferred_category_match:
      voice_assignment[speaker_id] = None
  for speaker_id in unique_speaker_mapping:
    if speaker_id not in voice_assignment:
      voice_assignment[speaker_id] = None
  return voice_assignment



"""Tests for utility functions in text_to_speech.py."""

from collections import namedtuple
from unittest.mock import MagicMock, patch
from absl.testing import absltest
from absl.testing import parameterized
from ariel import text_to_speech
from google.cloud import texttospeech

AvailableVoice = namedtuple("AvailableVoice", ["name", "ssml_gender"])


class ListAvailableVoicesTest(absltest.TestCase):

  def test_list_available_voices(self):
    mock_client = MagicMock(spec=texttospeech.TextToSpeechClient)
    mock_response = texttospeech.ListVoicesResponse(
        voices=[
            texttospeech.Voice(
                name="en-US-Standard-A",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            ),
            texttospeech.Voice(
                name="en-US-Standard-B",
                ssml_gender=texttospeech.SsmlVoiceGender.MALE,
            ),
            texttospeech.Voice(
                name="en-US-Standard-C",
                ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
            ),
        ]
    )
    mock_client.list_voices.return_value = mock_response
    result = text_to_speech.list_available_voices("en-US", client=mock_client)
    self.assertEqual(
        result,
        {
            "en-US-Standard-A": "Female",
            "en-US-Standard-B": "Male",
            "en-US-Standard-C": "Neutral",
        },
    )


class TestAssignVoices(parameterized.TestCase):

  @parameterized.named_parameters([
      (
          "preferred_voices_match",
          [
              {"speaker_id": "speaker1", "ssml_gender": "Male"},
              {"speaker_id": "speaker2", "ssml_gender": "Female"},
          ],
          ["News", "Studio"],
          {"speaker1": "en-US-News-B", "speaker2": "en-US-Studio-C"},
          True,
      ),
      (
          "no_preferred_voices_match",
          [
              {"speaker_id": "speaker1", "ssml_gender": "Male"},
              {"speaker_id": "speaker2", "ssml_gender": "Female"},
          ],
          ["NonExistent1", "NonExistent2"],
          {"speaker1": None, "speaker2": None},
          True,
      ),
      (
          "no_preferred_voices_no_fallback",
          [
              {"speaker_id": "speaker1", "ssml_gender": "Male"},
              {"speaker_id": "speaker2", "ssml_gender": "Female"},
          ],
          None,
          {"speaker1": None, "speaker2": None},
          False,
      ),
  ])
  def test_assign_voices(
      self,
      utterance_metadata,
      preferred_voices,
      expected_assignment,
      fallback_no_preferred_category_match,
  ):
    mock_client = MagicMock(spec=texttospeech.TextToSpeechClient)
    mock_response = texttospeech.ListVoicesResponse(
        voices=[
            texttospeech.Voice(
                name="en-US-News-B",
                ssml_gender=texttospeech.SsmlVoiceGender.MALE,
            ),
            texttospeech.Voice(
                name="en-US-Studio-C",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            ),
        ]
    )
    mock_client.list_voices.return_value = mock_response

    assignment = text_to_speech.assign_voices(
        utterance_metadata=utterance_metadata,
        target_language="en-US",
        client=mock_client,
        preferred_voices=preferred_voices,
        fallback_no_preferred_category_match=fallback_no_preferred_category_match,
    )
    self.assertEqual(assignment, expected_assignment)


if __name__ == "__main__":
  absltest.main()

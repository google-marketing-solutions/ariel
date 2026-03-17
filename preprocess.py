"""Functions related to pre-processing the video with Gemini."""

# Copyright 2025 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
import logging

from google import genai
from google.genai import types

from models import VoiceData

GEMINI_PROMPT = """Analyse the attached video. Using the response schema,
provide the primary language of the spoken text and a list of voices matched to
the speakers in the order they speak in the video.

For the language, use the BCP-47 code appropriate to the dialect and accent from
the following list: ar-EG, bn-BD, nl-NL, en-IN, en-US, fr-FR, de-DE, hi-IN,
id-ID, it-IT, ja-JP, ko-KR, mr-IN, pl-PL, pt-BR, ro-RO, ru-RU, es-ES, ta-IN,
te-IN, th-TH, tr-TR, uk-UA, vi-VN, af-ZA, sq-AL, am-ET, ar-001, hy-AM, az-AZ,
eu-ES, be-BY, bg-BG, my-MM, ca-ES, ceb-PH, cmn-CN, cmn-tw, hr-HR, cs-CZ, da-DK,
en-AU, en-GB, et-EE, fil-PH, fi-FI, fr-CA, gl-ES, ka-GE, el-GR, gu-IN, ht-HT,
he-IL, hu-HU, is-IS, jv-JV, kn-IN, kok-IN, lo-LA, la-VA, lv-LV, lt-LT, lb-LU,
mk-MK, mai-IN, mg-MG, ms-MY, ml-IN, mn-MN, ne-NP, nb-NO, nn-NO, or-IN, ps-AF,
fa-IR, pt-PT, pa-IN, sr-RS, sd-IN, si-LK, sk-SK, sl-SI, es-419, es-MX, sw-KE,
sv-SE, ur-PK

If a speaker speaks more than once, only include their voice
for the first instance. Match each voice in the video to a voice available for
use with the gemini-2.5-pro-tts API so that the tone, pitch, and energy are as
close as possible. DO NOT use Neural2, WaveNet, or Standard voice names (e.g.,
avoid names like 'en-US-Neural2-A'). Use ONLY the specific Gemini-TTS names like
Achird, Aoede, Kore, or Schedar.

Available Reference List:

Female/Feminine: Achernar, Aoede, Autonoe, Callirrhoe, Despina, Erinome, Gacrux,
Kore, Laomedeia, Leda, Pulcherrima, Sulafat, Vindemiatrix, Zephyr.

Male/Masculine: Achird, Algenib, Algieba, Alnilam, Charon, Enceladus, Fenrir,
Iapetus, Orus, Puck, Rasalgethi, Sadachbia, Sadaltager, Schedar, Umbriel,
Zubenelgenubi."""


def get_gemini_config() -> dict[str, str|float|type[VoiceData]]:
  """Returns the configuration for the Gemini model."""
  return {
      "response_mime_type": "application/json",
      "response_schema": VoiceData,
      "temperature": 0.2,  # Low temperature to keep the results deterministic
  }


def extract_video_details(
    gcs_path: str, gemini_client: genai.Client, model_string: str
) -> VoiceData:
  """Uses Gemini to extract the details of the given video.

  The language, number of speakers, and a TTS voice that is close the
  original speaker's voice for each speaker is extracted.

  Args:
    gcs_path: the path to the video file on GCS.
    gemini_client: the genai.Client to use when prompting Gemini.
    model_string: the model string for the Gemini model to use.

  Returns:
    A VoiceData object with the extracted metadata.
  """
  video_part = types.Part.from_uri(file_uri=gcs_path, mime_type="video/mp4")

  gemini_response = gemini_client.models.generate_content(
      model=model_string,
      contents=[video_part, GEMINI_PROMPT],
      config=get_gemini_config(),
  )

  data: VoiceData = gemini_response.parsed
  ### DEBUG
  print(f'#### DEBUG #### Preprocessed Data: {data}')
  ### DEBUG
  return data

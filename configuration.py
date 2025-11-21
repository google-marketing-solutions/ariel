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

import os
from dataclasses import dataclass


@dataclass
class Config:
    gcp_project_id: str
    gcp_project_location: str
    gcs_bucket_name: str
    gemini_model: str
    gemini_flash_model: str
    gemini_pro_model: str
    audio_format: str
    video_format: str
    gemini_tts_model: str
    gemini_flash_tts_model: str
    gemini_pro_tts_model: str


def get_config() -> Config:
    """
  Reads configuration from environment variables and returns a Config object.
  """
    return Config(
        gcp_project_id=os.environ.get('GCP_PROJECT_ID'),
        gcp_project_location=os.environ.get('GCP_PROJECT_LOCATION'),
        gcs_bucket_name=os.environ.get('GCS_BUCKET_NAME'),
        gemini_model=os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash'),
        gemini_flash_model=os.environ.get('GEMINI_FLASH_MODEL',
                                          'gemini-2.5-flash'),
        gemini_pro_model=os.environ.get('GEMINI_PRO_MODEL', 'gemini-2.5-pro'),
        audio_format=os.environ.get('AUDIO_FORMAT', 'mp3'),
        video_format=os.environ.get('VIDEO_FORMAT', 'mp4'),
        gemini_tts_model=os.environ.get('GEMINI_TTS_MODEL',
                                        'gemini-2.5-pro-tts'),
        gemini_flash_tts_model=os.environ.get('GEMINI_FLASH_TTS_MODEL',
                                              'gemini-2.5-flash-tts'),
        gemini_pro_tts_model=os.environ.get('GEMINI_PRO_TTS_MODEL',
                                            'gemini-2.5-pro-tts'),
    )

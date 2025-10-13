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
from typing import Optional


@dataclass
class Config:
    gcp_project_id: str
    gcp_project_location: str
    gcs_bucket_name: str
    gemini_model: str
    audio_format: str
    video_format: str
    gemini_api_key: str
    gemini_tts_model: str


def get_config() -> Config:
    """
  Reads configuration from environment variables and returns a Config object.
  """
    return Config(
        gcp_project_id=os.environ.get('GCP_PROJECT_ID'),
        gcp_project_location=os.environ.get('GCP_PROJECT_LOCATION'),
        gcs_bucket_name=os.environ.get('GCS_BUCKET_NAME'),
        gemini_model=os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash'),
        audio_format=os.environ.get('AUDIO_FORMAT', 'mp3'),
        video_format=os.environ.get('VIDEO_FORMAT', 'mp4'),
        gemini_api_key=os.environ.get('GEMINI_API_KEY'),
        gemini_tts_model=os.environ.get('GEMINI_TTS_MODEL',
                                        'gemini-2.5-flash-preview-tts'),
    )

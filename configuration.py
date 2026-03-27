"""The configuration for Ariel."""

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

import dataclasses
import os


@dataclasses.dataclass
class Config:
  """Represents the configuration of an Ariel deployment.

  Attrubutes:
    gcp_project_id: The ID of the GCP project Ariel is deployed in.
    gcp_project_location: The GCP region Ariel is deployed in.
    gcs_bucket_name: The GCS bucket to store assets in.
    gemini_flash_model: The model string to use when the flash model is chosen.
    gemini_pro_model: The model string to use when the pro model is chosen.
    gemini_flash_tts_model: The model string to use with TTS when flash is
    chosen.
    gemini_pro_tts_model: The model string to use with TTS when pro is chosen.
  """

  gcp_project_id: str
  gcp_project_location: str
  gcs_bucket_name: str
  gemini_flash_model: str
  gemini_pro_model: str
  gemini_flash_tts_model: str
  gemini_pro_tts_model: str


def get_config() -> Config:
  """Reads configuration from environment variables and returns a Config object."""
  return Config(
      gcp_project_id=os.environ.get("GCP_PROJECT_ID") or "",
      gcp_project_location=os.environ.get("GCP_PROJECT_LOCATION") or "",
      gcs_bucket_name=os.environ.get("GCS_BUCKET_NAME") or "",
      gemini_flash_model=os.environ.get(
          "GEMINI_FLASH_MODEL", "gemini-3-flash-preview"
      ),
      gemini_pro_model=os.environ.get(
          "GEMINI_PRO_MODEL", "gemini-3.1-pro-preview"
      ),
      gemini_flash_tts_model=os.environ.get(
          "GEMINI_FLASH_TTS_MODEL", "gemini-2.5-flash-tts"
      ),
      gemini_pro_tts_model=os.environ.get(
          "GEMINI_PRO_TTS_MODEL", "gemini-2.5-pro-tts"
      ),
  )

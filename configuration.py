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

from typing import NamedTuple
import yaml


class ArielConfig(NamedTuple):
  gcp_project_id: str
  gcs_bucket_name: str
  gemini_model: str


def get_config(config_path: str="configuration.yaml") -> ArielConfig:
  with open(config_path) as config_file:
    config = yaml.safe_load(config_file)
    return ArielConfig(
      gcp_project_id=config["gcp_project_id"],
      gcs_bucket_name=config["gcs_bucket_name"],
      gemini_model=config["gemini_model"]
    )

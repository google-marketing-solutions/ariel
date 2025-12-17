#!/bin/bash

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

if [ -f "configuration.yaml" ]; then
  eval $(python3 -c 'import yaml, sys;
config = yaml.safe_load(sys.stdin);
if config:
  for k, v in config.items():
    print(f"export {k}=\"{v}\"")' < configuration.yaml)
fi

uvicorn main:app --host 0.0.0.0 --port 8080 --reload

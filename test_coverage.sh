#!/bin/bash

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

rm -f coverage_report.txt

echo "Python test coverage" >> coverage_report.txt
uv sync --dev
coverage run \
  --source=. \
  --omit="tests/*,.venv/*,*/site-packages/*" \
  -m unittest discover -s tests \
  && coverage report -m >> coverage_report.txt

echo "" >> coverage_report.txt
echo "JavaScript test coverage" >> coverage_report.txt
npm test -- --coverage >> coverage_report.txt

cat coverage_report.txt

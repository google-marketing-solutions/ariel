# Copyright 2025 Google LLC
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

FROM python:3.12

ENV PROJECT_ID "my-project-id"

ENV REGION "us-central1"

WORKDIR /app

COPY . /app

RUN sed -i "s/\$PROJECT_ID/${PROJECT_ID}/g" /app/templates/index.html

RUN sed -i "s/\$REGION/${REGION}/g" /app/templates/index.html

RUN apt-get -y update && apt-get -y upgrade && apt-get install -y --no-install-recommends ffmpeg && apt-get install -y --no-install-recommends libsox-dev

RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8080

CMD ["uvicorn", "main:app", "--reload", "--log-level", "debug", "--host", "0.0.0.0", "--port", "8080"]
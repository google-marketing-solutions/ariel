FROM python:3.12-slim
USER root

RUN apt-get -y update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg && \
  rm -rf /var/cache/apt && \
  apt-get clean

WORKDIR /app
COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
ENV HF_HOME=/app/models
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

COPY . ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

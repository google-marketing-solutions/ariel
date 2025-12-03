FROM python:3.13
USER root
RUN apt-get -y update
RUN apt-get install -y ffmpeg

WORKDIR /app
COPY . ./
RUN pip install --no-cache-dir -r requirements.txt

ENV HF_HOME=/app/models
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

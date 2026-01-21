FROM python:3.13
USER root
RUN apt-get -y update && \
  apt-get install -y ffmpeg && \
  rm -rf /var/cache/apt && \
  apt-get clean

WORKDIR /app
COPY ./requirements.txt ./
RUN pip install -r requirements.txt
ENV HF_HOME=/app/models
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

COPY . ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

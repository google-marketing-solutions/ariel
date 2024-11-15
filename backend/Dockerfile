FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

#python for running app, ffmpeg for video editing
RUN apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip python3-dev python-is-python3 tzdata ffmpeg && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /ariel
COPY requirements.txt .
RUN pip install -r ./requirements.txt

COPY app.py .

ENV PORT 8080
CMD exec gunicorn -b 0.0.0.0:$PORT -t 600 -w 7 app:app

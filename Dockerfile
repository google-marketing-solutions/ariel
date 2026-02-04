FROM python:3.13-slim
USER root

RUN apt-get -y update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg && \
  rm -rf /var/cache/apt && \
  apt-get clean

WORKDIR /app
RUN pip install uv
COPY ./pyproject.toml ./
COPY ./uv.lock ./
RUN uv sync --no-dev
ENV HF_HOME=/app/models
RUN uv run python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

COPY . ./

CMD ["uv", "run", "--no-dev", "--no-sync", "--frozen", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

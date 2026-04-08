FROM python:3.13-slim
USER root

RUN apt-get -y update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg build-essential && \
  rm -rf /var/cache/apt && \
  apt-get clean

WORKDIR /app
RUN pip install uv
COPY ./pyproject.toml ./
COPY ./uv.lock ./
RUN uv sync --no-dev

# Copy everything, including the locally built frontend (un-ignored in .gcloudignore)
COPY . ./

CMD ["uv", "run", "--no-dev", "--no-sync", "--frozen", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.13
USER root
RUN apt-get -y update
RUN apt-get install -y ffmpeg

WORKDIR /app
COPY . ./
RUN pip install --no-cache-dir -r requirements.txt

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

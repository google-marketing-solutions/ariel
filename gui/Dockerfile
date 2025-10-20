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
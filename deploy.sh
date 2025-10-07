uv pip freeze > requirements.txt
gcloud run deploy ariel --source . --region=us-central1 --quiet

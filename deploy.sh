# Build requirements.txt needed for cloud run but skipping the local file output from uv
pipx run uv pip compile pyproject.toml -o requirements.txt

# Deploy and capture the exit code
gcloud beta run deploy ariel --source . --region=us-central1 --quiet --iap

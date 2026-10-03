@echo off
echo Memulai Deployment ke Google Cloud Run / App Engine...
gcloud app deploy app.yaml --project=duel-masters-ai
pause
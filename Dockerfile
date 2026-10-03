FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn flask-cors

COPY . .

ENV PORT=8080
EXPOSE $PORT

CMD gunicorn --bind 0.0.0.0:$PORT duel_masters.app:app

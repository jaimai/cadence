# Image for the API. Build context: apps/api.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# One container does everything: migrations, API and the publishing worker.
ENV EMBED_WORKER=true

CMD ["./deploy/start.sh"]

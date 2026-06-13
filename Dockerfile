# syntax=docker/dockerfile:1
# ---- Stage 1: build deps and train the model ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

COPY constants.py utils.py ./
COPY ml/ ./ml/
# Train at build time so the image ships ready-to-serve. Mount a real BTS CSV
# at /build/data/flights.csv to train on real data instead of synthetic.
RUN python -m ml.train

# ---- Stage 2: slim runtime ----
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    FDP_MODEL_PATH=/app/models/model.pkl \
    FDP_METRICS_PATH=/app/models/metrics.json
WORKDIR /app

# libgomp1 is required by xgboost at runtime; curl powers the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY --from=builder /install /usr/local
COPY --from=builder /build/models/ ./models/

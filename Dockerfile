# syntax=docker/dockerfile:1
# ---- Stage 1: build deps and train the model ----
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build

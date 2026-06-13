"""FastAPI application: /predict, /health, /stats."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import configure_logging, settings
from app.model import ModelNotLoadedError, model
from app.schemas import (
    FlightRequest,
    HealthResponse,
    PredictionResponse,
    StatsResponse,
)

configure_logging()
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once at startup so every request hits a warm pipeline.
    try:
        model.load()
    except FileNotFoundError as exc:
        # Don't crash — /health reports not-ready so the LB drains this instance.
        logger.error("Startup: %s", exc)
    yield

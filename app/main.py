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

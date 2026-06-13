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


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Predicts the probability that a US domestic flight departs >15 min late.",
    lifespan=lifespan,
)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
    request.state.request_id = request_id
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.exception(
            "Unhandled error",
            extra={"request_id": request_id, "path": request.url.path,
                   "method": request.method, "latency_ms": round(latency_ms, 2)},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )
    latency_ms = (time.perf_counter() - t0) * 1000
    response.headers["x-request-id"] = request_id
    response.headers["x-process-time-ms"] = f"{latency_ms:.2f}"
    logger.info(
        "request",
        extra={"request_id": request_id, "path": request.url.path,
               "method": request.method, "status_code": response.status_code,
               "latency_ms": round(latency_ms, 2)},
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "request_id": request_id})


@app.exception_handler(ModelNotLoadedError)
async def model_not_loaded_handler(request: Request, exc: ModelNotLoadedError):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=503,
        content={"detail": "Model not loaded; service unavailable.", "request_id": request_id},
    )


@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health():
    """Liveness/readiness probe. Returns 200 only when the model is loaded."""
    loaded = model.loaded
    return JSONResponse(
        status_code=200 if loaded else 503,
        content=HealthResponse(
            status="ok" if loaded else "degraded",
            version=settings.version,
            model_loaded=loaded,
        ).model_dump(),
    )

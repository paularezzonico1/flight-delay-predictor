"""FastAPI application: /predict, /health, /stats."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.cache import build_cache
from app.cache.base import cache_key
from app.config import configure_logging, settings
from app.metrics import metrics
from app.model import ModelNotLoadedError, model
from app.repositories import PredictionRecord
from app.repositories.factory import build_repository
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
    # ModelService falls back to the heuristic strategy if the artifact is
    # missing, so this no longer crashes on a cold image.
    model.load()
    # Repository and cache pick concrete vs no-op backends from configuration,
    # so the service runs identically with or without RDS/Redis.
    app.state.repo = build_repository()
    app.state.cache = build_cache()
    yield
    metrics.flush()


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
    # jsonable_encoder coerces non-serializable error context (e.g. a ValueError
    # raised inside a custom validator) so JSONResponse can render it.
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({"detail": exc.errors(), "request_id": request_id}),
    )


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


@app.get("/stats", response_model=StatsResponse, tags=["ops"])
async def stats():
    """Model metadata and offline evaluation metrics."""
    md = model.metadata
    if not md:
        return JSONResponse(status_code=503, content={"detail": "Metrics unavailable."})
    return StatsResponse(
        model_type=md.get("model_type", "unknown"),
        target=md.get("target", "departure delay > 15 min"),
        features=md.get("features", []),
        trained_at=md.get("trained_at"),
        n_train=md.get("n_train"),
        n_test=md.get("n_test"),
        metrics=md.get("metrics", {}),
        known_airlines=md.get("known_airlines", []),
        known_airports=md.get("known_airports", []),
    )


def _log_prediction(repo, request_id, flight: FlightRequest, route: str, payload: dict) -> None:
    """Persist a served prediction via the repository (no-op without a DB)."""
    repo.log_prediction(
        PredictionRecord(
            request_id=request_id,
            carrier=flight.airline,
            origin=flight.origin,
            destination=flight.destination,
            route=route,
            month=flight.month,
            day_of_week=flight.day_of_week,
            dep_hour=flight.dep_hour,
            delay_probability=payload["delay_probability"],
            will_be_delayed=payload["will_be_delayed"],
            risk_level=payload["risk_level"],
            model_version=payload["model_version"],
            latency_ms=payload["latency_ms"],
            cache_hit=payload["cache_hit"],
        )
    )


@app.post("/predict", response_model=PredictionResponse, tags=["inference"])
async def predict(flight: FlightRequest, request: Request):
    """Return the delay probability for a single flight.

    Repeat (route, carrier, time-of-day) requests are served from the Redis
    cache, skipping model inference. Every request — hit or miss — is logged to
    RDS for audit, tagged with whether it was a cache hit.
    """
    repo = request.app.state.repo
    cache = request.app.state.cache
    request_id = getattr(request.state, "request_id", None)
    route = f"{flight.origin}-{flight.destination}"
    key = cache_key(route, flight.airline, flight.dep_hour)

    cached = cache.get(key)
    if cached is not None:
        cached["cache_hit"] = True
        _log_prediction(repo, request_id, flight, route, cached)
        metrics.record_prediction(cached["latency_ms"], True, model.active_strategy)
        return PredictionResponse(**cached)

    payload = model.predict(flight)
    cache.set(key, payload)
    _log_prediction(repo, request_id, flight, route, payload)
    metrics.record_prediction(payload["latency_ms"], False, model.active_strategy)
    return PredictionResponse(**payload)


@app.get("/predictions/recent", tags=["inference"])
async def recent_prediction(
    request: Request,
    origin: str,
    destination: str,
    airline: str,
    dep_hour: int,
):
    """Most recent stored prediction for a route/carrier/time-of-day.

    Backed by the ``(route, carrier)`` index on the predictions table (see
    migrations). Returns 404 when nothing has been logged yet (or no DB).
    """
    route = f"{origin.strip().upper()}-{destination.strip().upper()}"
    hit = request.app.state.repo.find_recent(route, airline.strip().upper(), dep_hour)
    if hit is None:
        return JSONResponse(status_code=404, content={"detail": "No prior prediction found."})
    return hit


@app.get("/", tags=["ops"])
async def root():
    return {"service": settings.app_name, "version": settings.version, "docs": "/docs"}

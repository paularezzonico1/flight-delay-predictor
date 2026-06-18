"""Application configuration and structured JSON logging."""
from __future__ import annotations

import json
import logging
import sys
import time

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_", env_file=".env", extra="ignore")

    app_name: str = "Flight Delay Predictor"
    version: str = "1.0.0"
    model_path: str = "models/model.pkl"
    metrics_path: str = "models/metrics.json"
    log_level: str = "INFO"
    # Probability >= this is reported as `will_be_delayed: true`.
    decision_threshold: float = 0.5

    # --- Persistence (RDS Postgres) ---------------------------------------
    # SQLAlchemy URL, e.g. postgresql+psycopg://user:pass@host:5432/fdp.
    # When empty, prediction logging is disabled (a NullPredictionRepository
    # is used) so the service runs identically offline and in CI.
    database_url: str = ""
    db_pool_size: int = 5
    db_pool_max_overflow: int = 5

    # --- Cache (Redis) ----------------------------------------------------
    # e.g. redis://localhost:6379/0. Empty disables caching (NullCache).
    redis_url: str = ""
    cache_ttl_seconds: int = 300

    # --- Observability (CloudWatch custom metrics) ------------------------
    # Empty namespace disables metric publishing (no-op without AWS creds).
    cloudwatch_namespace: str = ""
    aws_region: str = "us-east-1"


settings = Settings()


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line — friendly to CloudWatch / ELK."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "path", "method", "status_code", "latency_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    # Quiet uvicorn's default access logs; we emit our own structured ones.
    logging.getLogger("uvicorn.access").handlers = []

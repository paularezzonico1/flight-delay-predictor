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

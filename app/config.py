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

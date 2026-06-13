"""Model loading and inference. The pipeline is loaded once at process start."""
from __future__ import annotations

import json
import logging
import os
import time

import joblib
import pandas as pd

from app.config import settings
from app.schemas import FlightRequest
from constants import FEATURES
from utils import risk_level

logger = logging.getLogger(__name__)


class ModelNotLoadedError(RuntimeError):
    """Raised when a prediction is attempted before the model is available."""


class DelayModel:
    def __init__(self) -> None:
        self._pipeline = None
        self._metadata: dict = {}

    def load(self) -> None:
        path = settings.model_path
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model not found at {path!r}. Run `python -m ml.train` first."
            )
        t0 = time.perf_counter()
        self._pipeline = joblib.load(path)
        if os.path.exists(settings.metrics_path):
            with open(settings.metrics_path) as fh:
                self._metadata = json.load(fh)
        logger.info("Model loaded from %s in %.1f ms", path, (time.perf_counter() - t0) * 1000)

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    @property
    def metadata(self) -> dict:
        return self._metadata

    @property
    def version(self) -> str:
        return self._metadata.get("trained_at", "unknown")

    def _validate_known(self, flight: FlightRequest) -> list[str]:
        """Warn (don't reject) on unseen categories — OneHotEncoder ignores them."""
        warnings: list[str] = []
        airlines = set(self._metadata.get("known_airlines", []))
        airports = set(self._metadata.get("known_airports", []))
        if airlines and flight.airline not in airlines:
            warnings.append(f"Unknown airline '{flight.airline}'; prediction may be unreliable.")
        if airports and flight.origin not in airports:
            warnings.append(f"Unknown origin '{flight.origin}'; prediction may be unreliable.")
        if airports and flight.destination not in airports:
            warnings.append(f"Unknown destination '{flight.destination}'; prediction may be unreliable.")
        return warnings

    def predict(self, flight: FlightRequest) -> dict:
        if not self.loaded:
            raise ModelNotLoadedError("Model is not loaded.")

        warnings = self._validate_known(flight)
        row = pd.DataFrame(
            [[
                flight.airline, flight.origin, flight.destination,
                flight.month, flight.day_of_week, flight.dep_hour,
            ]],
            columns=FEATURES,
        )

        t0 = time.perf_counter()
        proba = float(self._pipeline.predict_proba(row)[0, 1])
        latency_ms = (time.perf_counter() - t0) * 1000

        threshold = settings.decision_threshold
        return {
            "delay_probability": round(proba, 4),
            "will_be_delayed": proba >= threshold,
            "threshold": threshold,
            "risk_level": risk_level(proba),
            "model_version": self.version,
            "latency_ms": round(latency_ms, 3),
            "warnings": warnings,
        }

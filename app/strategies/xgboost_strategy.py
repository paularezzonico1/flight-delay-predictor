"""Production strategy: the trained XGBoost pipeline loaded from model.pkl."""
from __future__ import annotations

import json
import logging
import os

import joblib
import pandas as pd

from app.config import settings
from app.schemas import FlightRequest
from app.strategies.base import PredictionStrategy, StrategyResult
from constants import FEATURES

logger = logging.getLogger(__name__)


class XGBoostStrategy(PredictionStrategy):
    name = "xgboost"

    def __init__(self) -> None:
        self._pipeline = None
        self._metadata: dict = {}

    def load(self) -> None:
        path = settings.model_path
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Model not found at {path!r}. Run `python -m ml.train` first."
            )
        self._pipeline = joblib.load(path)
        if os.path.exists(settings.metrics_path):
            with open(settings.metrics_path) as fh:
                self._metadata = json.load(fh)
        logger.info("XGBoost strategy loaded from %s", path)

    @property
    def available(self) -> bool:
        return self._pipeline is not None

    @property
    def metadata(self) -> dict:
        return self._metadata

    @property
    def model_version(self) -> str:
        return self._metadata.get("trained_at", "unknown")

    def _unknown_category_warnings(self, flight: FlightRequest) -> list[str]:
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

    def predict(self, flight: FlightRequest) -> StrategyResult:
        row = pd.DataFrame(
            [[
                flight.airline, flight.origin, flight.destination,
                flight.month, flight.day_of_week, flight.dep_hour,
            ]],
            columns=FEATURES,
        )
        proba = float(self._pipeline.predict_proba(row)[0, 1])
        return StrategyResult(
            delay_probability=proba,
            model_version=self.model_version,
            warnings=self._unknown_category_warnings(flight),
        )

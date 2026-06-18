"""Fallback strategy: a transparent base-rate heuristic.

Used when the XGBoost artifact is missing or fails to load, so the service keeps
answering (clearly flagged as degraded via the model version and a warning)
instead of returning 503s. It reuses the same carrier/airport/time effects that
shape the documented BTS-like delay distribution, combined on the logit scale.
"""
from __future__ import annotations

import logging
import math

from app.schemas import FlightRequest
from app.strategies.base import PredictionStrategy, StrategyResult
from constants import AIRLINES, AIRPORTS
from ml.generate_data import _dow_effect, _hour_effect, _month_effect

logger = logging.getLogger(__name__)

# Population means used to centre each effect (kept in step with ml/generate_data).
_AIRLINE_BASE = 0.18
_AIRPORT_BASE = 0.045


class FallbackStrategy(PredictionStrategy):
    name = "fallback-heuristic"

    @property
    def model_version(self) -> str:
        return "fallback-heuristic-v1"

    def load(self) -> None:
        logger.warning("FallbackStrategy active — serving base-rate heuristic, not XGBoost.")

    @property
    def available(self) -> bool:
        # Pure function of the request; always ready.
        return True

    def predict(self, flight: FlightRequest) -> StrategyResult:
        airline_e = AIRLINES.get(flight.airline, _AIRLINE_BASE)
        origin_e = AIRPORTS.get(flight.origin, _AIRPORT_BASE)
        dest_e = AIRPORTS.get(flight.destination, _AIRPORT_BASE)

        z = (
            -2.4
            + 20.0 * (airline_e - _AIRLINE_BASE)
            + 16.0 * (origin_e - _AIRPORT_BASE)
            + 7.0 * (dest_e - _AIRPORT_BASE)
            + 14.0 * (_hour_effect(flight.dep_hour) - 0.09)
            + 18.0 * _month_effect(flight.month)
            + 14.0 * _dow_effect(flight.day_of_week)
        )
        proba = 1.0 / (1.0 + math.exp(-z))
        return StrategyResult(
            delay_probability=proba,
            model_version=self.model_version,
            warnings=["Serving heuristic fallback; XGBoost model unavailable."],
        )

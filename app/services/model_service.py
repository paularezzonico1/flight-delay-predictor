"""Model service: holds the active prediction strategy and assembles responses.

Calling code (the API routes) talks only to this service and never to a concrete
strategy. At load time it prefers the production strategy (XGBoost) and falls
back to the heuristic if the model artifact is unavailable — the swap is
invisible to callers.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from app.config import settings
from app.schemas import FlightRequest
from app.strategies.base import PredictionStrategy
from app.strategies.errors import ModelNotLoadedError
from app.strategies.fallback_strategy import FallbackStrategy
from app.strategies.xgboost_strategy import XGBoostStrategy
from utils import risk_level

logger = logging.getLogger(__name__)


class ModelService:
    def __init__(
        self,
        primary: Optional[PredictionStrategy] = None,
        fallback: Optional[PredictionStrategy] = None,
    ) -> None:
        self._primary = primary or XGBoostStrategy()
        self._fallback = fallback or FallbackStrategy()
        self._active: Optional[PredictionStrategy] = None

    def load(self) -> None:
        """Activate the primary strategy, falling back to the heuristic on failure."""
        try:
            self._primary.load()
            if self._primary.available:
                self._active = self._primary
                logger.info("Active prediction strategy: %s", self._active.name)
                return
        except Exception as exc:  # noqa: BLE001 - any load failure should degrade, not crash.
            logger.error("Primary strategy '%s' failed to load: %s", self._primary.name, exc)

        self._fallback.load()
        self._active = self._fallback
        logger.warning("Active prediction strategy: %s (degraded)", self._active.name)

    @property
    def loaded(self) -> bool:
        return self._active is not None and self._active.available

    @property
    def active_strategy(self) -> str:
        return self._active.name if self._active else "none"

    @property
    def metadata(self) -> dict:
        return self._active.metadata if self._active else {}

    @property
    def version(self) -> str:
        md = self.metadata
        return md.get("trained_at", self.active_strategy)

    def predict(self, flight: FlightRequest) -> dict:
        if not self.loaded:
            raise ModelNotLoadedError("No prediction strategy is available.")

        t0 = time.perf_counter()
        result = self._active.predict(flight)
        latency_ms = (time.perf_counter() - t0) * 1000

        threshold = settings.decision_threshold
        proba = result.delay_probability
        return {
            "delay_probability": round(proba, 4),
            "will_be_delayed": proba >= threshold,
            "threshold": threshold,
            "risk_level": risk_level(proba),
            "model_version": result.model_version,
            "latency_ms": round(latency_ms, 3),
            "warnings": result.warnings,
            "cache_hit": False,
        }

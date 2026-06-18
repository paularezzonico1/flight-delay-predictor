"""Strategy-pattern tests: fallback heuristic and active-strategy selection."""
from __future__ import annotations

import pytest

from app.schemas import FlightRequest
from app.services.model_service import ModelService
from app.strategies.base import PredictionStrategy, StrategyResult
from app.strategies.errors import ModelNotLoadedError
from app.strategies.fallback_strategy import FallbackStrategy


def _flight(**kw) -> FlightRequest:
    base = dict(airline="B6", origin="JFK", destination="SFO",
                month=7, day_of_week=5, dep_hour=18)
    base.update(kw)
    return FlightRequest(**base)


def test_fallback_strategy_returns_valid_probability():
    strat = FallbackStrategy()
    strat.load()
    result = strat.predict(_flight())
    assert isinstance(result, StrategyResult)
    assert 0.0 <= result.delay_probability <= 1.0
    assert result.model_version == "fallback-heuristic-v1"


def test_service_falls_back_when_primary_unavailable():
    class BrokenPrimary(PredictionStrategy):
        name = "broken"

        def load(self):
            raise FileNotFoundError("no model")

        @property
        def available(self):
            return False

        def predict(self, flight):  # pragma: no cover - never reached
            raise AssertionError

    service = ModelService(primary=BrokenPrimary(), fallback=FallbackStrategy())
    service.load()
    assert service.loaded
    assert service.active_strategy == "fallback-heuristic"
    payload = service.predict(_flight())
    assert 0.0 <= payload["delay_probability"] <= 1.0
    assert payload["cache_hit"] is False


def test_service_prefers_available_primary():
    class GoodPrimary(PredictionStrategy):
        name = "good"

        def load(self):
            pass

        @property
        def available(self):
            return True

        def predict(self, flight):
            return StrategyResult(delay_probability=0.99, model_version="good-v1")

    service = ModelService(primary=GoodPrimary(), fallback=FallbackStrategy())
    service.load()
    assert service.active_strategy == "good"
    assert service.predict(_flight())["model_version"] == "good-v1"


def test_predict_before_load_raises():
    service = ModelService(primary=FallbackStrategy(), fallback=FallbackStrategy())
    with pytest.raises(ModelNotLoadedError):
        service.predict(_flight())

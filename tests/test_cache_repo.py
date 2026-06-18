"""Cache and repository tests using null/in-memory backends (no infra)."""
from __future__ import annotations

from datetime import datetime, timezone

from app.cache.base import NullCache, cache_key
from app.repositories.base import PredictionRecord
from app.repositories.null_repository import NullPredictionRepository


def test_cache_key_is_stable_and_specific():
    assert cache_key("JFK-SFO", "B6", 18) == "pred:JFK-SFO:B6:18"
    assert cache_key("JFK-SFO", "B6", 18) != cache_key("JFK-SFO", "B6", 19)


def test_null_cache_always_misses():
    cache = NullCache()
    cache.set("pred:JFK-SFO:B6:18", {"delay_probability": 0.4})
    assert cache.get("pred:JFK-SFO:B6:18") is None


def test_null_repository_is_inert():
    repo = NullPredictionRepository()
    repo.log_prediction(
        PredictionRecord(
            request_id="abc", carrier="B6", origin="JFK", destination="SFO",
            route="JFK-SFO", month=7, day_of_week=5, dep_hour=18,
            delay_probability=0.4, will_be_delayed=False, risk_level="moderate",
            model_version="x", latency_ms=1.2,
        )
    )
    assert repo.find_recent("JFK-SFO", "B6", 18) is None
    now = datetime.now(timezone.utc)
    assert repo.count_in_window(now, now) == 0
    assert repo.healthy() is True

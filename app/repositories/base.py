"""Abstract repository contract for prediction persistence."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class PredictionRecord:
    """A persisted prediction. Mirrors :class:`app.db.models.PredictionLog`
    but is a plain value object, so callers never depend on the ORM."""

    request_id: Optional[str]
    carrier: str
    origin: str
    destination: str
    route: str
    month: int
    day_of_week: int
    dep_hour: int
    delay_probability: float
    will_be_delayed: bool
    risk_level: str
    model_version: str
    latency_ms: float
    cache_hit: bool = False


class AbstractPredictionRepository(ABC):
    """All RDS access for predictions goes through this interface.

    Implementations: :class:`SqlPredictionRepository` (Postgres) and
    :class:`NullPredictionRepository` (no database configured).
    """

    @abstractmethod
    def log_prediction(self, record: PredictionRecord) -> None:
        """Persist a single prediction request/response."""

    @abstractmethod
    def find_recent(self, route: str, carrier: str, dep_hour: int) -> Optional[dict]:
        """Return the most recent prediction for a route/carrier/time-of-day,
        or ``None``. This is the query the ``(route, carrier)`` index serves."""

    @abstractmethod
    def count_in_window(self, start: datetime, end: datetime) -> int:
        """Count predictions persisted within ``[start, end)`` — used to derive
        a real writes/sec figure after a load test."""

    def healthy(self) -> bool:
        """Whether the backing store is reachable. Defaults to True."""
        return True

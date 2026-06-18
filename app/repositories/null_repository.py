"""No-op repository used when no database is configured.

Lets the service run end-to-end offline (CI, local tests, demos) without an
RDS instance: predictions simply aren't persisted and lookups always miss.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.repositories.base import AbstractPredictionRepository, PredictionRecord


class NullPredictionRepository(AbstractPredictionRepository):
    def log_prediction(self, record: PredictionRecord) -> None:
        return None

    def find_recent(self, route: str, carrier: str, dep_hour: int) -> Optional[dict]:
        return None

    def count_in_window(self, start: datetime, end: datetime) -> int:
        return 0

    def healthy(self) -> bool:
        # Always "healthy" — there is nothing to reach.
        return True

"""Repository layer.

The Repository pattern wraps *all* RDS access behind a small interface so no
other part of the service constructs SQL or touches a SQLAlchemy session
directly. This decouples the API/serving code from the persistence technology:
the same callers work against Postgres, a null/no-op backend (offline), or a
future store, with no change to the call sites.
"""
from app.repositories.base import (
    AbstractPredictionRepository,
    PredictionRecord,
)
from app.repositories.null_repository import NullPredictionRepository
from app.repositories.prediction_repository import SqlPredictionRepository

__all__ = [
    "AbstractPredictionRepository",
    "PredictionRecord",
    "NullPredictionRepository",
    "SqlPredictionRepository",
]

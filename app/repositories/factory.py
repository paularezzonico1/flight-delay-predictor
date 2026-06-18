"""Repository selection.

Returns a Postgres-backed repository when a database is configured, otherwise a
no-op one. Callers depend only on :class:`AbstractPredictionRepository`.
"""
from __future__ import annotations

import logging

from app.db.engine import get_sessionmaker
from app.repositories.base import AbstractPredictionRepository
from app.repositories.null_repository import NullPredictionRepository
from app.repositories.prediction_repository import SqlPredictionRepository

logger = logging.getLogger(__name__)


def build_repository() -> AbstractPredictionRepository:
    session_factory = get_sessionmaker()
    if session_factory is None:
        logger.info("Using NullPredictionRepository (no database configured).")
        return NullPredictionRepository()
    logger.info("Using SqlPredictionRepository.")
    return SqlPredictionRepository(session_factory)

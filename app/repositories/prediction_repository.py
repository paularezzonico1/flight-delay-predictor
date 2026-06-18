"""Postgres-backed prediction repository.

This is the *only* place in the service that issues queries against RDS. It
maps between the :class:`PredictionRecord` value object and the
:class:`PredictionLog` ORM row, and exposes the route/carrier lookup that the
``idx_predictions_route_carrier`` index serves.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.db.models import PredictionLog
from app.repositories.base import AbstractPredictionRepository, PredictionRecord

logger = logging.getLogger(__name__)


class SqlPredictionRepository(AbstractPredictionRepository):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def log_prediction(self, record: PredictionRecord) -> None:
        row = PredictionLog(
            request_id=record.request_id,
            carrier=record.carrier,
            origin=record.origin,
            destination=record.destination,
            route=record.route,
            month=record.month,
            day_of_week=record.day_of_week,
            dep_hour=record.dep_hour,
            delay_probability=record.delay_probability,
            will_be_delayed=record.will_be_delayed,
            risk_level=record.risk_level,
            model_version=record.model_version,
            latency_ms=record.latency_ms,
            cache_hit=record.cache_hit,
        )
        try:
            with self._session_factory() as session:
                session.add(row)
                session.commit()
        except SQLAlchemyError:
            # Logging a prediction must never fail the request itself.
            logger.exception("Failed to persist prediction for route=%s", record.route)

    def find_recent(self, route: str, carrier: str, dep_hour: int) -> Optional[dict]:
        """Most recent prediction for this route/carrier/time-of-day.

        The WHERE clause leads with ``route`` and ``carrier`` to hit
        ``idx_predictions_route_carrier``; see migration 002.
        """
        stmt = (
            select(
                PredictionLog.delay_probability,
                PredictionLog.will_be_delayed,
                PredictionLog.risk_level,
                PredictionLog.model_version,
            )
            .where(
                PredictionLog.route == route,
                PredictionLog.carrier == carrier,
                PredictionLog.dep_hour == dep_hour,
            )
            .order_by(PredictionLog.created_at.desc())
            .limit(1)
        )
        try:
            with self._session_factory() as session:
                hit = session.execute(stmt).first()
        except SQLAlchemyError:
            logger.exception("find_recent failed for route=%s carrier=%s", route, carrier)
            return None
        if hit is None:
            return None
        return {
            "delay_probability": hit.delay_probability,
            "will_be_delayed": hit.will_be_delayed,
            "risk_level": hit.risk_level,
            "model_version": hit.model_version,
        }

    def count_in_window(self, start: datetime, end: datetime) -> int:
        stmt = select(func.count()).select_from(PredictionLog).where(
            PredictionLog.created_at >= start,
            PredictionLog.created_at < end,
        )
        with self._session_factory() as session:
            return int(session.execute(stmt).scalar_one())

    def healthy(self) -> bool:
        try:
            with self._session_factory() as session:
                session.execute(select(1))
            return True
        except SQLAlchemyError:
            logger.warning("Database health check failed.")
            return False

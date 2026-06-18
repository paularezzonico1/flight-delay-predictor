"""SQLAlchemy engine and session factory.

The engine is built lazily from ``settings.database_url``. When that URL is
empty (CI, local tests, demos with no RDS), :func:`get_sessionmaker` returns
``None`` and the caller falls back to a no-op repository — so the service runs
identically with or without a database.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine() -> Optional[Engine]:
    """Return a process-wide engine, or ``None`` when no database is configured."""
    url = settings.database_url
    if not url:
        logger.info("No FDP_DATABASE_URL set; prediction logging is disabled.")
        return None
    engine = create_engine(
        url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_pre_ping=True,  # transparently recycle connections dropped by RDS.
        future=True,
    )
    logger.info("Database engine created for %s", _sanitize(url))
    return engine


@lru_cache(maxsize=1)
def get_sessionmaker() -> Optional[sessionmaker]:
    engine = get_engine()
    if engine is None:
        return None
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False, future=True)


def _sanitize(url: str) -> str:
    """Drop any password component before logging a connection URL."""
    if "@" not in url:
        return url
    creds, host = url.rsplit("@", 1)
    scheme_user = creds.split(":", 2)
    if len(scheme_user) >= 3:
        scheme_user[2] = "***"
    return ":".join(scheme_user) + "@" + host

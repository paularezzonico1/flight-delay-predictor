"""ORM models for persisted data.

The :class:`PredictionLog` table records every prediction request/response so
traffic can be audited, replayed, and analysed. The composite index on
``(route, carrier)`` that accelerates route/carrier lookups is intentionally
*not* declared here — it is applied by ``migrations/002_add_route_carrier_index.sql``
so its impact can be measured with EXPLAIN ANALYZE before and after.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PredictionLog(Base):
    """One row per /predict call: the input features, the model output, and
    serving metadata (model version, latency, cache hit, timestamp)."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(32))

    # --- Request features ---
    carrier: Mapped[str] = mapped_column(String(8), nullable=False)
    origin: Mapped[str] = mapped_column(String(8), nullable=False)
    destination: Mapped[str] = mapped_column(String(8), nullable=False)
    # Denormalised "ORIGIN-DEST" so the hot lookup filters one column, not two.
    route: Mapped[str] = mapped_column(String(16), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    dep_hour: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Response ---
    delay_probability: Mapped[float] = mapped_column(Float, nullable=False)
    will_be_delayed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # --- Serving metadata ---
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<PredictionLog id={self.id} route={self.route} carrier={self.carrier} "
            f"p={self.delay_probability:.3f}>"
        )

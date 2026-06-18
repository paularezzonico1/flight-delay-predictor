"""Bulk-seed the predictions table with synthetic rows.

Used before benchmarking the route/carrier lookup so EXPLAIN ANALYZE runs against
a realistically sized table. Connects via --url or FDP_DATABASE_URL and inserts
rows in batches.

Usage:
    python -m scripts.seed_predictions --rows 200000 \
        --url postgresql+psycopg://fdp:fdp@localhost:5432/fdp
"""
from __future__ import annotations

import argparse
import logging
import os
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine

from app.db.models import Base, PredictionLog
from constants import AIRLINES, AIRPORTS
from sqlalchemy.orm import Session

logger = logging.getLogger("seed")

_AIRLINES = list(AIRLINES)
_AIRPORTS = list(AIRPORTS)


def _random_rows(n: int, rng: random.Random) -> list[dict]:
    base_time = datetime.now(timezone.utc) - timedelta(days=7)
    rows: list[dict] = []
    for i in range(n):
        origin, dest = rng.sample(_AIRPORTS, 2)
        carrier = rng.choice(_AIRLINES)
        dep_hour = rng.randint(0, 23)
        proba = round(rng.random(), 4)
        rows.append(
            dict(
                created_at=base_time + timedelta(seconds=i),
                request_id=f"seed{i:08d}",
                carrier=carrier,
                origin=origin,
                destination=dest,
                route=f"{origin}-{dest}",
                month=rng.randint(1, 12),
                day_of_week=rng.randint(1, 7),
                dep_hour=dep_hour,
                delay_probability=proba,
                will_be_delayed=proba >= 0.5,
                risk_level="high" if proba >= 0.5 else "low",
                model_version="seed",
                latency_ms=round(rng.uniform(0.5, 3.0), 3),
                cache_hit=False,
            )
        )
    return rows


def seed(url: str, rows: int, batch: int = 10_000, seed_val: int = 42) -> None:
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)  # ensure table exists (idempotent)
    rng = random.Random(seed_val)
    inserted = 0
    with Session(engine) as session:
        while inserted < rows:
            n = min(batch, rows - inserted)
            session.execute(PredictionLog.__table__.insert(), _random_rows(n, rng))
            session.commit()
            inserted += n
            logger.info("Inserted %d / %d", inserted, rows)
    logger.info("Done. Seeded %d rows into predictions.", inserted)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=200_000)
    ap.add_argument("--url", default=os.environ.get("FDP_DATABASE_URL", ""))
    args = ap.parse_args()
    if not args.url:
        raise SystemExit("Set --url or FDP_DATABASE_URL")
    seed(args.url, args.rows)


if __name__ == "__main__":
    main()

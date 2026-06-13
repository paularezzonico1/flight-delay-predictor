"""
Flight delay dataset loader / generator.

Primary path: load a real US DOT / BTS "On-Time Performance" CSV (the canonical
public flight-delay source) from data/flights.csv.

Fallback path: when no real CSV is present (CI, demos, first run), synthesize a
dataset whose delay distribution mirrors documented BTS patterns — carrier
baselines, congested hubs, evening/seasonal peaks. Synthetic data is for
development convenience; train on the BTS CSV for real performance numbers.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from constants import AIRLINES, AIRPORTS, TARGET_THRESHOLD_MIN
from utils import normalize

logger = logging.getLogger(__name__)


def _hour_effect(hour: int) -> float:
    """Delays build through the day; early morning is cleanest."""
    return float(np.clip((hour - 5) * 0.012, 0.0, 0.18))


def _month_effect(month: int) -> float:
    """Summer convective season (Jun-Aug) and December winter ops are worst."""
    summer = 0.06 if month in (6, 7, 8) else 0.0
    winter = 0.05 if month == 12 else 0.0
    return summer + winter


def _dow_effect(dow: int) -> float:
    """Thursday/Friday/Sunday peaks (1=Mon ... 7=Sun)."""
    return {4: 0.02, 5: 0.03, 7: 0.025}.get(dow, 0.0)


def generate_synthetic(n: int = 200_000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    airlines = rng.choice(list(AIRLINES), size=n, p=normalize(AIRLINES.values()))
    origins = rng.choice(list(AIRPORTS), size=n)
    dests = rng.choice(list(AIRPORTS), size=n)
    # No flight from an airport to itself.
    same = origins == dests
    dests[same] = rng.choice(list(AIRPORTS), size=int(same.sum()))

    months = rng.integers(1, 13, size=n)
    days_of_week = rng.integers(1, 8, size=n)
    dep_hours = rng.integers(0, 24, size=n)

    base = 0.10  # baseline delay rate
    prob = (
        base
        + np.array([AIRLINES[a] for a in airlines])
        + np.array([AIRPORTS[o] for o in origins])
        + np.array([AIRPORTS[d] for d in dests]) * 0.4
        + np.array([_hour_effect(h) for h in dep_hours])
        + np.array([_month_effect(m) for m in months])
        + np.array([_dow_effect(d) for d in days_of_week])
    )

    prob = np.clip(prob + rng.normal(0, 0.04, size=n), 0.01, 0.95)
    delayed = (rng.random(n) < prob).astype(int)

    df = pd.DataFrame(
        {
            "airline": airlines,
            "origin": origins,
            "destination": dests,
            "month": months,
            "day_of_week": days_of_week,
            "dep_hour": dep_hours,
            "delayed": delayed,
        }
    )
    logger.info("Generated %d synthetic flights, delay rate %.3f", n, df.delayed.mean())
    return df


def load_real(csv_path: str) -> pd.DataFrame:
    """Map a BTS On-Time Performance CSV into our schema."""
    df = pd.read_csv(csv_path)
    cols = {c.upper(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        raise KeyError(f"None of {names} found in {list(df.columns)}")

    out = pd.DataFrame(
        {
            "airline": df[pick("OP_UNIQUE_CARRIER", "OP_CARRIER", "CARRIER")],
            "origin": df[pick("ORIGIN")],
            "destination": df[pick("DEST", "DESTINATION")],
            "month": df[pick("MONTH")].astype(int),
            "day_of_week": df[pick("DAY_OF_WEEK")].astype(int),
            "dep_hour": (df[pick("CRS_DEP_TIME", "DEP_TIME")].fillna(0).astype(int) // 100),
        }
    )

    dep_delay = df[pick("DEP_DELAY", "DEP_DELAY_NEW")].fillna(0)
    out["delayed"] = (dep_delay > TARGET_THRESHOLD_MIN).astype(int)
    out = out.dropna()
    logger.info("Loaded %d real flights from %s", len(out), csv_path)
    return out


def load_dataset(csv_path: str = "data/flights.csv", n_synthetic: int = 200_000) -> pd.DataFrame:
    if os.path.exists(csv_path):
        logger.info("Using real dataset at %s", csv_path)
        df = load_real(csv_path)
    else:
        logger.warning("No dataset at %s — falling back to synthetic data.", csv_path)
        df = generate_synthetic(n=n_synthetic)
    df = df.drop_duplicates().reset_index(drop=True)
    _validate_schema(df)
    log_summary(df)
    return df


def _validate_schema(df: pd.DataFrame) -> None:
    """Fail fast if a loaded dataset is missing columns or out of range."""
    required = {"airline", "origin", "destination", "month", "day_of_week", "dep_hour", "delayed"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Dataset missing columns: {sorted(missing)}")
    if not df.month.between(1, 12).all():
        raise ValueError("month out of range 1-12")
    if not df.day_of_week.between(1, 7).all():
        raise ValueError("day_of_week out of range 1-7")
    if not df.dep_hour.between(0, 23).all():
        raise ValueError("dep_hour out of range 0-23")

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

    # Combine effects on the logit scale: this yields a realistic (~20%) delay
    # rate with enough separability for the model to learn, while a modest noise
    # term keeps the problem from being perfectly predictable.
    airline_e = np.array([AIRLINES[a] for a in airlines])
    origin_e = np.array([AIRPORTS[o] for o in origins])
    dest_e = np.array([AIRPORTS[d] for d in dests])
    hour_e = np.array([_hour_effect(h) for h in dep_hours])
    month_e = np.array([_month_effect(m) for m in months])
    dow_e = np.array([_dow_effect(d) for d in days_of_week])

    z = (
        -2.4
        + 20.0 * (airline_e - 0.18)
        + 16.0 * (origin_e - 0.045)
        + 7.0 * (dest_e - 0.045)
        + 14.0 * (hour_e - 0.09)
        + 18.0 * month_e
        + 14.0 * dow_e
        + rng.normal(0, 0.2, size=n)
    )
    prob = 1.0 / (1.0 + np.exp(-z))
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


def _parse_dates(s: pd.Series) -> pd.Series:
    """Parse BTS flight dates, trying common explicit formats before inferring."""
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return pd.to_datetime(s, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.to_datetime(s)


def load_real(csv_path: str) -> pd.DataFrame:
    """Map a BTS On-Time Performance CSV into our schema.

    Handles the two common public layouts:
      * raw delay minutes (DEP_DELAY) with explicit MONTH / DAY_OF_WEEK, and
      * a pre-computed DEP_DEL15 indicator with only FL_DATE (month and
        day_of_week are then derived from the date).
    Cancelled / unscheduled rows (no departure, hence no label) are dropped.
    """
    df = pd.read_csv(csv_path)
    cols = {c.upper(): c for c in df.columns}

    def pick(*names, required=True):
        for n in names:
            if n in cols:
                return cols[n]
        if required:
            raise KeyError(f"None of {names} found in {list(df.columns)}")
        return None

    out = pd.DataFrame(
        {
            "airline": df[pick("OP_UNIQUE_CARRIER", "OP_CARRIER", "CARRIER")],
            "origin": df[pick("ORIGIN")],
            "destination": df[pick("DEST", "DESTINATION")],
            "dep_hour": (df[pick("CRS_DEP_TIME", "DEP_TIME")].fillna(0).astype(int) // 100),
        }
    )

    # Month / day-of-week: use explicit columns when present, else derive them
    # from the flight date (pandas dayofweek is 0=Mon, we want 1=Mon..7=Sun).
    month_col, dow_col = pick("MONTH", required=False), pick("DAY_OF_WEEK", required=False)
    if month_col and dow_col:
        out["month"] = df[month_col].astype(int)
        out["day_of_week"] = df[dow_col].astype(int)
    else:
        dates = _parse_dates(df[pick("FL_DATE", "FLIGHTDATE", "FL_DATE_TIME")])
        out["month"] = dates.dt.month.astype(int)
        out["day_of_week"] = (dates.dt.dayofweek + 1).astype(int)

    # Label: prefer the pre-computed >15-min indicator, else derive from minutes.
    del15_col = pick("DEP_DEL15", required=False)
    if del15_col is not None:
        out["delayed"] = df[del15_col]
    else:
        out["delayed"] = (df[pick("DEP_DELAY", "DEP_DELAY_NEW")] > TARGET_THRESHOLD_MIN).astype(float)

    cancelled_col = pick("CANCELLED", required=False)
    if cancelled_col is not None:
        out = out[df[cancelled_col].fillna(0) == 0]
    out = out.dropna(subset=["delayed"])
    out["delayed"] = out["delayed"].astype(int)
    out = out.dropna().reset_index(drop=True)
    logger.info("Loaded %d real flights from %s", len(out), csv_path)
    return out


def load_dataset(csv_path: str = "data/flights.csv", n_synthetic: int = 200_000) -> pd.DataFrame:
    if os.path.exists(csv_path):
        logger.info("Using real dataset at %s", csv_path)
        df = load_real(csv_path)
    else:
        logger.warning("No dataset at %s — falling back to synthetic data.", csv_path)
        df = generate_synthetic(n=n_synthetic)
    # Note: do NOT drop duplicates — distinct flights legitimately share the same
    # carrier/route/schedule features, and their frequency carries the signal.
    df = df.reset_index(drop=True)
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


def dep_hour_bucket(hour: int) -> str:
    """Coarse daypart label for exploratory summaries."""
    if hour < 6:
        return "night"
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


def log_summary(df: pd.DataFrame) -> None:
    """Log headline data-quality / distribution stats after loading."""
    logger.info("Rows=%d delay_rate=%.3f", len(df), df.delayed.mean())
    by_airline = df.groupby("airline").delayed.mean().sort_values(ascending=False)
    logger.info("Worst airlines: %s", by_airline.head(3).round(3).to_dict())
    buckets = df.dep_hour.map(dep_hour_bucket)
    logger.info("Delay rate by daypart: %s", df.delayed.groupby(buckets).mean().round(3).to_dict())


def top_delay_routes(df: pd.DataFrame, n: int = 5) -> pd.Series:
    """Return the n most delay-prone origin-destination routes."""
    routes = df.assign(route=df.origin + "-" + df.destination)
    return routes.groupby("route").delayed.mean().sort_values(ascending=False).head(n)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    frame = load_dataset()
    print(frame.head())
    print(f"\nRows: {len(frame):,}  Delay rate: {frame.delayed.mean():.3f}")
    print("\nTop delay-prone routes:")
    print(top_delay_routes(frame))

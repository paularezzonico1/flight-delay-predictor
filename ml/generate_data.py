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

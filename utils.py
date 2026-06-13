"""Small shared helpers used across the data and serving layers."""
from __future__ import annotations

from typing import Iterable

import numpy as np


def normalize(values: Iterable[float]) -> np.ndarray:
    """Return a probability vector that sums to 1."""
    arr = np.asarray(list(values), dtype=float)
    return arr / arr.sum()


def risk_level(p: float) -> str:
    """Bucket a delay probability into low / moderate / high."""
    from constants import RISK_LOW_MAX, RISK_MODERATE_MAX

    if p < RISK_LOW_MAX:
        return "low"
    if p < RISK_MODERATE_MAX:
        return "moderate"
    return "high"

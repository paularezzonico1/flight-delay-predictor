"""Small shared helpers used across the data and serving layers."""
from __future__ import annotations

from typing import Iterable

import numpy as np


def normalize(values: Iterable[float]) -> np.ndarray:
    """Return a probability vector that sums to 1."""
    arr = np.asarray(list(values), dtype=float)
    return arr / arr.sum()

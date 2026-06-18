"""Errors shared across the model/serving layer."""
from __future__ import annotations


class ModelNotLoadedError(RuntimeError):
    """Raised when a prediction is attempted before any strategy is available."""

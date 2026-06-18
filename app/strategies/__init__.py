"""Prediction strategies.

The Strategy pattern puts the model behind a uniform interface
(:class:`PredictionStrategy`) so the *active* model can be swapped without
touching any calling code. The production strategy wraps the trained XGBoost
pipeline; a heuristic fallback keeps the service answering (degraded) when the
model artifact is missing or fails to load.
"""
from app.strategies.base import PredictionStrategy, StrategyResult

__all__ = ["PredictionStrategy", "StrategyResult"]

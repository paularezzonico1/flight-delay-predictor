"""
Train an XGBoost classifier to predict whether a flight's departure will be
delayed by more than 15 minutes.

Outputs:
  models/model.pkl     -- a self-contained sklearn Pipeline (preprocess + XGB)
  models/metrics.json  -- evaluation metrics + metadata served by GET /stats

Run:  python -m ml.train   (from the project root)
Set TUNE=1 to run a randomized hyperparameter search before fitting.
"""
from __future__ import annotations

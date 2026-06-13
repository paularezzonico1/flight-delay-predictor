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

import json
import logging
import os
import time
from datetime import datetime, timezone

import joblib
from sklearn.compose import ColumnTransformer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from constants import CATEGORICAL, FEATURES, NUMERIC, TARGET
from ml.generate_data import load_dataset

logger = logging.getLogger(__name__)

MODEL_DIR = os.environ.get("MODEL_DIR", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")

DEFAULT_PARAMS = dict(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.9,
    colsample_bytree=0.9,
    eval_metric="logloss",
    tree_method="hist",
    n_jobs=-1,
    random_state=42,
)


def build_pipeline(scale_pos_weight: float) -> Pipeline:
    preprocess = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ]
    )
    clf = XGBClassifier(scale_pos_weight=scale_pos_weight, **DEFAULT_PARAMS)
    return Pipeline([("preprocess", preprocess), ("clf", clf)])


def tune(X_train, y_train) -> dict:
    """Optional RandomizedSearchCV over key XGBoost params (set TUNE=1)."""
    from sklearn.model_selection import RandomizedSearchCV

    search_space = {
        "clf__max_depth": [4, 6, 8],
        "clf__n_estimators": [200, 300, 400],
        "clf__learning_rate": [0.05, 0.1, 0.2],
        "clf__subsample": [0.8, 0.9, 1.0],
    }
    base = build_pipeline(scale_pos_weight=1.0)
    search = RandomizedSearchCV(
        base, search_space, n_iter=8, scoring="roc_auc", cv=3, n_jobs=-1, random_state=42
    )
    search.fit(X_train, y_train)
    logger.info("Best params: %s (roc_auc=%.4f)", search.best_params_, search.best_score_)
    return {k.replace("clf__", ""): v for k, v in search.best_params_.items()}


def evaluate(pipe: Pipeline, X_test, y_test) -> dict:
    """Compute offline metrics plus warm single-prediction latency."""
    proba = pipe.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)
    metrics = {}
    metrics["accuracy"] = round(accuracy_score(y_test, preds), 4)
    metrics["precision"] = round(precision_score(y_test, preds, zero_division=0), 4)
    metrics["recall"] = round(recall_score(y_test, preds, zero_division=0), 4)

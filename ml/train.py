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
    metrics["f1"] = round(f1_score(y_test, preds, zero_division=0), 4)
    metrics["roc_auc"] = round(roc_auc_score(y_test, proba), 4)
    metrics["pr_auc"] = round(average_precision_score(y_test, proba), 4)
    metrics["brier_score"] = round(brier_score_loss(y_test, proba), 4)

    sample = X_test.iloc[:1]
    pipe.predict_proba(sample)  # warm-up
    t0 = time.perf_counter()
    for _ in range(100):
        pipe.predict_proba(sample)
    metrics["single_predict_latency_ms"] = round((time.perf_counter() - t0) / 100 * 1000, 3)
    return metrics


def feature_importance(pipe: Pipeline, top_n: int = 15) -> list:
    """Return the most influential one-hot features by XGBoost gain."""
    ohe = pipe.named_steps["preprocess"].named_transformers_["cat"]
    names = ohe.get_feature_names_out(CATEGORICAL).tolist() + NUMERIC
    importances = pipe.named_steps["clf"].feature_importances_
    ranked = sorted(zip(names, importances), key=lambda t: t[1], reverse=True)
    return [{"feature": n, "importance": round(float(i), 5)} for n, i in ranked[:top_n]]


def save_artifacts(pipe: Pipeline, metadata: dict) -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(pipe, MODEL_PATH)
    with open(METRICS_PATH, "w") as fh:
        json.dump(metadata, fh, indent=2)
    size_kb = os.path.getsize(MODEL_PATH) / 1024
    logger.info("Saved model -> %s (%.1f KB)", MODEL_PATH, size_kb)
    logger.info("Saved metrics -> %s", METRICS_PATH)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    df = load_dataset()
    X, y = df[FEATURES], df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    pos = int(y_train.sum())
    neg = int(len(y_train) - pos)
    scale_pos_weight = neg / max(pos, 1)
    logger.info("Train rows: %d (pos=%d neg=%d, spw=%.2f)", len(X_train), pos, neg, scale_pos_weight)

    pipe = build_pipeline(scale_pos_weight)
    if os.environ.get("TUNE") == "1":
        pipe.named_steps["clf"].set_params(**tune(X_train, y_train))
    logger.info("Fitting XGBoost pipeline...")
    pipe.fit(X_train, y_train)

    metrics = evaluate(pipe, X_test, y_test)
    logger.info("Evaluation: %s", json.dumps(metrics))
    metadata = {
        "model_type": "XGBClassifier",
        "target": "departure delay > 15 min",
        "features": FEATURES,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "train_delay_rate": round(float(y_train.mean()), 4),
        "known_airlines": sorted(df.airline.unique().tolist()),
        "known_airports": sorted(set(df.origin.unique()) | set(df.destination.unique())),
        "metrics": metrics,
        "top_features": feature_importance(pipe),
    }
    save_artifacts(pipe, metadata)

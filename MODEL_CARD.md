# Model Card — Flight Delay Predictor

## Overview
- **Task:** binary classification — will a flight's departure be delayed > 15 min?
- **Algorithm:** XGBoost gradient-boosted trees inside a scikit-learn `Pipeline`
  (one-hot encoding for categorical features, numeric passthrough).

## Intended use
Estimate departure-delay risk for a single US domestic flight given carrier,
route, and schedule. For planning/triage signal — not a guarantee.

## Training data
US DOT / BTS "On-Time Performance" data, **January 2023** (`data/flights.csv`):
528,542 scheduled US domestic flights after dropping cancelled rows; 21.1%
departure-delay rate. Label: the BTS `DEP_DEL15` indicator (departure delayed
≥ 15 min); the loader also derives the label from `DEP_DELAY` minutes when only
that column is present. A synthetic fallback mirrors documented BTS patterns so
the project runs without a CSV.

## Features
`airline`, `origin`, `destination` (categorical IATA codes); `month`,
`day_of_week` (1=Mon), `dep_hour` (0–23). In the January-only snapshot `month`
is constant and therefore uninformative.

## Evaluation
Stratified 80/20 split on the January 2023 data. Class imbalance handled via
`scale_pos_weight` (≈3.7), trading precision for recall. Metrics are written to
`models/metrics.json` and served at `GET /stats`:

| ROC-AUC | PR-AUC | Accuracy | Precision | Recall | F1 | Brier |
|---------|--------|----------|-----------|--------|-----|-------|
| 0.686 | 0.364 | 0.619 | 0.310 | 0.659 | 0.422 | 0.223 |

## Limitations
- Does not model weather, aircraft tail history, or upstream/network delays —
  the dominant real-world delay drivers — which caps achievable accuracy.
- Trained on a single month (January 2023); seasonality is not represented.
- Unknown carriers/airports are accepted but flagged in the response `warnings`.

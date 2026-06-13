# Model Card — Flight Delay Predictor

## Overview
- **Task:** binary classification — will a flight's departure be delayed > 15 min?
- **Algorithm:** XGBoost gradient-boosted trees inside a scikit-learn `Pipeline`
  (one-hot encoding for categorical features, numeric passthrough).

## Intended use
Estimate departure-delay risk for a single US domestic flight given carrier,
route, and schedule. For planning/triage signal — not a guarantee.

## Training data
US DOT / BTS "On-Time Performance" data (`data/flights.csv`) when provided;
otherwise a synthetic dataset that mirrors documented BTS delay patterns so the
project runs out of the box. Label: `DEP_DELAY > 15` minutes.

## Features
`airline`, `origin`, `destination` (categorical IATA codes); `month`,
`day_of_week` (1=Mon), `dep_hour` (0–23).

## Evaluation
Stratified 80/20 split. Metrics — accuracy, precision, recall, F1, ROC-AUC,
PR-AUC, Brier score — are written to `models/metrics.json` and served at
`GET /stats`. Class imbalance handled via `scale_pos_weight`.

## Limitations
- Does not model weather, aircraft tail history, or upstream/network delays.
- Synthetic fallback data is illustrative; real metrics require the BTS CSV.
- Unknown carriers/airports are accepted but flagged in the response `warnings`.

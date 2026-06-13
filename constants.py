"""Shared constants for the Flight Delay Predictor.

Centralizes the feature schema, delay threshold, and reference lists of carriers
and airports so the data, model, and API layers agree on one definition.
"""
from __future__ import annotations

# "delayed" == scheduled departure delayed by more than this many minutes.
TARGET_THRESHOLD_MIN = 15

# Feature schema shared by training and inference.
CATEGORICAL = ["airline", "origin", "destination"]
NUMERIC = ["month", "day_of_week", "dep_hour"]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "delayed"

# Top US carriers (IATA) with rough relative delay propensities.
AIRLINES = {
    "AA": 0.20, "DL": 0.14, "UA": 0.19, "WN": 0.17, "B6": 0.23,
    "AS": 0.13, "NK": 0.24, "F9": 0.25, "G4": 0.22, "HA": 0.12,
}

# Major airports; hubs carry a congestion premium.
AIRPORTS = {
    "ATL": 0.04, "ORD": 0.07, "DFW": 0.05, "DEN": 0.05, "LAX": 0.04,
    "JFK": 0.06, "SFO": 0.07, "LAS": 0.02, "SEA": 0.03, "EWR": 0.08,
    "MIA": 0.04, "BOS": 0.05, "PHX": 0.01, "IAH": 0.04, "MCO": 0.02,
}

# Probability cutoffs for the reported risk band.
RISK_LOW_MAX = 0.20
RISK_MODERATE_MAX = 0.50

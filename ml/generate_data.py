"""
Flight delay dataset loader / generator.

Primary path: load a real US DOT / BTS "On-Time Performance" CSV (the canonical
public flight-delay source) from data/flights.csv.

Fallback path: when no real CSV is present (CI, demos, first run), synthesize a
dataset whose delay distribution mirrors documented BTS patterns — carrier
baselines, congested hubs, evening/seasonal peaks. Synthetic data is for
development convenience; train on the BTS CSV for real performance numbers.
"""
from __future__ import annotations

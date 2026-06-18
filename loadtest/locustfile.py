"""Locust load test for the Flight Delay Predictor API.

Drives /predict with a deliberate mix of *repeated* and *random* requests:

  * ~70% of traffic reuses a small pool of (route, carrier, dep_hour) tuples so
    the Redis cache gets meaningful hits (this is what makes the cache-hit-rate
    measurement real).
  * ~30% is random across carriers/airports/hours to exercise cache misses and
    model inference.

A burst LoadTestShape ramps users up, spikes, then ramps down so the ASG's
request/CPU target-tracking policies have a reason to scale out.

Run (against a local stack or the deployed ALB):
    locust -f loadtest/locustfile.py --host http://localhost:8000 \
        --headless -u 200 -r 20 -t 3m --csv loadtest/report
"""
from __future__ import annotations

import random

from locust import HttpUser, LoadTestShape, between, task

CARRIERS = ["AA", "DL", "UA", "WN", "B6", "AS", "NK", "F9", "G4", "HA"]
AIRPORTS = ["ATL", "ORD", "DFW", "DEN", "LAX", "JFK", "SFO", "LAS", "SEA", "EWR"]

# Small hot set of repeated lookups -> cache hits.
HOT_REQUESTS = [
    {"airline": "B6", "origin": "JFK", "destination": "SFO", "month": 7, "day_of_week": 5, "dep_hour": 18},
    {"airline": "AA", "origin": "DFW", "destination": "LAX", "month": 7, "day_of_week": 5, "dep_hour": 8},
    {"airline": "UA", "origin": "ORD", "destination": "EWR", "month": 12, "day_of_week": 4, "dep_hour": 17},
    {"airline": "DL", "origin": "ATL", "destination": "SEA", "month": 6, "day_of_week": 7, "dep_hour": 21},
    {"airline": "WN", "origin": "LAS", "destination": "DEN", "month": 3, "day_of_week": 2, "dep_hour": 6},
]


def _random_request() -> dict:
    origin, dest = random.sample(AIRPORTS, 2)
    return {
        "airline": random.choice(CARRIERS),
        "origin": origin,
        "destination": dest,
        "month": random.randint(1, 12),
        "day_of_week": random.randint(1, 7),
        "dep_hour": random.randint(0, 23),
    }


class FlightUser(HttpUser):
    wait_time = between(0.05, 0.3)

    @task(7)
    def predict_hot(self):
        self.client.post("/predict", json=random.choice(HOT_REQUESTS), name="/predict [hot]")

    @task(3)
    def predict_random(self):
        self.client.post("/predict", json=_random_request(), name="/predict [random]")

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")


class BurstShape(LoadTestShape):
    """Ramp -> burst -> sustain -> ramp down, to trigger ASG scale-out."""

    stages = [
        {"duration": 30, "users": 25, "spawn_rate": 10},
        {"duration": 90, "users": 200, "spawn_rate": 40},   # burst
        {"duration": 150, "users": 200, "spawn_rate": 40},  # sustain peak
        {"duration": 180, "users": 50, "spawn_rate": 20},   # ramp down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None

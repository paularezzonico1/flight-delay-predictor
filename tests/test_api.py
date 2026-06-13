"""API tests. Trains a tiny model into a temp dir so tests are self-contained."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def _trained_model(tmp_path_factory):
    """Train a small model once and point the app config at it."""
    model_dir = tmp_path_factory.mktemp("models")
    os.environ["MODEL_DIR"] = str(model_dir)
    os.environ["FDP_MODEL_PATH"] = os.path.join(model_dir, "model.pkl")
    os.environ["FDP_METRICS_PATH"] = os.path.join(model_dir, "metrics.json")

    import ml.train as train
    train.MODEL_DIR = str(model_dir)
    train.MODEL_PATH = os.environ["FDP_MODEL_PATH"]
    train.METRICS_PATH = os.environ["FDP_METRICS_PATH"]

    import ml.generate_data as gd
    orig = gd.load_dataset
    gd.load_dataset = lambda *a, **k: gd.generate_synthetic(n=8000)
    train.load_dataset = gd.load_dataset
    try:
        train.main()
    finally:
        gd.load_dataset = orig


@pytest.fixture(scope="session")
def client(_trained_model):
    from app.config import settings
    settings.model_path = os.environ["FDP_MODEL_PATH"]
    settings.metrics_path = os.environ["FDP_METRICS_PATH"]
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["model_loaded"] is True


def test_stats(client):
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["model_type"] == "XGBClassifier"
    assert "roc_auc" in body["metrics"]
    assert len(body["known_airlines"]) > 0


def test_predict_ok(client):
    r = client.post("/predict", json={
        "airline": "B6", "origin": "JFK", "destination": "SFO",
        "month": 7, "day_of_week": 5, "dep_hour": 18,
    })
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["delay_probability"] <= 1.0
    assert body["risk_level"] in {"low", "moderate", "high"}
    assert isinstance(body["will_be_delayed"], bool)


def test_predict_lowercase_is_normalized(client):
    r = client.post("/predict", json={
        "airline": "aa", "origin": "atl", "destination": "lax",
        "month": 1, "day_of_week": 2, "dep_hour": 6,
    })
    assert r.status_code == 200


def test_predict_same_airport_rejected(client):
    r = client.post("/predict", json={
        "airline": "AA", "origin": "JFK", "destination": "JFK",
        "month": 7, "day_of_week": 5, "dep_hour": 18,
    })
    assert r.status_code == 422


def test_predict_out_of_range_rejected(client):
    r = client.post("/predict", json={
        "airline": "AA", "origin": "JFK", "destination": "LAX",
        "month": 13, "day_of_week": 5, "dep_hour": 18,
    })
    assert r.status_code == 422


def test_predict_unknown_airline_warns(client):
    r = client.post("/predict", json={
        "airline": "ZZ", "origin": "JFK", "destination": "LAX",
        "month": 7, "day_of_week": 5, "dep_hour": 18,
    })
    assert r.status_code == 200
    assert any("Unknown airline" in w for w in r.json()["warnings"])

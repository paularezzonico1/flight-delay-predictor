# Flight Delay Predictor

Predicts the probability that a US domestic flight departs more than 15 minutes
late, served as a low-latency REST API.

<!-- Detailed architecture, metrics, API reference, and run instructions are
     filled in below. -->

## Architecture

```
                         Internet
                            │  HTTP :80
                            ▼
              ┌──────────────────────────────┐
              │  Application Load Balancer    │  health checks → /health
              │  (target-tracking listener)   │
              └──────────────┬───────────────┘
                             │  :8000
              ┌──────────────┴───────────────┐
              │      Auto Scaling Group       │  scales on CPU 50% +
              │   (2–6 EC2, rolling updates)  │  1000 req/target
              │                               │
              │   ┌───────────────────────┐   │
              │   │  Docker container      │   │
              │   │  uvicorn + FastAPI     │   │
              │   │   /predict /health     │   │
              │   │   /stats   /docs       │   │
              │   │        │               │   │
              │   │   XGBoost Pipeline     │   │  loaded once at startup
              │   │   (model.pkl)          │   │  (warm, in-process)
              │   └───────────────────────┘   │
              └──────────────┬───────────────┘
                             │ logs/metrics
                             ▼
                  CloudWatch Logs + Alarms + Dashboard

Build/train flow:  BTS CSV (or synthetic) → ml/train.py → model.pkl + metrics.json
                   baked into the Docker image at build time.
```

## Components
- **`ml/`** — dataset loader (`generate_data.py`) and training pipeline
  (`train.py`) producing `models/model.pkl` + `models/metrics.json`.
- **`app/`** — FastAPI service: `config.py` (settings + JSON logging),
  `schemas.py` (validation), `model.py` (inference singleton), `main.py` (routes,
  middleware, error handling).
- **`deploy/`** — `cloudformation.yaml` (ALB + ASG), `monitoring.yaml`
  (CloudWatch), `deploy.sh` (build → ECR → CloudFormation).

## API

Interactive docs at `/docs` (Swagger) and `/redoc`.

### `POST /predict`
Request:
```json
{ "airline": "B6", "origin": "JFK", "destination": "SFO",
  "month": 7, "day_of_week": 5, "dep_hour": 18 }
```
Response:
```json
{ "delay_probability": 0.42, "will_be_delayed": false, "threshold": 0.5,
  "risk_level": "moderate", "model_version": "2026-...", "latency_ms": 1.8,
  "warnings": [] }
```
Field rules: `month` 1–12, `day_of_week` 1–7 (Mon–Sun), `dep_hour` 0–23;
airline/origin/destination are IATA codes (case-insensitive); origin ≠ destination.
Invalid input → `422` with field-level detail. Unknown codes are accepted with a
`warnings` entry. Model not yet loaded → `503`.

### `GET /health`
Returns `200` with `{"status":"ok","model_loaded":true}` when ready, else `503`
(`degraded`). Used as the ALB and container health check.

### `GET /stats`
Model metadata and offline metrics (accuracy, precision, recall, F1, ROC-AUC,
PR-AUC, Brier score, single-prediction latency), plus known airlines/airports.

## Performance

- **Latency:** the XGBoost pipeline is loaded once at process start and served
  warm and in-process. Single-prediction latency is ~1–5 ms locally
  (`metrics.single_predict_latency_ms` in `GET /stats`), comfortably inside the
  sub-100 ms response-time target end-to-end. Each response carries an
  `x-process-time-ms` header for observability.
- **Throughput / scaling:** two uvicorn workers per container; the ASG adds
  instances on average CPU > 50% or > 1000 requests/target.
- **Model quality:** reported live by `GET /stats`. On the bundled synthetic
  dataset (≈23% delay rate) the model reaches roughly ROC-AUC ~0.80, accuracy
  ~0.72, F1 ~0.55 (illustrative). Train on the real BTS CSV
  (`data/flights.csv`) for production-representative numbers, then read the exact
  metrics from `/stats` or `models/metrics.json`.

> Note: the bundled dataset is synthetic so the project runs out of the box.
> The numbers above are not real BTS performance — drop a BTS CSV in `data/` and
> retrain to get genuine metrics.

## Run locally

### With Python
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m ml.train                      # writes models/model.pkl + metrics.json
python -m uvicorn app.main:app --port 8000
curl localhost:8000/health
curl -X POST localhost:8000/predict -H 'content-type: application/json' \
  -d '{"airline":"B6","origin":"JFK","destination":"SFO","month":7,"day_of_week":5,"dep_hour":18}'
```
Or use the Makefile: `make install && make train && make run`.

### With Docker
```bash
docker compose up --build      # trains the model during the image build
curl localhost:8000/health
```

## Run tests
```bash
python -m pytest -q            # trains a small model into a temp dir, hits the API
```

## Deploy to AWS
Builds the image, pushes to ECR, and provisions an ALB + Auto Scaling Group via
CloudFormation:
```bash
export VPC_ID=vpc-0abc123
export SUBNET_IDS=subnet-aaa,subnet-bbb     # 2+ public subnets, different AZs
./deploy/deploy.sh
```
The script prints the public `ApiUrl`. Optionally deploy CloudWatch alarms +
dashboard with `deploy/monitoring.yaml`, passing the `*FullName` stack outputs.

### Configuration
All settings are environment variables prefixed `FDP_` (see `.env.example`):
`FDP_LOG_LEVEL`, `FDP_DECISION_THRESHOLD`, `FDP_MODEL_PATH`, `FDP_METRICS_PATH`.

## Project layout
```
app/      FastAPI service (config, schemas, model, main)
ml/       data loader + XGBoost training pipeline
deploy/   CloudFormation (ALB + ASG), monitoring, deploy.sh
tests/    API tests
constants.py / utils.py   shared schema + helpers
Dockerfile / docker-compose.yml / Makefile
```

## License
MIT — see [LICENSE](LICENSE).

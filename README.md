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
              ┌──────────────┴────────────────────┐
              │        Auto Scaling Group          │  scales on CPU 50% +
              │     (2–6 EC2, rolling updates)     │  1000 req/target
              │                                    │
              │   ┌────────────────────────────┐   │
              │   │  uvicorn + FastAPI          │   │
              │   │   /predict /health /stats   │   │
              │   │        │         ▲          │   │
              │   │   ModelService   │ cache    │   │  Strategy pattern:
              │   │   (Strategy)     ▼          │   │  XGBoost or fallback
              │   │   XGBoost Pipeline          │   │  (loaded once, warm)
              │   └───┬──────────────┬──────────┘   │
              │       │ Repository   │ cache get/set │
              │       │ (SQL)        ▼               │
              │       │        ┌──────────┐          │  Redis container ON the
              │       │        │  Redis   │          │  instance (not ElastiCache)
              │       │        └──────────┘          │
              └───────┼────────────────────────────┘
                      │ log every prediction        │ logs + custom metrics
                      ▼                              ▼
              ┌──────────────┐            CloudWatch Logs + Alarms +
              │ RDS Postgres │            Dashboard (SNS notifications)
              │ (public sub, │
              │  SG-locked)  │  indexed on (route, carrier)
              └──────────────┘

Build/train flow:  BTS CSV (or synthetic) → ml/train.py → model.pkl + metrics.json
                   baked into the Docker image at build time.
Infra:  modular Terraform (remote state in S3 + DynamoDB lock); CI/CD via GitHub
        Actions (test → build → ECR → ASG instance refresh behind health checks).
```

## Components
- **`ml/`** — dataset loader (`generate_data.py`) and training pipeline
  (`train.py`) producing `models/model.pkl` + `models/metrics.json`.
- **`app/`** — FastAPI service:
  - `config.py` (settings + JSON logging), `schemas.py` (validation),
    `main.py` (routes, middleware, error handling).
  - `strategies/` — **Strategy pattern** around the model (XGBoost + fallback).
  - `services/model_service.py` — picks and drives the active strategy.
  - `repositories/` — **Repository pattern** wrapping all RDS access.
  - `db/` — SQLAlchemy engine + `PredictionLog` ORM model.
  - `cache/` — Redis cache (with a null fallback) for repeat lookups.
  - `metrics.py` — CloudWatch custom-metrics emitter.
- **`migrations/`** — raw-SQL schema migrations (table + the `(route, carrier)` index).
- **`infra/terraform/`** — modular Terraform: `bootstrap/` (S3/DynamoDB remote
  state) and `modules/` (`network`, `rds`, `compute`, `monitoring`).
- **`.github/workflows/`** — `ci.yml` (test) and `cd.yml` (build → ECR → ASG rollout).
- **`loadtest/`** — Locust burst load test.

## Design patterns

Two patterns keep the serving code decoupled from its dependencies:

- **Repository pattern** (`app/repositories/`) — wraps *all* RDS access behind
  `AbstractPredictionRepository`. The routes, services, and cache never build SQL
  or touch a SQLAlchemy session; they call `log_prediction()`, `find_recent()`,
  and `count_in_window()`. This decouples the service from the persistence layer:
  the same call sites work against Postgres (`SqlPredictionRepository`) or a no-op
  backend (`NullPredictionRepository`, used when no database is configured, e.g.
  in CI and local tests). Swapping or mocking storage touches one class.

- **Strategy pattern** (`app/strategies/`) — puts the model behind
  `PredictionStrategy` so the *active* model can be swapped without changing any
  caller. `ModelService` loads the production `XGBoostStrategy` and transparently
  falls back to a `FallbackStrategy` (a base-rate heuristic) when the model
  artifact is missing or fails to load — so a cold image degrades instead of
  returning 503s. Adding a new model is a new strategy class; the API code is
  untouched.

## Cost vs. best-practice tradeoffs

This is a portfolio/demo project, so two deliberate choices trade textbook best
practice for materially lower ongoing cost. Both are safe-by-design here but
would be revisited for production:

- **RDS in a public subnet, no NAT Gateway.** Best practice is to put RDS in a
  private subnet and give instances egress via a NAT Gateway — but a NAT Gateway
  costs ~$32/mo plus data processing, which is disproportionate for a demo.
  Instead the database lives in a public subnet with `publicly_accessible = true`
  and is locked down at the **security-group** layer: the RDS SG accepts `:5432`
  *only* from the app-instance SG, so there is no network path from the internet
  to the database port. The network ACL still allows the subnet to route, but the
  SG is the actual control. See `infra/terraform/modules/network/main.tf`.
  *Production:* private subnets + NAT (or VPC endpoints) and `publicly_accessible = false`.

- **Redis as a container on the EC2 instance, not ElastiCache.** Managed
  ElastiCache adds a standing monthly bill; for a demo whose cache is disposable
  (it only memoises repeat `route/carrier/time-of-day` lookups) a `redis:7-alpine`
  container co-located on each instance is enough. It is started by the launch
  template's user data with an LRU eviction policy and bound to the instance.
  *Production:* a managed, replicated ElastiCache cluster for durability and a
  shared cache across instances.

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
  warm and in-process. Each response carries an `x-process-time-ms` header and a
  `latency_ms` field for observability.
- **Throughput / scaling:** two uvicorn workers per container; the ASG adds
  instances on average CPU > 50% or > 1000 requests/target.
- **Caching & persistence:** repeat `route/carrier/time-of-day` requests are
  served from Redis (skipping inference); every request is logged to RDS, whose
  `(route, carrier)` index accelerates the lookup query.

### Measured system performance

The index speedup, real cache hit rate, write throughput, and load-test p99
latency are **measured, not estimated** — each captured from the tool that
produced it (Postgres `EXPLAIN ANALYZE`, `redis-cli INFO stats`, a `COUNT` over
the load-test window, and Locust's own report). See **[METRICS.md](METRICS.md)**
for the numbers and the exact command behind each one.

### Model quality

- Trained on **real US DOT / BTS On-Time Performance data for
  January 2023** — 528,542 flights, 21.1% departure-delay rate. Held-out 20%
  test split (metrics also served live at `GET /stats`):

  | Metric | Value |
  |--------|-------|
  | ROC-AUC | 0.686 |
  | PR-AUC | 0.364 |
  | Accuracy | 0.619 |
  | Precision | 0.310 |
  | Recall | 0.659 |
  | F1 | 0.422 |
  | Brier score | 0.223 |

  These reflect the genuine difficulty of predicting delays from schedule
  features alone (carrier, route, month, day-of-week, departure hour) without
  weather or upstream/network signals. Recall is favoured over precision via
  `scale_pos_weight` so most real delays are flagged. The model recovers
  sensible structure — the worst carriers (Frontier, Spirit, JetBlue) and the
  evening-departure delay peak match published BTS patterns.

> Note: this snapshot is January 2023 only, so the `month` feature is constant
> in training and carries no signal here; add more months of BTS data to use it.
> A synthetic-data fallback (`ml/generate_data.py`) lets the project run end-to-end
> with no CSV present.

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

### With Docker (API only)
```bash
docker compose up --build      # trains the model during the image build
curl localhost:8000/health
```

### Full local stack (API + Postgres + Redis)
Mirrors the AWS wiring — used to capture the numbers in [METRICS.md](METRICS.md):
```bash
docker compose -f docker-compose.measure.yml up -d postgres redis
docker exec -i fdp-pg psql -U fdp -d fdp < migrations/001_create_predictions.sql
docker exec -i fdp-pg psql -U fdp -d fdp < migrations/002_add_route_carrier_index.sql
docker compose -f docker-compose.measure.yml up -d --build api
curl localhost:8000/health
```
Without `FDP_DATABASE_URL` / `FDP_REDIS_URL`, the service runs identically but
skips logging and caching (null backends).

## Run tests
```bash
python -m pytest -q            # offline: null DB/cache backends, no infra needed
```

## Deploy to AWS (Terraform)
Infrastructure is modular Terraform with remote state in S3 + DynamoDB locking.
**Review the plan before applying.**
```bash
# 1. One-time: create the remote-state bucket + lock table
cd infra/terraform/bootstrap
terraform init && terraform apply -var state_bucket_name=<unique-bucket>

# 2. Main stack
cd ..
terraform init \
  -backend-config="bucket=<unique-bucket>" \
  -backend-config="key=flight-delay-predictor/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=fdp-terraform-locks"
export TF_VAR_db_password=...           # never commit secrets
terraform plan -var image_uri=<ecr-image-uri>     # review first
terraform apply -var image_uri=<ecr-image-uri>
terraform output api_url
```
CI/CD (GitHub Actions, `.github/workflows/cd.yml`) builds and pushes the image to
ECR and rolls the ASG via a health-gated instance refresh.

### Configuration
All settings are environment variables prefixed `FDP_` (see `.env.example`):
`FDP_LOG_LEVEL`, `FDP_DECISION_THRESHOLD`, `FDP_MODEL_PATH`, `FDP_METRICS_PATH`,
`FDP_DATABASE_URL`, `FDP_REDIS_URL`, `FDP_CACHE_TTL_SECONDS`,
`FDP_CLOUDWATCH_NAMESPACE`, `FDP_AWS_REGION`.

## Project layout
```
app/                FastAPI service
  strategies/       Strategy pattern (XGBoost + fallback) + ModelService
  repositories/     Repository pattern over RDS
  db/ cache/        SQLAlchemy ORM/engine + Redis cache
  metrics.py        CloudWatch custom metrics
ml/                 data loader + XGBoost training pipeline
migrations/         raw-SQL schema migrations (table + route/carrier index)
infra/terraform/    modular Terraform (bootstrap + network/rds/compute/monitoring)
.github/workflows/  CI (test) and CD (build → ECR → ASG rollout)
loadtest/           Locust burst load test
scripts/            predictions seed script
tests/              API + strategy + cache/repo tests
METRICS.md          measured numbers + the command behind each
constants.py / utils.py   shared schema + helpers
Dockerfile / docker-compose.yml / docker-compose.measure.yml / Makefile
```

## License
MIT — see [LICENSE](LICENSE).

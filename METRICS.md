# Measured numbers

Every number here was captured from the actual output of the tool named beside
it — none are estimated. They were produced against the local measurement stack
(`docker-compose.measure.yml`: Postgres 16 + Redis 7 + the API container) on an
Apple-silicon laptop, except where noted. Because the load generator, API, and
both data stores share one machine, absolute latencies are pessimistic versus a
real multi-node deployment; the *relative* results (index speedup, cache hit
rate) are representative.

Reproduce the stack:
```bash
docker compose -f docker-compose.measure.yml up -d postgres redis
docker exec -i fdp-pg psql -U fdp -d fdp < migrations/001_create_predictions.sql
FDP_DATABASE_URL=postgresql+psycopg://fdp:fdp@localhost:5432/fdp \
  python -m scripts.seed_predictions --rows 200000
```

---

## 1. Prediction-lookup query: before vs. after the (route, carrier) index

Table seeded with **200,000** rows. The lookup is the query behind
`GET /predictions/recent` / `SqlPredictionRepository.find_recent`.

**Command** (run inside the Postgres container, before and after applying
`migrations/002_add_route_carrier_index.sql`):
```bash
docker exec fdp-pg psql -U fdp -d fdp -c "EXPLAIN ANALYZE \
  SELECT delay_probability, will_be_delayed, risk_level, model_version \
  FROM predictions \
  WHERE route='SFO-ATL' AND carrier='AS' AND dep_hour=4 \
  ORDER BY created_at DESC LIMIT 1;"
```

| | Plan | Execution Time (first run) | Execution Time (warm repeats) |
|---|---|---|---|
| **Before** (no index) | Index Scan Backward on `idx_predictions_created_at`, **Rows Removed by Filter: 7399** | **3.503 ms** | 2.162 ms, 2.259 ms |
| **After** `idx_predictions_route_carrier` | Bitmap Index Scan on `idx_predictions_route_carrier` (113 rows) → top-N sort | **0.411 ms** | 0.434 ms, 0.502 ms |

→ The index turns a 7,399-row filtered backward scan into a 113-row bitmap index
scan: **~8.5× faster** on the first run (3.503 ms → 0.411 ms), ~5× warm.

---

## 2. Redis cache hit rate (during the load test)

Stats reset (`redis-cli CONFIG RESETSTAT`) before the Locust run; pulled after.

**Command:**
```bash
docker exec fdp-redis redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
```
**Output:**
```
keyspace_hits:67998
keyspace_misses:14641
```
→ Hit rate = 67998 / (67998 + 14641) = **82.3 %** (82,639 cache lookups total,
one per `/predict`).

---

## 3. Write throughput to RDS (during the load test)

Seed rows carry `model_version = 'seed'` and are excluded; the window is derived
from the real first/last logged timestamps.

**Command:**
```bash
docker exec fdp-pg psql -U fdp -d fdp -c "SELECT count(*) AS rows, \
  EXTRACT(EPOCH FROM (max(created_at)-min(created_at))) AS span_seconds, \
  round(count(*)/EXTRACT(EPOCH FROM (max(created_at)-min(created_at)))::numeric, 1) AS writes_per_sec \
  FROM predictions WHERE model_version <> 'seed';"
```
**Output:**
```
 rows  | span_seconds | writes_per_sec
-------+--------------+----------------
 82639 |   180.436011 |          458.0
```
→ **458.0 writes/sec** (82,639 prediction rows over 180.44 s).

---

## 4. Load-test latency (Locust report)

**Command:**
```bash
locust -f loadtest/locustfile.py --host http://localhost:8000 \
  --headless --csv loadtest/report --only-summary
```
(`BurstShape` ramps to a 200-user peak; total run 180 s.)

From `loadtest/report_stats.csv`, Aggregated row:

| Metric | Value |
|---|---|
| Requests | 90,671 |
| Failures | 0 (0.00%) |
| Throughput | 502.4 req/s |
| Median (p50) | 110 ms |
| **p99** | **390 ms** |
| p99.9 | 640 ms |
| Max | 770 ms |

→ **p99 = 390 ms** at the 200-user burst peak, zero failures. (Single-laptop
stack; the API alone reports ~2–6 ms `latency_ms` per prediction — the rest is
queueing under co-located load.)

---

## 5. CI workflow duration & ASG scale-out

### GitHub Actions `ci.yml` — local run via `act`
The real Actions-tab duration requires pushing to GitHub (out of scope here:
local-only). Captured instead by running the workflow locally with
[`act`](https://github.com/nektos/act):

**Command:**
```bash
act -W .github/workflows/ci.yml -j test --container-architecture linux/amd64
```
Per-step durations reported by `act` (medium runner image
`catthehacker/ubuntu:act-latest`):

| Step | Duration |
|---|---|
| `actions/checkout@v4` | 0.31 s |
| `actions/setup-python@v5` | 24.79 s |
| Install dependencies | 1 m 29.57 s |
| Run tests | 6.58 s → **14 passed** |
| **Sum of job steps** | **~121 s (2 m 1 s)** |
| Total `act` wall time | 222 s (includes one-time ~500 MB runner-image pull) |

- ⚠️ This is a *local proxy*, not the GitHub-hosted runner time. The
  post-`setup-python` cache cleanup reports a benign `node not found` error
  (a known `act`/medium-image limitation); every actual workflow step succeeded.
- On GitHub, read the real duration from the **Actions** tab → workflow run →
  job timing (dependency install is typically faster there thanks to `pip` caching).

### ASG scale-out during burst — PENDING (requires live AWS)
Cannot be captured without `terraform apply` (deliberately not run — see the
task constraints). On a deployed stack, capture the real instance-count change
and scaling activity with:
```bash
# instance count over time
aws autoscaling describe-auto-scaling-groups --auto-scaling-group-names fdp-asg \
  --query "AutoScalingGroups[0].Instances[].InstanceId"
# scaling activities triggered by the request/CPU target-tracking policies
aws autoscaling describe-scaling-activities --auto-scaling-group-name fdp-asg \
  --query "Activities[].{Time:StartTime,Desc:Description,Cause:Cause}"
```
Record the desired-capacity change (e.g. 2 → N) and the peak p99 from the same
Locust report pointed at the ALB URL.

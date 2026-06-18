# Load test

A [Locust](https://locust.io/) load test that drives burst traffic at the
`/predict` endpoint, mixing repeated and random requests so both the Redis cache
and model inference paths are exercised.

## Install

```bash
pip install -r requirements-dev.txt    # includes locust
```

## Run headless (CI / measurement)

```bash
locust -f loadtest/locustfile.py --host http://localhost:8000 \
    --headless -u 200 -r 20 -t 3m --csv loadtest/report
```

- `--csv loadtest/report` writes `report_stats.csv` (incl. p99 latency) used in
  [`../METRICS.md`](../METRICS.md).
- Against the deployed stack, point `--host` at the ALB URL (`terraform output api_url`).

## Run with the web UI

```bash
locust -f loadtest/locustfile.py --host http://localhost:8000
# open http://localhost:8089
```

## Traffic profile

| Task              | Weight | Purpose                          |
|-------------------|--------|----------------------------------|
| `/predict [hot]`  | 7      | Repeated tuples → Redis cache hits |
| `/predict [random]` | 3    | Cache misses → model inference   |
| `/health`         | 1      | Liveness noise                   |

`BurstShape` ramps to 200 users and sustains a peak so the ASG's request/CPU
target-tracking policies scale out.

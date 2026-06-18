.PHONY: install train test run docker-up docker-down measure-up measure-down loadtest tf-validate clean

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

train:
	python -m ml.train

test:
	python -m pytest -q

run:
	python -m uvicorn app.main:app --reload --port 8000

docker-up:
	docker compose up --build

docker-down:
	docker compose down

# Full local stack (API + Postgres + Redis) used for the METRICS.md measurements.
measure-up:
	docker compose -f docker-compose.measure.yml up -d postgres redis
	docker exec -i fdp-pg psql -U fdp -d fdp < migrations/001_create_predictions.sql
	docker exec -i fdp-pg psql -U fdp -d fdp < migrations/002_add_route_carrier_index.sql
	docker compose -f docker-compose.measure.yml up -d --build api

measure-down:
	docker compose -f docker-compose.measure.yml down -v

# Burst load test against the local stack (writes loadtest/report_*.csv).
loadtest:
	locust -f loadtest/locustfile.py --host http://localhost:8000 \
		--headless --csv loadtest/report --only-summary

tf-validate:
	cd infra/terraform && terraform fmt -recursive -check && \
		terraform init -backend=false -input=false >/dev/null && terraform validate

clean:
	rm -rf models/model.pkl models/metrics.json .pytest_cache __pycache__

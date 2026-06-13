.PHONY: install train test run docker-up docker-down clean

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

clean:
	rm -rf models/model.pkl models/metrics.json .pytest_cache __pycache__

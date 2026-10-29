.PHONY: install run test docker clean

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

run:
	cd backend && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	cd backend && .venv/bin/python scripts/smoke_test.py

docker:
	docker compose up --build

clean:
	find backend -name __pycache__ -type d -exec rm -rf {} + ; rm -rf backend/data

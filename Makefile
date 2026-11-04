.PHONY: api web test test-api test-ml train alerts

api:
	cd services/api && uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

test: test-api test-ml

test-api:
	cd services/api && python -m pytest -q

test-ml:
	cd ml && python -m pytest -q

train:
	cd ml && python -m startsit_ml.train --seasons 2018-2025 --test-season 2025

alerts:
	cd services/api && python -m app.jobs.inactive_watch

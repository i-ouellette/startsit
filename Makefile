.PHONY: api web test test-api test-ml train predict alerts

SEASON ?= 2026

api:
	cd services/api && uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

test: test-api test-ml

test-api:
	cd services/api && python -m pytest -q

test-ml:
	cd ml && python -m pytest -q

# Train on completed seasons and backtest on the last one (re-run once a season).
train:
	cd ml && python -m startsit_ml.train --seasons 2018-2025 --test-season 2025

# Score the next unplayed week of SEASON (re-run each week, e.g. Tuesday after MNF).
predict:
	cd ml && python -m startsit_ml.predict --season $(SEASON)

alerts:
	cd services/api && python -m app.jobs.inactive_watch

# startsit

**Start/sit decisions that know your league, and how much risk you want to take.**

Paste a Sleeper username → startsit reads your real roster and scoring settings, projects every player as a
**floor / median / ceiling** range, and solves for your optimal lineup. Drag the risk slider from
*play it safe* to *swing big* and watch the lineup reshuffle. Turn on alerts and it tells you, before kickoff,
when a starter is ruled out and who to swap in.

## How it works

- **League sync:** public Sleeper API (no login) → leagues, rosters, `roster_positions`, scoring
- **Projections as distributions:** LightGBM quantile models (p10 / p50 / p90) trained on nflverse data
- **Risk slider:** `score = median + r·(ceiling − median)` for `r > 0`, toward the floor for `r < 0`
- **Optimal lineup:** players × slots assignment solved exactly (`scipy.optimize.linear_sum_assignment`),
  so FLEX / SUPER_FLEX / REC_FLEX are always handled correctly (greedy fill isn't)
- **Game-day alerts:** scheduled job diffs starters against injury status and sends the best swap once

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/ROADMAP.md](docs/ROADMAP.md).

## Repo layout

```
apps/web/          Next.js frontend
services/api/      FastAPI backend (Sleeper client, projector, optimizer, alerts job)
ml/                Training pipeline (nflverse → features → quantile models → artifacts/)
docs/              Architecture + roadmap
```

## Quick start

```bash
# API  (http://localhost:8000/docs)
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Web  (http://localhost:3000)
cd apps/web
npm install
npm run dev

# Train models, then score this week (downloads nflverse data on first run)
cd ml
pip install -e ".[dev]"
python -m startsit_ml.train --seasons 2018-2025 --test-season 2025
python -m startsit_ml.predict --season 2026
```

Or use `make api`, `make web`, `make test`, `make train`, `make predict`.
The API picks up new weekly projections automatically, with no restart needed.

## Results

_Backtest numbers land here after milestone M2 (p50 MAE vs rolling-average baseline, p10–p90 coverage)._

## Status

M0 scaffold complete: tests cover the optimizer, risk scoring, API routes, the alert job (all against a
mocked Sleeper league) and the ML pipeline on synthetic data. Next: run it against a live league (M1).

"""Projectors return a floor/median/ceiling distribution per player.

- BaselineProjector: rolling mean/std of recent weekly fantasy points (from Sleeper stats).
- ModelProjector: loads the quantile models trained in `ml/` (milestone M2).
"""

from __future__ import annotations

import asyncio
import logging
import statistics
from pathlib import Path
from typing import Protocol

from app.clients.sleeper import SleeperClient, SleeperError
from app.models import Projection

log = logging.getLogger(__name__)

Z90 = 1.2816  # z-score for the 10th/90th percentile of a normal distribution

# Shrink small samples toward a position prior so one big week doesn't dominate.
POSITION_PRIOR = {  # (mean, std) half-PPR-ish weekly points
    "QB": (16.0, 7.0),
    "RB": (9.0, 6.5),
    "WR": (9.0, 6.5),
    "TE": (6.5, 5.0),
    "K": (7.5, 3.5),
    "DEF": (7.0, 5.0),
}
PRIOR_WEIGHT_WEEKS = 2.0

SCORING_KEY = {"ppr": "pts_ppr", "half_ppr": "pts_half_ppr", "standard": "pts_std"}


def scoring_format(scoring_settings: dict | None) -> str:
    rec = float((scoring_settings or {}).get("rec", 0) or 0)
    if rec >= 1:
        return "ppr"
    if rec >= 0.5:
        return "half_ppr"
    return "standard"


def risk_score(p: Projection, risk: float) -> float:
    """Blend toward ceiling (risk > 0) or floor (risk < 0). See docs/ARCHITECTURE.md."""
    r = max(-1.0, min(1.0, risk))
    if r >= 0:
        return p.median + r * (p.ceiling - p.median)
    return p.median + r * (p.median - p.floor)


def distribution_from_samples(samples: list[float], position: str | None) -> Projection:
    prior_mean, prior_std = POSITION_PRIOR.get(position or "", (6.0, 5.0))
    n = len(samples)
    mean = (sum(samples) + prior_mean * PRIOR_WEIGHT_WEEKS) / (n + PRIOR_WEIGHT_WEEKS)
    if n >= 2:
        sample_std = statistics.stdev(samples)
        std = (sample_std * n + prior_std * PRIOR_WEIGHT_WEEKS) / (n + PRIOR_WEIGHT_WEEKS)
    else:
        std = prior_std
    floor = max(0.0, mean - Z90 * std)
    ceiling = mean + Z90 * std
    return Projection(
        floor=round(floor, 2), median=round(mean, 2), ceiling=round(ceiling, 2), source="baseline"
    )


class Projector(Protocol):
    async def project(
        self, player_ids: list[str], positions: dict[str, str | None],
        season: int, week: int, scoring: str,
    ) -> dict[str, Projection]: ...


class BaselineProjector:
    def __init__(self, sleeper: SleeperClient, lookback_weeks: int = 4) -> None:
        self.sleeper = sleeper
        self.lookback = lookback_weeks

    async def _recent_stats(self, season: int, week: int) -> list[dict[str, dict]]:
        weeks = [w for w in range(week - 1, max(0, week - 1 - self.lookback), -1) if w >= 1]

        async def fetch(w: int) -> dict[str, dict]:
            try:
                return await self.sleeper.get_week_stats(season, w)
            except (SleeperError, Exception) as exc:  # noqa: BLE001 - undocumented endpoint
                log.warning("stats fetch failed for week %s: %s", w, exc)
                return {}

        return list(await asyncio.gather(*(fetch(w) for w in weeks)))

    async def project(self, player_ids, positions, season, week, scoring):
        key = SCORING_KEY.get(scoring, "pts_half_ppr")
        weekly = await self._recent_stats(season, week)
        out: dict[str, Projection] = {}
        for pid in player_ids:
            samples: list[float] = []
            for stats in weekly:
                row = stats.get(pid)
                # Only count weeks the player actually played (gp == games played).
                if row and row.get("gp", 1) and key in row:
                    samples.append(float(row[key]))
            out[pid] = distribution_from_samples(samples, positions.get(pid))
        return out


class ModelProjector:
    """Serves the LightGBM quantile models produced by `ml/startsit_ml/train.py` (M2)."""

    def __init__(self, model_dir: str) -> None:
        self.model_dir = Path(model_dir)
        if not (self.model_dir / "manifest.json").exists():
            raise FileNotFoundError(
                f"No trained model in {self.model_dir}. Run `make train` or use projector=baseline."
            )
        # TODO(M2): load manifest + per-quantile boosters, and a feature builder for the week.

    async def project(self, player_ids, positions, season, week, scoring):
        raise NotImplementedError("ModelProjector lands in milestone M2")

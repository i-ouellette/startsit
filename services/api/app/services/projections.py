"""Projectors return a floor/median/ceiling distribution per player.

- BaselineProjector: rolling mean/std of recent weekly fantasy points (from Sleeper stats).
- ModelProjector: serves weekly quantile-model projections scored by `ml/` (falls back to baseline).
"""

from __future__ import annotations

import asyncio
import json
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
    """Serves weekly projections written by `ml/startsit_ml/predict.py`.

    Reads artifacts/projections/{season}_w{week}.json. Players the model doesn't cover
    (kickers, defenses, rookies with no Sleeper ID match) and any week without a file
    fall back to the baseline. Players on bye get a zero projection.
    """

    def __init__(self, model_dir: str, fallback: Projector) -> None:
        self.dir = Path(model_dir) / "projections"
        self.fallback = fallback
        self._cache: dict[Path, tuple[float, dict]] = {}

    def _load(self, season: int, week: int) -> dict | None:
        path = self.dir / f"{season}_w{week}.json"
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            log.info("no model projections at %s; using baseline", path)
            return None
        cached = self._cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        data = json.loads(path.read_text())
        self._cache[path] = (mtime, data)
        return data

    async def project(self, player_ids, positions, season, week, scoring):
        data = self._load(season, week)
        table = (data or {}).get("scorings", {}).get(scoring)
        if table is None:
            return await self.fallback.project(player_ids, positions, season, week, scoring)

        bye = set(data.get("bye", []))
        out: dict[str, Projection] = {}
        missing: list[str] = []
        for pid in player_ids:
            if pid in bye:
                out[pid] = Projection(floor=0, median=0, ceiling=0, source="bye")
            elif pid in table:
                f, m, c = table[pid]
                out[pid] = Projection(floor=f, median=m, ceiling=c, source="model")
            else:
                missing.append(pid)
        if missing:
            out.update(await self.fallback.project(missing, positions, season, week, scoring))
        return out

"""Score an upcoming week and write projections the API can serve.

    python -m startsit_ml.predict --season 2026            # next unplayed week
    python -m startsit_ml.predict --season 2026 --week 10

Output: artifacts/projections/{season}_w{week}.json
    {"season", "week", "generated_at",
     "scorings": {"ppr": {"<sleeper_id>": [floor, median, ceiling]}, ...},
     "bye": ["<sleeper_id>", ...]}
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from startsit_ml.data import load_schedule, load_sleeper_crosswalk, load_weekly
from startsit_ml.features import build_features
from startsit_ml.train import ARTIFACTS, QUANTILES


def upcoming_rows(
    hist: pd.DataFrame, schedule: pd.DataFrame, season: int, week: int
) -> tuple[pd.DataFrame, list[str]]:
    """One empty-stat row per active player for their week-`week` game, plus players on bye."""
    played = hist[(hist["season"] == season) & (hist["week"] < week)]
    latest = (
        played.sort_values("week")
        .groupby("player_id")
        .tail(1)[["player_id", "player_display_name", "position", "team"]]
    )
    games = schedule[(schedule["season"] == season) & (schedule["week"] == week)]
    opponent = {**dict(zip(games["home_team"], games["away_team"], strict=True)),
                **dict(zip(games["away_team"], games["home_team"], strict=True))}

    latest = latest.assign(opponent_team=latest["team"].map(opponent))
    on_bye = latest[latest["opponent_team"].isna()]["player_id"].tolist()
    rows = latest.dropna(subset=["opponent_team"]).assign(
        season=season, week=week, season_type="REG"
    )
    return rows, on_bye


def predict_week(
    hist: pd.DataFrame,
    schedule: pd.DataFrame,
    crosswalk: pd.DataFrame,
    season: int,
    week: int,
    model_dir: Path = ARTIFACTS,
) -> dict:
    manifest = json.loads((model_dir / "manifest.json").read_text())

    # Only information available before kickoff of `week`.
    known = hist[(hist["season"] < season) | ((hist["season"] == season) & (hist["week"] < week))]
    rows, on_bye = upcoming_rows(known, schedule, season, week)
    feats, _ = build_features(pd.concat([known, rows], ignore_index=True))
    target = feats[(feats["season"] == season) & (feats["week"] == week)]
    X = target[manifest["features"]]

    to_sleeper = dict(zip(crosswalk["gsis_id"], crosswalk["sleeper_id"], strict=True))
    sleeper_ids = target["player_id"].map(to_sleeper)
    keep = sleeper_ids.notna().to_numpy()

    out: dict[str, dict[str, list[float]]] = {}
    for scoring in manifest["scorings"]:
        q = np.column_stack([
            lgb.Booster(model_file=str(model_dir / f"{scoring}_{name}.txt")).predict(X)
            for name in QUANTILES
        ])
        q = np.sort(np.clip(q, 0, None), axis=1)  # enforce floor <= median <= ceiling
        out[scoring] = {
            sid: [round(float(v), 2) for v in row]
            for sid, row in zip(sleeper_ids[keep], q[keep], strict=True)
        }

    return {
        "season": season,
        "week": week,
        "generated_at": datetime.now(UTC).isoformat(),
        "scorings": out,
        "bye": sorted({to_sleeper[p] for p in on_bye if p in to_sleeper}),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, default=None, help="Defaults to the next unplayed week")
    ap.add_argument("--history-from", type=int, default=2018)
    args = ap.parse_args()

    hist = load_weekly(list(range(args.history_from, args.season + 1)), refresh={args.season})
    current = hist[hist["season"] == args.season]
    week = args.week or (int(current["week"].max()) + 1 if not current.empty else 1)

    result = predict_week(hist, load_schedule(args.season), load_sleeper_crosswalk(),
                          args.season, week)
    path = ARTIFACTS / "projections" / f"{args.season}_w{week}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    n = len(next(iter(result["scorings"].values()), {}))
    print(f"wrote {path} ({n} players, {len(result['bye'])} on bye)")


if __name__ == "__main__":
    main()

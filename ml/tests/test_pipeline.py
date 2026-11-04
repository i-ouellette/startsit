"""Runs the full feature + training pipeline on synthetic data (no network)."""

import json

import numpy as np
import pandas as pd

from startsit_ml.features import build_features
from startsit_ml.train import train


def synthetic_weekly(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    teams = ["BUF", "MIA", "NYJ", "NE", "KC", "LV", "DEN", "LAC"]
    rows = []
    for pid in range(60):
        pos = ["QB", "RB", "WR", "TE"][pid % 4]
        talent = rng.uniform(4, 20)
        for season in (2023, 2024, 2025):
            for week in range(1, 18):
                targets = max(0, rng.normal(talent / 2, 2)) if pos != "QB" else 0
                rec = targets * 0.65
                pts = max(0.0, rng.normal(talent, talent * 0.45))
                rows.append(dict(
                    player_id=f"p{pid}", player_display_name=f"Player {pid}", position=pos,
                    team=teams[pid % 8], opponent_team=teams[(pid + week) % 8],
                    season=season, week=week, season_type="REG",
                    attempts=30 if pos == "QB" else 0, carries=rng.poisson(8) if pos == "RB" else 0,
                    targets=targets, receptions=rec, target_share=targets / 35,
                    air_yards_share=0.1, wopr=0.3, receiving_air_yards=targets * 8,
                    passing_yards=250 if pos == "QB" else 0, rushing_yards=30, receiving_yards=rec * 11,
                    fantasy_points=pts - rec, fantasy_points_ppr=pts,
                ))
    return pd.DataFrame(rows)


def test_features_are_lagged():
    df = synthetic_weekly()
    feats, cols = build_features(df)
    row = feats[(feats.player_id == "p0") & (feats.season == 2023) & (feats.week == 2)].iloc[0]
    week1 = df[(df.player_id == "p0") & (df.season == 2023) & (df.week == 1)].iloc[0]
    # Week-2 rolling feature must equal week-1 actual (no leakage of week-2 result).
    assert row["fantasy_points_ppr_r3"] == week1["fantasy_points_ppr"]
    assert "fp_ppr" not in cols and "fantasy_points_ppr" not in cols


def test_train_writes_artifacts(tmp_path):
    metrics = train(synthetic_weekly(), test_season=2025, out=tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert set(manifest["quantiles"]) == {"floor", "median", "ceiling"}
    assert (tmp_path / "fp_ppr_ceiling.txt").exists()
    assert 0.5 < metrics["coverage_p10_p90"] < 0.95

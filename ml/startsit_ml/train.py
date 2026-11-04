"""Train p10/p50/p90 LightGBM models and backtest them on a held-out season.

    python -m startsit_ml.train --seasons 2018-2025 --test-season 2025
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from startsit_ml.data import load_weekly
from startsit_ml.features import build_features

QUANTILES = {"floor": 0.1, "median": 0.5, "ceiling": 0.9}
ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
PARAMS = dict(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=40,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)


def pinball(y: np.ndarray, q: np.ndarray, alpha: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


def train(df: pd.DataFrame, test_season: int, target: str = "fp_ppr", out: Path = ARTIFACTS) -> dict:
    feats, cols = build_features(df)
    train_df = feats[feats["season"] < test_season]
    test_df = feats[feats["season"] == test_season]
    if train_df.empty or test_df.empty:
        raise ValueError("Need data before and in the test season")

    out.mkdir(parents=True, exist_ok=True)
    preds: dict[str, np.ndarray] = {}
    for name, alpha in QUANTILES.items():
        model = lgb.LGBMRegressor(objective="quantile", alpha=alpha, **PARAMS)
        model.fit(train_df[cols], train_df[target])
        preds[name] = model.predict(test_df[cols])
        model.booster_.save_model(str(out / f"{target}_{name}.txt"))

    y = test_df[target].to_numpy()
    lo, mid, hi = np.minimum(preds["floor"], preds["median"]), preds["median"], preds["ceiling"]
    baseline = test_df["fantasy_points_ppr_r3"].fillna(test_df["fantasy_points_ppr_r8"]).fillna(0)

    metrics = {
        "test_season": test_season,
        "n_test": int(len(y)),
        "mae_p50": round(float(np.mean(np.abs(y - mid))), 3),
        "mae_baseline_r3": round(float(np.mean(np.abs(y - baseline))), 3),
        "coverage_p10_p90": round(float(np.mean((y >= lo) & (y <= hi))), 3),  # target ~0.80
        "pinball": {n: round(pinball(y, preds[n], a), 3) for n, a in QUANTILES.items()},
        "by_position": {
            pos: round(float(np.mean(np.abs(y[m] - mid[m]))), 3)
            for pos in sorted(test_df["position"].unique())
            if (m := (test_df["position"] == pos).to_numpy()).any()
        },
    }
    manifest = {
        "target": target,
        "features": cols,
        "quantiles": QUANTILES,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return metrics


def _parse_seasons(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2018-2025")
    ap.add_argument("--test-season", type=int, default=2025)
    ap.add_argument("--target", default="fp_ppr", choices=["fp_ppr", "fp_half", "fp_std"])
    args = ap.parse_args()
    df = load_weekly(_parse_seasons(args.seasons))
    print(json.dumps(train(df, args.test_season, args.target), indent=2))


if __name__ == "__main__":
    main()

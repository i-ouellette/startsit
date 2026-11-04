"""Train p10/p50/p90 LightGBM models per scoring format and backtest on a held-out season.

    python -m startsit_ml.train --seasons 2018-2025 --test-season 2025
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from startsit_ml.data import load_weekly
from startsit_ml.features import build_features

QUANTILES = {"floor": 0.1, "median": 0.5, "ceiling": 0.9}
TARGETS = {"ppr": "fp_ppr", "half_ppr": "fp_half", "standard": "fp_std"}
ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"
PARAMS = dict(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=40,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)


def pinball(y: np.ndarray, q: np.ndarray, alpha: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


def _fit(train_df: pd.DataFrame, cols: list[str], target: str, alpha: float) -> lgb.LGBMRegressor:
    model = lgb.LGBMRegressor(objective="quantile", alpha=alpha, **PARAMS)
    model.fit(train_df[cols], train_df[target])
    return model


def train(df: pd.DataFrame, test_season: int, out: Path = ARTIFACTS,
          scorings: list[str] | None = None) -> dict:
    """Backtest on `test_season`, then refit on all data and save models + manifest."""
    feats, cols = build_features(df)
    train_df = feats[feats["season"] < test_season]
    test_df = feats[feats["season"] == test_season]
    if train_df.empty or test_df.empty:
        raise ValueError("Need data before and in the test season")

    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, dict] = {}
    for scoring in scorings or list(TARGETS):
        target = TARGETS[scoring]
        preds = {n: _fit(train_df, cols, target, a).predict(test_df[cols])
                 for n, a in QUANTILES.items()}

        y = test_df[target].to_numpy()
        lo, mid, hi = np.minimum(preds["floor"], preds["median"]), preds["median"], preds["ceiling"]
        # Baseline = what the rolling-average projector would have said.
        rec_adj = {"fp_ppr": 0.0, "fp_half": 0.5, "fp_std": 1.0}[target]
        baseline = (
            test_df["fantasy_points_ppr_r3"] - rec_adj * test_df["receptions_r3"].fillna(0)
        ).fillna(0)

        report[scoring] = {
            "n_test": int(len(y)),
            "mae_p50": round(float(np.mean(np.abs(y - mid))), 3),
            "mae_baseline_r3": round(float(np.mean(np.abs(y - baseline))), 3),
            "coverage_p10_p90": round(float(np.mean((y >= lo) & (y <= hi))), 3),  # aim ~0.80
            "pinball": {n: round(pinball(y, preds[n], a), 3) for n, a in QUANTILES.items()},
            "mae_by_position": {
                pos: round(float(np.mean(np.abs(y[m] - mid[m]))), 3)
                for pos in sorted(test_df["position"].unique())
                if (m := (test_df["position"] == pos).to_numpy()).any()
            },
        }

        # Production models see every season, including the backtest one.
        for name, alpha in QUANTILES.items():
            _fit(feats, cols, target, alpha).booster_.save_model(str(out / f"{scoring}_{name}.txt"))

    manifest = {
        "features": cols,
        "quantiles": QUANTILES,
        "scorings": list(report),
        "test_season": test_season,
        "trained_at": datetime.now(UTC).isoformat(),
        "metrics": report,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return report


def parse_seasons(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="2018-2025")
    ap.add_argument("--test-season", type=int, default=2025)
    args = ap.parse_args()
    df = load_weekly(parse_seasons(args.seasons))
    print(json.dumps(train(df, args.test_season), indent=2))


if __name__ == "__main__":
    main()

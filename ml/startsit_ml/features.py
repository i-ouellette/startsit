"""Feature engineering. Every feature is *lagged* (only info known before kickoff)."""

from __future__ import annotations

import numpy as np
import pandas as pd

USAGE = [
    "fantasy_points_ppr", "attempts", "carries", "targets", "receptions",
    "target_share", "air_yards_share", "wopr", "receiving_air_yards",
    "passing_yards", "rushing_yards", "receiving_yards",
]
WINDOWS = (3, 8)
TARGET = "fantasy_points_ppr"
POSITION_CODES = {"QB": 0, "RB": 1, "WR": 2, "TE": 3}


def add_scoring_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    rec = df["receptions"].fillna(0)
    df["fp_ppr"] = df["fantasy_points_ppr"]
    df["fp_half"] = df["fantasy_points_ppr"] - 0.5 * rec
    df["fp_std"] = df["fantasy_points_ppr"] - rec
    return df


def _player_rolling(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["player_id", "season", "week"]).copy()
    g = df.groupby("player_id", group_keys=False)
    for col in USAGE:
        if col not in df.columns:
            continue
        lagged = g[col].shift(1)
        for w in WINDOWS:
            df[f"{col}_r{w}"] = (
                lagged.groupby(df["player_id"]).rolling(w, min_periods=1).mean()
                .reset_index(level=0, drop=True)
            )
    lagged_fp = g[TARGET].shift(1)
    df["fp_volatility_r8"] = (
        lagged_fp.groupby(df["player_id"]).rolling(8, min_periods=2).std()
        .reset_index(level=0, drop=True)
    )
    df["games_played_prior"] = g.cumcount()
    return df


def _defense_allowed(df: pd.DataFrame) -> pd.DataFrame:
    """Rolling PPR points each defense allowed to each position (lagged)."""
    allowed = (
        df.groupby(["opponent_team", "position", "season", "week"], as_index=False)[TARGET].sum()
        .sort_values(["opponent_team", "position", "season", "week"])
    )
    grp = allowed.groupby(["opponent_team", "position"])[TARGET]
    allowed["def_allowed_r6"] = grp.transform(lambda s: s.shift(1).rolling(6, min_periods=1).mean())
    return df.merge(
        allowed[["opponent_team", "position", "season", "week", "def_allowed_r6"]],
        on=["opponent_team", "position", "season", "week"],
        how="left",
    )


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = add_scoring_targets(df)
    df = _player_rolling(df)
    df = _defense_allowed(df)
    # Fixed mapping so training and weekly scoring always agree.
    df["position_code"] = df["position"].map(POSITION_CODES).fillna(-1).astype(int)
    feature_cols = sorted(set(
        [c for c in df.columns if c.endswith(tuple(f"_r{w}" for w in WINDOWS))]
        + ["fp_volatility_r8", "def_allowed_r6", "games_played_prior", "position_code", "week"]
    ))
    # Need at least one prior game to say anything useful.
    df = df[df["games_played_prior"] >= 1].replace([np.inf, -np.inf], np.nan)
    return df, feature_cols

"""Load nflverse weekly player stats + the Sleeper ID crosswalk.

Data dictionary: https://nflreadr.nflverse.com/articles/dictionary_player_stats.html
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

POSITIONS = ["QB", "RB", "WR", "TE"]
CACHE = Path(__file__).resolve().parent.parent / "data"

STAT_COLUMNS = [
    "player_id", "player_display_name", "position", "team", "opponent_team",
    "season", "week", "season_type",
    "attempts", "passing_yards", "passing_tds",
    "carries", "rushing_yards", "rushing_tds",
    "targets", "receptions", "receiving_yards", "receiving_tds", "receiving_air_yards",
    "target_share", "air_yards_share", "wopr",
    "fantasy_points", "fantasy_points_ppr",
]


def load_weekly(seasons: list[int], use_cache: bool = True) -> pd.DataFrame:
    """Regular-season weekly stats for skill positions, cached as parquet."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"weekly_{min(seasons)}_{max(seasons)}.parquet"
    if use_cache and path.exists():
        return pd.read_parquet(path)

    import nflreadpy as nfl  # imported lazily so tests don't need network

    df = nfl.load_player_stats(seasons, summary_level="week").to_pandas()
    df = df[[c for c in STAT_COLUMNS if c in df.columns]]
    df = df[(df["season_type"] == "REG") & (df["position"].isin(POSITIONS))].copy()
    df.to_parquet(path)
    return df


def load_sleeper_crosswalk() -> pd.DataFrame:
    """gsis_id (nflverse) <-> sleeper_id mapping, from the ffverse player-ID table."""
    import nflreadpy as nfl

    ids = nfl.load_ff_playerids().to_pandas()
    return ids[["gsis_id", "sleeper_id", "name", "position"]].dropna(subset=["gsis_id", "sleeper_id"])

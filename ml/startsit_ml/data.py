"""Load nflverse weekly player stats, schedules and the Sleeper ID crosswalk.

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


def _load_season(season: int, refresh: bool) -> pd.DataFrame:
    """One season of regular-season skill-position stats, cached as parquet per season."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f"weekly_{season}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)

    import nflreadpy as nfl  # imported lazily so tests don't need network

    df = nfl.load_player_stats([season], summary_level="week").to_pandas()
    df = df[[c for c in STAT_COLUMNS if c in df.columns]]
    df = df[(df["season_type"] == "REG") & (df["position"].isin(POSITIONS))].copy()
    df.to_parquet(path)
    return df


def load_weekly(seasons: list[int], refresh: set[int] | None = None) -> pd.DataFrame:
    """Weekly stats for several seasons. Seasons in `refresh` are re-downloaded
    (use this for the in-progress season, which changes every week)."""
    refresh = refresh or set()
    return pd.concat([_load_season(s, s in refresh) for s in seasons], ignore_index=True)


def load_schedule(season: int) -> pd.DataFrame:
    """Regular-season games: season, week, home_team, away_team."""
    import nflreadpy as nfl

    games = nfl.load_schedules([season]).to_pandas()
    games = games[games["game_type"] == "REG"]
    return games[["season", "week", "home_team", "away_team"]].reset_index(drop=True)


def load_sleeper_crosswalk() -> pd.DataFrame:
    """gsis_id (nflverse) -> sleeper_id (as string), from the ffverse player-ID table."""
    import nflreadpy as nfl

    ids = nfl.load_ff_playerids().to_pandas()[["gsis_id", "sleeper_id"]]
    ids = ids.dropna(subset=["gsis_id", "sleeper_id"])
    # sleeper_id can arrive as a float (e.g. 4046.0); Sleeper uses plain digit strings.
    ids["sleeper_id"] = ids["sleeper_id"].map(lambda v: str(int(float(v))))
    return ids.drop_duplicates("gsis_id")

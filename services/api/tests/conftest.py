"""Fixtures: a fake Sleeper league served by respx so tests never hit the network."""

from __future__ import annotations

import re

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response

BASE = "https://api.sleeper.app/v1"

PLAYERS = {
    "qb1": {"full_name": "Alpha QB", "position": "QB", "fantasy_positions": ["QB"], "team": "BUF"},
    "qb2": {"full_name": "Backup QB", "position": "QB", "fantasy_positions": ["QB"], "team": "NYJ"},
    "rb1": {"full_name": "Bell Cow", "position": "RB", "fantasy_positions": ["RB"], "team": "SF"},
    "rb2": {"full_name": "Hurt Back", "position": "RB", "fantasy_positions": ["RB"], "team": "DAL",
            "injury_status": "Out"},
    "rb3": {"full_name": "Handcuff", "position": "RB", "fantasy_positions": ["RB"], "team": "DAL"},
    "wr1": {"full_name": "Alpha WR", "position": "WR", "fantasy_positions": ["WR"], "team": "MIN"},
    "wr2": {"full_name": "Deep Threat", "position": "WR", "fantasy_positions": ["WR"],
            "team": "MIA"},
    "wr3": {"full_name": "Slot Guy", "position": "WR", "fantasy_positions": ["WR"], "team": "DET"},
    "wr4": {"full_name": "Possession WR", "position": "WR", "fantasy_positions": ["WR"],
            "team": "GB"},
    "te1": {"full_name": "Tight End", "position": "TE", "fantasy_positions": ["TE"], "team": "KC"},
    "k1": {"full_name": "Kicker", "position": "K", "fantasy_positions": ["K"], "team": "BAL"},
    "PHI": {"first_name": "Philadelphia", "last_name": "Eagles", "position": "DEF",
            "fantasy_positions": ["DEF"], "team": "PHI"},
}

# Weekly PPR points for weeks 5-8 (most recent last).
WEEKLY_PPR = {
    "qb1": [24, 18, 30, 21], "qb2": [12, 10, 15, 9],
    "rb1": [20, 25, 18, 22], "rb2": [15, 14, 16, 13], "rb3": [8, 11, 14, 12],
    "wr1": [19, 21, 17, 24], "wr2": [3, 28, 5, 26], "wr3": [11, 12, 10, 13], "wr4": [9, 10, 9, 10],
    "te1": [9, 7, 11, 8], "k1": [8, 9, 7, 10], "PHI": [6, 12, 4, 9],
}

LEAGUE = {
    "league_id": "L1",
    "name": "Queen's League",
    "season": "2026",
    "total_rosters": 10,
    "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "BN", "BN"],
    "scoring_settings": {"rec": 1.0},
}

ROSTERS = [
    {
        "roster_id": 1,
        "owner_id": "u1",
        "players": list(PLAYERS.keys()),
        # User currently starts the injured RB and the boom/bust WR in FLEX.
        "starters": ["qb1", "rb1", "rb2", "wr1", "wr3", "te1", "wr2", "k1", "PHI"],
        "reserve": [],
        "taxi": [],
    }
]


def _stats_for(week: int) -> dict:
    idx = week - 5
    if not 0 <= idx < 4:
        return {}
    return {pid: {"gp": 1, "pts_ppr": float(pts[idx]), "pts_half_ppr": float(pts[idx]) - 2,
                  "pts_std": float(pts[idx]) - 4}
            for pid, pts in WEEKLY_PPR.items()}


@pytest.fixture
def sleeper_mock():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        mock.get("/state/nfl").mock(return_value=Response(200, json={"season": "2026", "week": 9}))
        mock.get("/user/isaac").mock(
            return_value=Response(200, json={"user_id": "u1", "username": "isaac",
                                             "display_name": "Isaac"}))
        mock.get("/user/nobody").mock(return_value=Response(200, content=b"null"))
        mock.get("/user/u1/leagues/nfl/2026").mock(return_value=Response(200, json=[LEAGUE]))
        mock.get("/league/L1").mock(return_value=Response(200, json=LEAGUE))
        mock.get("/league/L1/rosters").mock(return_value=Response(200, json=ROSTERS))
        mock.get("/players/nfl").mock(return_value=Response(200, json=PLAYERS))
        mock.get(url__regex=re.compile(rf"{re.escape(BASE)}/stats/nfl/regular/2026/(\d+)")).mock(
            side_effect=lambda req: Response(
                200, json=_stats_for(int(str(req.url).rsplit("/", 1)[1]))
            )
        )
        yield mock


@pytest.fixture
def client(sleeper_mock):
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c

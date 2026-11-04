from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.clients.sleeper import SleeperClient, SleeperError
from app.deps import get_projector, get_sleeper
from app.models import LeagueSummary, LineupResponse, Player, UserLeagues
from app.services.lineup import build_lineup, to_player
from app.services.projections import Projector, scoring_format

router = APIRouter(prefix="/v1", tags=["leagues"])


def _http(exc: SleeperError) -> HTTPException:
    return HTTPException(status_code=404 if exc.status == 404 else 502, detail=str(exc))


@router.get("/users/{username}/leagues", response_model=UserLeagues)
async def user_leagues(
    username: str,
    season: int | None = Query(default=None, description="Defaults to the current NFL season"),
    sleeper: SleeperClient = Depends(get_sleeper),
):
    try:
        user = await sleeper.get_user(username)
        if season is None:
            season = int((await sleeper.get_state()).get("season"))
        leagues = await sleeper.get_leagues(user["user_id"], season)
    except SleeperError as exc:
        raise _http(exc) from exc

    return UserLeagues(
        user_id=user["user_id"],
        username=user.get("username") or username,
        display_name=user.get("display_name"),
        leagues=[
            LeagueSummary(
                league_id=lg["league_id"],
                name=lg.get("name") or "Untitled league",
                season=str(lg.get("season")),
                scoring=scoring_format(lg.get("scoring_settings")),
                roster_positions=lg.get("roster_positions") or [],
                total_rosters=lg.get("total_rosters") or 0,
            )
            for lg in leagues
        ],
    )


@router.get("/leagues/{league_id}/rosters/{owner_id}", response_model=list[Player])
async def roster(league_id: str, owner_id: str, sleeper: SleeperClient = Depends(get_sleeper)):
    try:
        rosters = await sleeper.get_rosters(league_id)
        players_db = await sleeper.get_players()
    except SleeperError as exc:
        raise _http(exc) from exc
    r = next((r for r in rosters if str(r.get("owner_id")) == owner_id), None)
    if r is None:
        raise HTTPException(404, f"No roster for owner {owner_id}")
    return [to_player(pid, players_db.get(pid)) for pid in r.get("players") or []]


@router.get("/leagues/{league_id}/lineup", response_model=LineupResponse)
async def lineup(
    league_id: str,
    owner_id: str,
    week: int | None = Query(default=None, ge=1, le=18),
    risk: float = Query(default=0.0, ge=-1.0, le=1.0, description="-1 safest ... +1 biggest swing"),
    sleeper: SleeperClient = Depends(get_sleeper),
    projector: Projector = Depends(get_projector),
):
    try:
        return await build_lineup(sleeper, projector, league_id, owner_id, week, risk)
    except SleeperError as exc:
        raise _http(exc) from exc

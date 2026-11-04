"""Glue: Sleeper roster + projections + risk -> optimal lineup and start/sit swaps."""

from __future__ import annotations

from app.clients.sleeper import SleeperClient, SleeperError
from app.models import LineupResponse, Player, Projection, SlotAssignment, Swap
from app.services.optimizer import Candidate, can_fill, optimize, starting_slots
from app.services.projections import Projector, risk_score, scoring_format

# How much of a player's projection to keep given their injury designation.
AVAILABILITY = {
    "Out": 0.0,
    "IR": 0.0,
    "Sus": 0.0,
    "PUP": 0.0,
    "NA": 0.0,
    "Doubtful": 0.25,
    "Questionable": 0.85,
}


def availability(injury_status: str | None) -> float:
    return AVAILABILITY.get(injury_status or "", 1.0)


def to_player(pid: str, info: dict | None) -> Player:
    info = info or {}
    name = info.get("full_name") or " ".join(
        x for x in (info.get("first_name"), info.get("last_name")) if x
    ) or pid
    eligible = info.get("fantasy_positions") or ([info["position"]] if info.get("position") else [])
    return Player(
        player_id=pid,
        name=name,
        position=info.get("position"),
        eligible=eligible,
        team=info.get("team"),
        injury_status=info.get("injury_status"),
    )


async def build_lineup(
    sleeper: SleeperClient,
    projector: Projector,
    league_id: str,
    owner_id: str,
    week: int | None,
    risk: float,
) -> LineupResponse:
    league, rosters, players_db = (
        await sleeper.get_league(league_id),
        await sleeper.get_rosters(league_id),
        await sleeper.get_players(),
    )
    roster = next((r for r in rosters if str(r.get("owner_id")) == str(owner_id)), None)
    if roster is None:
        raise SleeperError(404, f"No roster for owner {owner_id} in league {league_id}")

    season = int(league.get("season"))
    if week is None:
        week = int((await sleeper.get_state()).get("week") or 1)
    scoring = scoring_format(league.get("scoring_settings"))
    slots = starting_slots(league.get("roster_positions") or [])

    unavailable_holds = set(roster.get("reserve") or []) | set(roster.get("taxi") or [])
    pool_ids = [p for p in (roster.get("players") or []) if p not in unavailable_holds]
    players = {pid: to_player(pid, players_db.get(pid)) for pid in pool_ids}

    projections: dict[str, Projection] = await projector.project(
        pool_ids, {pid: p.position for pid, p in players.items()}, season, week, scoring
    )
    for pid, p in players.items():
        p.projection = projections.get(pid)
        base = risk_score(p.projection, risk) if p.projection else 0.0
        p.score = round(base * availability(p.injury_status), 2)

    candidates = [
        Candidate(pid, frozenset(p.eligible), p.score or 0.0) for pid, p in players.items()
    ]
    assignment = optimize(slots, candidates)

    lineup = [
        SlotAssignment(slot=s, player=players.get(pid) if pid else None) for s, pid in assignment
    ]
    started = {pid for _, pid in assignment if pid}
    bench = sorted(
        (p for pid, p in players.items() if pid not in started),
        key=lambda p: p.score or 0.0,
        reverse=True,
    )

    swaps = _diff_starters(assignment, roster.get("starters") or [], players)
    total = round(sum((a.player.score or 0.0) for a in lineup if a.player), 2)

    return LineupResponse(
        league_id=league_id,
        owner_id=str(owner_id),
        week=week,
        risk=risk,
        scoring=scoring,
        lineup=lineup,
        bench=bench,
        swaps=swaps,
        projected_total=total,
    )


def _diff_starters(
    assignment: list[tuple[str, str | None]], current: list[str], players: dict[str, Player]
) -> list[Swap]:
    """Pair new starters with the current starters they replace (slot-eligible first)."""
    optimal = {pid for _, pid in assignment if pid}
    current_set = {pid for pid in current if pid and pid != "0"}
    to_sit = [pid for pid in current if pid in current_set - optimal]

    swaps: list[Swap] = []
    for slot, pid in assignment:
        if not pid or pid in current_set:
            continue
        start = players[pid]
        sit_id = next(
            (s for s in to_sit if s in players and can_fill(slot, frozenset(players[s].eligible))),
            to_sit[0] if to_sit else None,
        )
        sit = players.get(sit_id) if sit_id else None
        if sit_id:
            to_sit.remove(sit_id)
        gain = (start.score or 0.0) - ((sit.score or 0.0) if sit else 0.0)
        swaps.append(Swap(slot=slot, start=start, sit=sit, gain=round(gain, 2)))
    return swaps

from __future__ import annotations

from pydantic import BaseModel, Field


class Projection(BaseModel):
    floor: float = Field(description="p10 fantasy points")
    median: float = Field(description="p50 fantasy points")
    ceiling: float = Field(description="p90 fantasy points")
    source: str = "baseline"


class Player(BaseModel):
    player_id: str
    name: str
    position: str | None
    eligible: list[str]
    team: str | None
    injury_status: str | None = None
    projection: Projection | None = None
    score: float | None = Field(default=None, description="Risk-adjusted score used for ranking")


class LeagueSummary(BaseModel):
    league_id: str
    name: str
    season: str
    scoring: str
    roster_positions: list[str]
    total_rosters: int


class UserLeagues(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    leagues: list[LeagueSummary]


class SlotAssignment(BaseModel):
    slot: str
    player: Player | None


class Swap(BaseModel):
    slot: str
    start: Player
    sit: Player | None
    gain: float


class LineupResponse(BaseModel):
    league_id: str
    owner_id: str
    week: int
    risk: float
    scoring: str
    lineup: list[SlotAssignment]
    bench: list[Player]
    swaps: list[Swap] = Field(description="Changes vs the roster's currently set starters")
    projected_total: float


class AlertSubscriptionIn(BaseModel):
    league_id: str
    owner_id: str
    email: str | None = None
    risk: float = Field(default=0.0, ge=-1, le=1)


class AlertSubscription(AlertSubscriptionIn):
    id: str

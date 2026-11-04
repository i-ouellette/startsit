"""Optimal lineup = an assignment problem (players x slots), solved exactly.

Greedy ("fill QB, then RB..., then FLEX") can be wrong when a player is eligible
for several slots; linear_sum_assignment is optimal and handles any flex config.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linear_sum_assignment

# Sleeper roster_positions -> which player positions may fill the slot.
SLOT_ELIGIBILITY: dict[str, set[str]] = {
    "QB": {"QB"},
    "RB": {"RB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "K": {"K"},
    "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"WR", "RB"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "DL": {"DL", "DE", "DT"},
    "LB": {"LB"},
    "DB": {"DB", "CB", "S"},
    "IDP_FLEX": {"DL", "DE", "DT", "LB", "DB", "CB", "S"},
}
NON_STARTING = {"BN", "IR", "TAXI"}

INELIGIBLE = -1e6


@dataclass(frozen=True)
class Candidate:
    player_id: str
    eligible: frozenset[str]  # fantasy positions
    score: float


def starting_slots(roster_positions: list[str]) -> list[str]:
    return [s for s in roster_positions if s not in NON_STARTING]


def can_fill(slot: str, eligible: frozenset[str]) -> bool:
    return bool(SLOT_ELIGIBILITY.get(slot, {slot}) & eligible)


def optimize(slots: list[str], candidates: list[Candidate]) -> list[tuple[str, str | None]]:
    """Return [(slot, player_id | None)] in slot order, maximizing total score."""
    if not slots:
        return []
    if not candidates:
        return [(s, None) for s in slots]

    scores = np.full((len(candidates), len(slots)), INELIGIBLE)
    for i, c in enumerate(candidates):
        for j, slot in enumerate(slots):
            if can_fill(slot, c.eligible):
                scores[i, j] = c.score

    rows, cols = linear_sum_assignment(scores, maximize=True)
    assigned: dict[int, str] = {}
    for i, j in zip(rows, cols, strict=True):
        if scores[i, j] > INELIGIBLE / 2:
            assigned[j] = candidates[i].player_id
    return [(slot, assigned.get(j)) for j, slot in enumerate(slots)]

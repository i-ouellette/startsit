"""Game-day alert job.

For every subscribed roster: if a *current starter* is Out/Doubtful/IR (or newly
Questionable), compute the best swap with the optimizer and notify once.

Run on a schedule (Sunday 9:00-13:00 ET every 15 min, plus TNF/MNF windows):
    python -m app.jobs.inactive_watch
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.clients.sleeper import SleeperClient
from app.deps import build_projector
from app.jobs.notifier import ConsoleNotifier, Notifier
from app.services.lineup import build_lineup
from app.services.projections import Projector
from app.store import SubscriptionStore

log = logging.getLogger(__name__)

ALERT_STATUSES = {"Out", "Doubtful", "IR", "Sus", "Questionable"}


@dataclass
class Alert:
    subscription_id: str
    email: str | None
    league_id: str
    player_name: str
    status: str
    swap_in: str | None
    gain: float | None

    def message(self) -> str:
        msg = f"{self.player_name} is {self.status}."
        if self.swap_in:
            msg += f" Start {self.swap_in} instead (+{self.gain:.1f} proj pts)."
        return msg


async def run_once(
    sleeper: SleeperClient, projector: Projector, store: SubscriptionStore, notifier: Notifier
) -> list[Alert]:
    state = await sleeper.get_state()
    week = int(state.get("week") or 1)
    players_db = await sleeper.get_players()
    sent: list[Alert] = []

    for sub in store.all():
        rosters = await sleeper.get_rosters(sub.league_id)
        roster = next((r for r in rosters if str(r.get("owner_id")) == sub.owner_id), None)
        if not roster:
            continue

        flagged = [
            (pid, players_db.get(pid, {}).get("injury_status"))
            for pid in roster.get("starters") or []
            if pid and pid != "0" and players_db.get(pid, {}).get("injury_status") in ALERT_STATUSES
        ]
        if not flagged:
            continue

        lineup = await build_lineup(sleeper, projector, sub.league_id, sub.owner_id, week, sub.risk)
        swaps_by_sit = {s.sit.player_id: s for s in lineup.swaps if s.sit}

        for pid, status in flagged:
            if not store.mark_sent((sub.league_id, pid, status, week)):
                continue
            swap = swaps_by_sit.get(pid)
            alert = Alert(
                subscription_id=sub.id,
                email=sub.email,
                league_id=sub.league_id,
                player_name=players_db.get(pid, {}).get("full_name") or pid,
                status=status,
                swap_in=swap.start.name if swap else None,
                gain=swap.gain if swap else None,
            )
            await notifier.send(alert.email, "Lineup alert", alert.message())
            sent.append(alert)
    return sent


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    sleeper = SleeperClient()
    try:
        # TODO(M3): load subscriptions from Postgres instead of an empty in-memory store.
        projector = build_projector(sleeper)
        alerts = await run_once(sleeper, projector, SubscriptionStore(), ConsoleNotifier())
        log.info("sent %d alerts", len(alerts))
    finally:
        await sleeper.aclose()


if __name__ == "__main__":
    asyncio.run(main())

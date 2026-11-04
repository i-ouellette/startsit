"""Alert subscription storage.

In-memory for now so the scaffold runs with zero setup. Milestone M3 swaps this
for Postgres (SQLModel/SQLAlchemy) behind the same interface.
"""

from __future__ import annotations

import uuid

from app.models import AlertSubscription, AlertSubscriptionIn


class SubscriptionStore:
    def __init__(self) -> None:
        self._subs: dict[str, AlertSubscription] = {}
        self._sent: set[tuple[str, str, str, int]] = set()  # (league, player, status, week)

    def add(self, sub: AlertSubscriptionIn) -> AlertSubscription:
        created = AlertSubscription(id=uuid.uuid4().hex[:12], **sub.model_dump())
        self._subs[created.id] = created
        return created

    def remove(self, sub_id: str) -> bool:
        return self._subs.pop(sub_id, None) is not None

    def all(self) -> list[AlertSubscription]:
        return list(self._subs.values())

    def mark_sent(self, key: tuple[str, str, str, int]) -> bool:
        """Returns True if this alert is new (and records it), False if already sent."""
        if key in self._sent:
            return False
        self._sent.add(key)
        return True

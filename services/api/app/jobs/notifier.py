from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger(__name__)


class Notifier(Protocol):
    async def send(self, to: str | None, subject: str, body: str) -> None: ...


class ConsoleNotifier:
    """Dev notifier. M3 adds ResendNotifier (email) and WebPushNotifier."""

    def __init__(self) -> None:
        self.outbox: list[tuple[str | None, str, str]] = []

    async def send(self, to: str | None, subject: str, body: str) -> None:
        self.outbox.append((to, subject, body))
        log.info("[alert] to=%s subject=%s body=%s", to, subject, body)

"""Thin, cached client for the public, read-only Sleeper API.

Docs: https://docs.sleeper.com  (no auth; ~1000 req/min soft limit)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import get_settings


class SleeperError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class _TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        hit = self._data.get(key)
        if hit and hit[0] > time.monotonic():
            return hit[1]
        return None

    def set(self, key: str, value: Any, ttl_s: float) -> None:
        self._data[key] = (time.monotonic() + ttl_s, value)

    def clear(self) -> None:
        self._data.clear()


class SleeperClient:
    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        s = get_settings()
        self._base = s.sleeper_base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=s.http_timeout_s)
        self._cache = _TTLCache()
        self._players_ttl = s.players_cache_ttl_s
        self._league_ttl = s.league_cache_ttl_s

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, ttl_s: float | None = None) -> Any:
        key = path
        if ttl_s and (cached := self._cache.get(key)) is not None:
            return cached
        resp = await self._http.get(f"{self._base}{path}")
        if resp.status_code >= 400:
            raise SleeperError(resp.status_code, f"Sleeper {path} -> {resp.status_code}")
        data = resp.json() if resp.content.strip() else None
        if ttl_s and data is not None:
            self._cache.set(key, data, ttl_s)
        return data

    # --- Users & leagues -------------------------------------------------
    async def get_user(self, username_or_id: str) -> dict:
        user = await self._get(f"/user/{username_or_id}", self._league_ttl)
        if not user:  # Sleeper returns `null` for unknown users
            raise SleeperError(404, f"Sleeper user '{username_or_id}' not found")
        return user

    async def get_leagues(self, user_id: str, season: int) -> list[dict]:
        return await self._get(f"/user/{user_id}/leagues/nfl/{season}", self._league_ttl) or []

    async def get_league(self, league_id: str) -> dict:
        return await self._get(f"/league/{league_id}", self._league_ttl)

    async def get_rosters(self, league_id: str) -> list[dict]:
        return await self._get(f"/league/{league_id}/rosters", self._league_ttl) or []

    async def get_league_users(self, league_id: str) -> list[dict]:
        return await self._get(f"/league/{league_id}/users", self._league_ttl) or []

    # --- Global ----------------------------------------------------------
    async def get_state(self) -> dict:
        """Current season/week, e.g. {"season": "2026", "week": 9, ...}."""
        return await self._get("/state/nfl", 300)

    async def get_players(self) -> dict[str, dict]:
        """All NFL players keyed by player_id (large; cached 24h)."""
        return await self._get("/players/nfl", self._players_ttl)

    async def get_week_stats(self, season: int, week: int) -> dict[str, dict]:
        """Per-player weekly stats incl. pts_ppr / pts_half_ppr / pts_std.

        Undocumented but long-standing endpoint; callers must tolerate failure.
        """
        return await self._get(f"/stats/nfl/regular/{season}/{week}", 6 * 60 * 60) or {}

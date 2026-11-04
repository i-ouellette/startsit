from __future__ import annotations

from fastapi import Request

from app.clients.sleeper import SleeperClient
from app.config import get_settings
from app.services.projections import BaselineProjector, ModelProjector, Projector
from app.store import SubscriptionStore


def build_projector(sleeper: SleeperClient) -> Projector:
    s = get_settings()
    baseline = BaselineProjector(sleeper, s.baseline_lookback_weeks)
    if s.projector == "baseline":
        return baseline
    return ModelProjector(s.model_dir, fallback=baseline)


def get_sleeper(request: Request) -> SleeperClient:
    return request.app.state.sleeper


def get_projector(request: Request) -> Projector:
    return request.app.state.projector


def get_store(request: Request) -> SubscriptionStore:
    return request.app.state.store

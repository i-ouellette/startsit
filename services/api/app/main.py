from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.sleeper import SleeperClient
from app.config import get_settings
from app.deps import build_projector
from app.routers import alerts, leagues
from app.store import SubscriptionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sleeper = SleeperClient()
    app.state.projector = build_projector(app.state.sleeper)
    app.state.store = SubscriptionStore()
    yield
    await app.state.sleeper.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="startsit API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(leagues.router)
    app.include_router(alerts.router)

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

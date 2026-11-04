from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STARTSIT_", env_file=".env", extra="ignore")

    sleeper_base_url: str = "https://api.sleeper.app/v1"
    players_cache_ttl_s: int = 24 * 60 * 60  # Sleeper asks: fetch /players/nfl at most once a day
    league_cache_ttl_s: int = 60
    http_timeout_s: float = 15.0

    # Projections
    # "auto": model projections when ml/ has scored the week, baseline otherwise.
    # "baseline": always use the rolling-average baseline.
    projector: str = "auto"
    model_dir: str = str(Path(__file__).resolve().parents[3] / "ml" / "artifacts")
    baseline_lookback_weeks: int = 4

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

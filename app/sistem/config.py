"""Конфигурация Sistem Core."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SISTEM_", extra="ignore")

    env: Literal["dev", "staging", "production", "test"] = "dev"
    debug: bool = False

    # DB / cache
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")

    # Auth
    jwt_private_key: str = Field(..., alias="JWT_PRIVATE_KEY")
    jwt_public_key: str = Field(..., alias="JWT_PUBLIC_KEY")
    jwt_alg: str = "RS256"
    jwt_access_ttl_minutes: int = 30
    jwt_refresh_ttl_days: int = 30

    # Secrets encryption
    secrets_key: str = Field(..., alias="SISTEM_SECRETS_KEY")

    # Observability
    sentry_dsn: str = ""

    # Rate limits
    default_rate_per_minute: int = 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[ca
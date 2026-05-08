"""
Application settings — loaded from .env via pydantic-settings.
All secrets injected at startup, type-validated before first request.
"""
from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Anthropic
    anthropic_api_key: str
    claude_model: str = "claude-sonnet-4-20250514"

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Confidence thresholds
    confidence_auto_send_threshold: float = 0.85
    confidence_escalate_threshold: float = 0.60

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
from __future__ import annotations
from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    anthropic_api_key: str = Field(..., min_length=20)
    claude_model: str = "claude-sonnet-4-20250514"
    claude_max_tokens: int = Field(default=1024, ge=256, le=4096)
    claude_timeout_s: int = Field(default=30, ge=5, le=120)
    claude_max_retries: int = Field(default=2, ge=0, le=5)

    confidence_auto_send_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    confidence_escalate_threshold: float = Field(default=0.60, ge=0.0, le=1.0)

    webhook_secret: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @field_validator("anthropic_api_key")
    @classmethod
    def key_not_placeholder(cls, v: str) -> str:
        if "your-key" in v:
            raise ValueError("ANTHROPIC_API_KEY is still the placeholder. Add your real key to .env")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
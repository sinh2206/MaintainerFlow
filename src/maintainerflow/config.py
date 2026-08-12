from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MAINTAINERFLOW_",
        extra="ignore",
    )

    environment: str = "production"
    log_level: str = "INFO"
    github_app_id: int = Field(gt=0)
    github_webhook_secret: SecretStr = Field(min_length=16)
    github_private_key: SecretStr | None = None
    github_api_url: str = "https://api.github.com"
    github_api_version: str = "2026-03-10"
    database_url: str
    redis_url: str
    delivery_lease_seconds: int = Field(default=60, ge=10, le=3600)
    recovery_interval_seconds: int = Field(default=30, ge=5, le=3600)
    recovery_batch_size: int = Field(default=100, ge=1, le=1000)
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    ai_enabled: bool = False
    ai_timeout_seconds: float = Field(default=30, gt=0, le=300)
    analysis_store_diff: bool = False
    analysis_max_diff_bytes: int = Field(default=1_000_000, ge=10_000, le=10_000_000)
    workflow_enabled: bool = False
    check_publish_enabled: bool = False
    check_mode: Literal["shadow", "suggestion"] = "shadow"
    outbox_lease_seconds: int = Field(default=60, ge=10, le=3600)
    outbox_batch_size: int = Field(default=20, ge=1, le=100)
    outbox_max_attempts: int = Field(default=5, ge=1, le=20)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith(("postgresql+asyncpg://", "sqlite+aiosqlite://")):
            raise ValueError("database_url must use asyncpg or aiosqlite")
        return value

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        if not value.startswith(("redis://", "rediss://")):
            raise ValueError("redis_url must use redis:// or rediss://")
        return value

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        if not value.startswith("gemini-"):
            raise ValueError("gemini_model must be a Gemini model ID")
        return value

    @model_validator(mode="after")
    def validate_ai_credentials(self) -> Self:
        if self.ai_enabled and self.gemini_api_key is None:
            raise ValueError("gemini_api_key is required when ai_enabled=true")
        if self.workflow_enabled and self.github_private_key is None:
            raise ValueError("github_private_key is required when workflow_enabled=true")
        if self.check_publish_enabled and not self.workflow_enabled:
            raise ValueError("workflow_enabled must be true when check publishing is enabled")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

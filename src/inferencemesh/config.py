"""Runtime configuration with explicit, validated resource bounds."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed gateway configuration."""

    model_config = SettingsConfigDict(
        env_prefix="INFERENCEMESH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"
    require_api_key: bool = False
    api_key: str = "local-dev-key"
    max_concurrent_requests: int = Field(default=32, ge=1, le=10_000)
    max_concurrent_per_tenant: int = Field(default=4, ge=1, le=1_000)
    max_queue_depth: int = Field(default=64, ge=1, le=100_000)
    queue_wait_ms: int = Field(default=250, ge=1, le=60_000)
    max_input_chars: int = Field(default=20_000, ge=1, le=1_000_000)
    max_output_tokens: int = Field(default=512, ge=1, le=32_768)
    fake_token_delay_ms: int = Field(default=5, ge=0, le=5_000)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings snapshot."""

    return Settings()

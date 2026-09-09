"""Validated local/demo and real HTTP model registry configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from inferencemesh.domain import Task


class BackendConfig(BaseModel):
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    public_model: str = Field(min_length=1)
    upstream_model: str = Field(min_length=1)
    base_url: str = Field(pattern=r"^https?://")
    api_key: str = ""
    tasks: list[Task] = Field(default_factory=lambda: [Task.CHAT], min_length=1)
    capacity: int = Field(default=4, ge=1)
    timeout_seconds: float = Field(default=120, gt=0, le=600)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INFERENCEMESH_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    environment: str = "development"
    log_level: str = "INFO"
    backend_mode: Literal["demo", "http"] = "demo"
    backends: list[BackendConfig] = Field(default_factory=list)
    require_api_key: bool = False
    api_key: str = "local-dev-key"
    metrics_api_key: str = ""
    requests_per_minute: int = Field(default=60, ge=1)
    output_tokens_per_minute: int = Field(default=8192, ge=1)
    health_interval_seconds: float = Field(default=5, ge=0)
    circuit_failure_threshold: int = Field(default=2, ge=1)
    circuit_cooldown_seconds: float = Field(default=5, gt=0)
    max_concurrent_requests: int = Field(default=32, ge=1, le=10000)
    max_concurrent_per_tenant: int = Field(default=4, ge=1, le=1000)
    max_queue_depth: int = Field(default=64, ge=0, le=100000)
    queue_wait_ms: int = Field(default=250, ge=1, le=60000)
    max_input_chars: int = Field(default=20000, ge=1, le=1000000)
    max_output_tokens: int = Field(default=512, ge=1, le=32768)
    fake_token_delay_ms: int = Field(default=5, ge=0, le=5000)

    @model_validator(mode="after")
    def validate_registry(self) -> "Settings":
        if self.backend_mode == "http" and not self.backends:
            raise ValueError("HTTP mode requires at least one configured backend")
        if len({backend.name for backend in self.backends}) != len(self.backends):
            raise ValueError("backend names must be unique")
        if self.environment == "public-demo" and (
            not self.require_api_key or self.api_key == "local-dev-key"
        ):
            raise ValueError("public-demo requires a non-default API key")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

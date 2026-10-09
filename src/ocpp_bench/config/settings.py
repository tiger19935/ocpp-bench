from __future__ import annotations

from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Protocol(StrEnum):
    V16 = "1.6"
    V201 = "2.0.1"
    BOTH = "both"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OCPP_BENCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    host: str = "0.0.0.0"
    port: int = Field(default=9000, ge=1, le=65535)
    admin_port: int = Field(default=9100, ge=1, le=65535)
    protocol: Protocol = Protocol.BOTH

    log_level: str = "info"
    log_json: bool = True

    inbound_queue_depth: int = Field(default=128, ge=1)
    call_timeout_sec: float = Field(default=30.0, gt=0)

    flap_window_sec: float = Field(default=60.0, gt=0)
    flap_limit: int = Field(default=5, ge=1)
    quarantine_clear_sec: float = Field(default=300.0, gt=0)

    duplicate_start_window_sec: float = Field(default=10.0, gt=0)

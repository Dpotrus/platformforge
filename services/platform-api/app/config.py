from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PlatformForge API"

    environment: str = "development"

    # gRPC server
    grpc_host: str = "127.0.0.1"
    grpc_port: int = Field(default=50051, ge=1, le=65535)

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    database_url: str = Field(
        min_length=1,
        pattern=r"^postgresql\+psycopg://",
    )

    # OpenTelemetry tracing
    otel_tracing_enabled: bool = False
    otel_service_name: str = "platformforge-api"
    otel_grpc_service_name: str = "platformforge-grpc"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
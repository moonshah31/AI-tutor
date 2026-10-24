from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded exclusively from the server environment."""

    app_env: str = "development"
    log_level: str = "INFO"

    mongodb_uri: str
    mongodb_database: str = "ai_tutor"

    cors_origins: str = "http://localhost:5173"

    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"

    document_storage_path: str = "./storage/documents"
    max_document_size_mb: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
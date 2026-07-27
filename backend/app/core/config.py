from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Auth0
    AUTH0_DOMAIN: str
    AUTH0_API_AUDIENCE: str
    AUTH0_ALGORITHMS: str = "RS256"

    # Anthropic
    ANTHROPIC_API_KEY: str

    # Voyage AI
    VOYAGE_API_KEY: str

    # Qdrant
    QDRANT_URL: str
    QDRANT_API_KEY: str

    # AWS S3
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_S3_BUCKET: str = "lilyai-documents"
    AWS_REGION: str = "eu-west-1"

    # Fernet encryption
    FERNET_KEY: str

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # CORS — comma-separated list of allowed frontend origins
    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()

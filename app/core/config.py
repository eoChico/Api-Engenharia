from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: Literal["dev", "prod"] = "dev"
    PROJECT_NAME: str = "api-eng"
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "api-eng"
    JWT_AUDIENCE: str = "api-eng-clients"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Refresh token (sessão do turno)
    REFRESH_TOKEN_EXPIRE_HOURS: int = 12       # janela deslizante
    REFRESH_ABSOLUTE_LIFETIME_DAYS: int = 7    # teto: depois disso, login de novo
    REFRESH_REUSE_GRACE_SECONDS: int = 10      # tolerância a refresh concorrente

    # Proteção contra força bruta
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15
    LOGIN_RATE_LIMIT: str = "10/minute"        # por IP
    REFRESH_RATE_LIMIT: str = "30/minute"
    RATE_LIMIT_STORAGE_URI: str = "memory://"  # em produção com vários workers: redis://...

    CORS_ORIGINS: list[str] = []
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]

    @model_validator(mode="after")
    def validate_security(self):
        if len(self.SECRET_KEY) < 32 or self.SECRET_KEY.startswith("troque"):
            raise ValueError(
                "SECRET_KEY fraca. Gere com: python -c "
                "\"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if "*" in self.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS não pode conter '*'")
        return self

settings = Settings()  # pyright: ignore[reportCallIssue]

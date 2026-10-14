from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://arctic:arctic@127.0.0.1:5432/arctic"
    jwt_secret: str = "development-only-change-this-secret-before-deploying"
    access_token_minutes: int = 30
    refresh_token_days: int = 14
    public_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    )
    uploads_dir: Path = Path("storage/uploads")
    max_upload_mb: int = 30
    certificate_font_path: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@example.com"
    smtp_starttls: bool = True
    enable_email_delivery: bool = False
    gigachat_credentials: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-2-Max"
    gigachat_ca_bundle: str = ""
    rate_limit_per_minute: int = 120
    auth_rate_limit_per_minute: int = 20

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            value = value.replace("postgresql://", "postgresql+psycopg://", 1)
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("Only PostgreSQL with psycopg is supported")
        return value

    @model_validator(mode="after")
    def production_secret(self):
        if self.environment == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("development-"):
                raise ValueError("Set a random JWT_SECRET of at least 32 characters in production")
            if "*" in self.cors_origins:
                raise ValueError("Use explicit CORS origins in production")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

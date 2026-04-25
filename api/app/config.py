"""Runtime configuration. Pulled from env at startup."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── DB ──────────────────────────────────────────────────────
    postgres_host: str = "timescaledb"
    postgres_port: int = 5432
    postgres_db: str = "oura"
    postgres_user: str = "oura"
    postgres_password: str = ""

    # ── Auth ────────────────────────────────────────────────────
    # Single-user app: a shared passcode mints a JWT good for 30 days.
    app_passcode: str = "change-me"
    jwt_secret: str = "change-me-too"
    jwt_ttl_days: int = 30

    # ── LLM ─────────────────────────────────────────────────────
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # ── CORS ────────────────────────────────────────────────────
    # Set to your app's public URL on Railway, e.g.
    # https://oura-app-production.up.railway.app
    cors_origin: str = "*"

    # ── Misc ────────────────────────────────────────────────────
    user_name: str = "you"
    user_age: int = 0
    user_timezone: str = "Asia/Kolkata"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def dsn(self) -> str:
        return (
            f"host={self.postgres_host} "
            f"port={self.postgres_port} "
            f"dbname={self.postgres_db} "
            f"user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


@lru_cache
def settings() -> Settings:
    return Settings()

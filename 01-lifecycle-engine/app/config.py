from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    stripe_webhook_secret: str = ""
    signature_tolerance_seconds: int = 300
    max_attempts: int = 5
    admin_token: str = ""
    # Real integrations; leave empty to use the logging no-ops.
    hubspot_token: str = ""
    access_api_base: str = ""
    access_api_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Google Gemini API Configuration
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings loaded from environment/.env.

    Use refresh_settings() to clear the cache if the environment changes at runtime.
    """
    return Settings()


def refresh_settings() -> None:
    """Clear cached settings so the next get_settings() reloads from env/.env."""
    get_settings.cache_clear()

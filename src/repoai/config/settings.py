from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Keys / model chouices
    # Google Gemini
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # AIMLAPI (OpenAI-compatible)
    AIMLAPI_API_KEY: str = ""
    AIMLAPI_BASE_URL: str = "https://api.aimlapi.com/v1"
    AIMLAPI_MODEL: str = "gpt-4o-mini"


settings = Settings()

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from repoai.config.settings import settings


def make_gemini_agent() -> Agent:
    google_provider = GoogleProvider(api_key=settings.GOOGLE_API_KEY)
    google_model = GoogleModel(model_name=settings.GEMINI_MODEL, provider=google_provider)
    agent = Agent(model=google_model)
    return agent

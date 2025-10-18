from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.litellm import LiteLLMProvider

from repoai.config.settings import settings


def make_aimlapi_agent() -> Agent:
    if not settings.AIMLAPI_API_KEY:
        raise RuntimeError("AIMLAPI_API_KEY is not set in settings.")

    aimlapi_provider = LiteLLMProvider(
        api_base=settings.AIMLAPI_BASE_URL, api_key=settings.AIMLAPI_API_KEY
    )
    aimlapi_model = OpenAIChatModel(settings.AIMLAPI_MODEL, provider=aimlapi_provider)
    agent = Agent(model=aimlapi_model)
    return agent

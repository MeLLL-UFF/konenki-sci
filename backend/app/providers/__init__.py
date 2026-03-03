from app.config import get_settings
from app.providers.provider_api import APIProvider
from app.providers.provider_local import LocalProvider
from app.providers.base import LLMProvider

def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "local":
        return LocalProvider()
    return APIProvider()
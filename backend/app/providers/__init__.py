from typing import Optional
from app.config import get_settings
from app.providers.provider_api import APIProvider
from app.providers.provider_local import LocalProvider
from app.providers.base import LLMProvider


def get_llm_provider(model: Optional[str] = None) -> LLMProvider:
    """
    Retorna o provider LLM adequado.

    - model: nome do modelo a usar (ex: "claude-haiku-4-20250514", "gpt-4o-mini").
             Se None, usa o padrão definido em llm_api_model / ollama_model do .env.

    O tipo de provider (api vs local) continua sendo controlado por LLM_PROVIDER no .env.
    """
    settings = get_settings()
    if settings.llm_provider == "local":
        return LocalProvider(model=model)
    return APIProvider(model=model)

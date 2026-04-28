from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # ── Provider switches ────────────────────────────────
    llm_provider: str = "local"      # "api" | "local"
    # emb_provider: str = "api"      # "api" | "local"  (reservado para Fase 2)

    # ── API provider credentials ─────────────────────────
    anthropic_api_key: str = ""
    openai_api_key:    str = ""
    gemini_api_key:    str = ""
    llm_api_model:     str = "mitral-7b"              # use sabiá se disponível; caso contrário, mantenha o provider padrão

    # ── Local provider (Ollama / vLLM) ───────────────────
    ollama_base_url:   str = "http://localhost:11434"
    ollama_model:      str = "mitral-7b"             # troque para "sabiá" se seu provider usar acento
    vllm_base_url:     str = "http://localhost:8000"
    vllm_model:        str = "sabia-7b"          # ajustar para seu modelo local

    # ── Dataset ────────────────────────────────────────────
    dataset_max_results: int = 6
    enable_dataset: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()
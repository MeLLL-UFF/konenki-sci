from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # ── Provider switches ────────────────────────────────
    llm_provider: str = "local"      # "api" | "local"
    emb_provider: str = "api"      # "api" | "local"  (reservado para Fase 2)

    # ── API provider credentials ─────────────────────────
    anthropic_api_key: str = ""
    openai_api_key:    str = ""
    gemini_api_key:    str = ""
    maritaca_api_key:  str = ""
    llm_api_model:     str = "claude-sonnet-4-20250514"  # troque conforme o provider

    # ── Local provider (Ollama / vLLM) ───────────────────
    ollama_base_url:   str = "http://localhost:11434"
    ollama_model:      str = "llama3.2"
    vllm_base_url:     str = "http://localhost:8000"
    vllm_model:        str = "mistral-7b-instruct"

    # ── PubMed ────────────────────────────────────────────
    pubmed_max_results: int = 6

    # ── News API ──────────────────────────────────────────
    news_api_key: str = ""

    # ── Notion (newsletter CMS) ───────────────────────────
    notion_api_key:      str = ""
    notion_database_id:  str = ""

    # ── Database ───────────────────────────────────────
    db_host:     str = ""
    db_port:     int = 5432
    db_name:     str = ""
    db_user:     str = ""
    db_password: str = ""

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
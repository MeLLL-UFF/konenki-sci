import httpx
from typing import Optional
from app.providers.base import LLMProvider
from app.config import get_settings

settings = get_settings()


class LocalProvider(LLMProvider):
    """
    Modelos locais via Ollama ou vLLM (OpenAI-compatible).

    O modelo pode ser definido por instância (construtor) ou
    cai para os valores de OLLAMA_MODEL / VLLM_MODEL do .env.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model  # None = usa o padrão do settings

    async def complete(self, system: str, user: str) -> str:
        # Tenta Ollama primeiro; fallback para vLLM
        try:
            return await self._ollama(system, user)
        except Exception:
            return await self._vllm(system, user)

    async def _ollama(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": self.model or settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["message"]["content"]

    async def _vllm(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.vllm_base_url}/v1/chat/completions",
                json={
                    "model": self.model or settings.vllm_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

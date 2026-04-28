import httpx
from app.providers.base import LLMProvider
from app.config import get_settings

settings = get_settings()

class LocalProvider(LLMProvider):
    """
    Fase 2/3 — modelos locais via Ollama ou vLLM.
    Usa a variável OLLAMA_BASE_URL / VLLM_BASE_URL para conectar.
    """

    async def complete(self, system: str, user: str) -> str:
        # Tenta Ollama primeiro; fallback para vLLM (OpenAI-compatible)
        try:
            return await self._ollama(system, user)
        except Exception:
            return await self._vllm(system, user)

    async def _ollama(self, system: str, user: str) -> str:
        print(f"[OLLAMA] Chamando Ollama em {settings.ollama_base_url}/api/chat com modelo {settings.ollama_model}")
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                },
            )
            print(f"[OLLAMA] Status da resposta: {r.status_code}")
            r.raise_for_status()
            response_json = r.json()

            # Compatibilidade com formatos de resposta Ollama / modelos locais.
            content = ""
            if isinstance(response_json, dict):
                # Ollama 1.x/2.x: { "message": { "content": "..." } }
                message = response_json.get("message")
                if isinstance(message, dict):
                    content = message.get("content", "")
                # Possível fallback: { "choices": [{ "message": { "content": "..." }}] }
                if not content:
                    choices = response_json.get("choices")
                    if isinstance(choices, list) and choices:
                        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
                        if isinstance(msg, dict):
                            content = msg.get("content", "")

            if not isinstance(content, str):
                content = str(content)

            print(f"[OLLAMA] Comprimento do conteúdo da resposta: {len(content)}")
            return content

    async def _vllm(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{settings.vllm_base_url}/v1/chat/completions",
                json={
                    "model": settings.vllm_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
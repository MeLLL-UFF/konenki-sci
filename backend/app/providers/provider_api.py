import httpx
from app.providers.base import LLMProvider
from app.config import get_settings

settings = get_settings()

class APIProvider(LLMProvider):
    """
    Fase 1 — provedores de API cloud.
    Detecta automaticamente qual chave está configurada.
    Ordem de prioridade: Anthropic → OpenAI → Gemini
    """

    async def complete(self, system: str, user: str) -> str:
        if settings.anthropic_api_key:
            return await self._anthropic(system, user)
        if settings.openai_api_key:
            return await self._openai(system, user)
        if settings.gemini_api_key:
            return await self._gemini(system, user)
        raise ValueError("Nenhuma chave de API configurada. Defina ANTHROPIC_API_KEY, OPENAI_API_KEY ou GEMINI_API_KEY no .env")

    # ── Anthropic ────────────────────────────────────────
    async def _anthropic(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.llm_api_model,
                    "max_tokens": 1024,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            blocks = r.json().get("content", [])
            return "".join(b.get("text", "") for b in blocks)

    # ── OpenAI ───────────────────────────────────────────
    async def _openai(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.llm_api_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    # ── Google Gemini ────────────────────────────────────
    async def _gemini(self, system: str, user: str) -> str:
        model = settings.llm_api_model or "gemini-1.5-flash"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={settings.gemini_api_key}"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
            })
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
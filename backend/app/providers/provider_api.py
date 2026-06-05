import httpx
from typing import Optional
from app.providers.base import LLMProvider
from app.config import get_settings

settings = get_settings()


class APIProvider(LLMProvider):
    """
    Provedores de API cloud: Anthropic, OpenAI, Maritaca (Sabiá) e Google Gemini.

    O modelo pode ser definido:
      1. Por instância — passado no construtor (prioridade máxima).
      2. Via settings.llm_api_model — padrão global do .env.

    O provider é detectado automaticamente pelo prefixo do nome do modelo:
      claude-*  → Anthropic
      gpt-*     → OpenAI
      sabia-*/sabiá-* → Maritaca
      gemini-*  → Google Gemini
    """

    def __init__(self, model: Optional[str] = None):
        # Usa o modelo passado explicitamente ou cai para o padrão global
        self.model = model or settings.llm_api_model

    async def complete(self, system: str, user: str) -> str:
        m = self.model or ""

        if m.startswith("claude") and settings.anthropic_api_key:
            return await self._anthropic(system, user)
        if m.startswith(("sabia", "sabiá")) and settings.maritaca_api_key:
            return await self._maritaca(system, user)
        if m.startswith("gemini") and settings.gemini_api_key:
            return await self._gemini(system, user)
        if m.startswith("gpt") and settings.openai_api_key:
            return await self._openai(system, user)

        # Fallback: primeira chave disponível
        if settings.anthropic_api_key:
            return await self._anthropic(system, user)
        if settings.maritaca_api_key:
            return await self._maritaca(system, user)
        if settings.gemini_api_key:
            return await self._gemini(system, user)
        if settings.openai_api_key:
            return await self._openai(system, user)

        raise ValueError(
            "Nenhuma chave de API configurada. "
            "Defina ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY ou MARITACA_API_KEY no .env"
        )

    # ── Anthropic ─────────────────────────────────────────────────────────────
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
                    "model": self.model,
                    "max_tokens": 1024,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            blocks = r.json().get("content", [])
            return "".join(b.get("text", "") for b in blocks)

    # ── OpenAI ────────────────────────────────────────────────────────────────
    async def _openai(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    # ── Maritaca (Sabiá) ──────────────────────────────────────────────────────
    async def _maritaca(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://chat.maritaca.ai/api/chat/completions",
                headers={"Authorization": f"Key {settings.maritaca_api_key}"},
                json={
                    "model": self.model or "sabia-3",
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    # ── Google Gemini ─────────────────────────────────────────────────────────
    async def _gemini(self, system: str, user: str) -> str:
        model = self.model or "gemini-1.5-flash"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={settings.gemini_api_key}"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
            })
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

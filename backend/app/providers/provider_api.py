import httpx
from typing import Optional
from app.providers.base import LLMProvider
from app.config import get_settings


class APIProvider(LLMProvider):
    """
    Provedores de API cloud: Anthropic, OpenAI, Maritaca (Sabiá) e Google Gemini.

    O modelo pode ser definido:
      1. Por instância — passado no construtor (prioridade máxima).
      2. Via settings.llm_api_model — padrão global do .env.

    A chave de API segue a mesma ordem: quando `api_key` é passada no construtor,
    ela vale só para esta instância (usada pelo modo desenvolvedor, em que a chave
    chega por requisição e nunca vira estado global do servidor). Sem ela, caímos
    nas chaves do .env.

    O provider é detectado automaticamente pelo prefixo do nome do modelo:
      claude-*  → Anthropic
      gpt-*     → OpenAI
      sabia-*/sabiá-* → Maritaca
      gemini-*  → Google Gemini
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        settings = get_settings()
        # Usa o modelo passado explicitamente ou cai para o padrão global
        self.model = model or settings.llm_api_model
        # Chave por instância: vence as do .env quando presente
        self.api_key = (api_key or "").strip() or None
        self._settings = settings

    # ── Resolução de chave ────────────────────────────────────────────────────
    def _key_for(self, vendor: str) -> str:
        """Chave da instância (modo dev) ou a do .env para aquele vendor."""
        if self.api_key:
            return self.api_key
        return {
            "anthropic": self._settings.anthropic_api_key,
            "openai":    self._settings.openai_api_key,
            "gemini":    self._settings.gemini_api_key,
            "maritaca":  self._settings.maritaca_api_key,
        }.get(vendor, "")

    def _has_key(self, vendor: str) -> bool:
        return bool(self._key_for(vendor))

    async def complete(self, system: str, user: str) -> str:
        m = self.model or ""

        if m.startswith("claude") and self._has_key("anthropic"):
            return await self._anthropic(system, user)
        if m.startswith(("sabia", "sabiá")) and self._has_key("maritaca"):
            return await self._maritaca(system, user)
        if m.startswith("gemini") and self._has_key("gemini"):
            return await self._gemini(system, user)
        if m.startswith("gpt") and self._has_key("openai"):
            return await self._openai(system, user)

        # Uma chave por instância só faz sentido com o modelo que a acompanha;
        # cair para outro vendor aqui usaria a chave errada no endpoint errado.
        if self.api_key:
            raise ValueError(
                f"Modelo {m!r} não reconhecido. Use um nome começando com "
                "'claude', 'gpt', 'gemini' ou 'sabia'."
            )

        # Fallback: primeira chave disponível no .env
        if self._settings.anthropic_api_key:
            return await self._anthropic(system, user)
        if self._settings.maritaca_api_key:
            return await self._maritaca(system, user)
        if self._settings.gemini_api_key:
            return await self._gemini(system, user)
        if self._settings.openai_api_key:
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
                    "x-api-key": self._key_for("anthropic"),
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
                headers={"Authorization": f"Bearer {self._key_for('openai')}"},
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
                headers={"Authorization": f"Key {self._key_for('maritaca')}"},
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
            f"{model}:generateContent?key={self._key_for('gemini')}"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
            })
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

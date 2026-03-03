from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """Interface comum para todos os provedores de LLM."""

    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        """Retorna a resposta textual do modelo."""
        ...
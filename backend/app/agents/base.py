from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable

# Callback para emitir eventos de progresso ao frontend (SSE)
StepCallback = Optional[Callable[[str], Awaitable[None]]]


@dataclass
class AgentResult:
    """Resultado padronizado retornado por qualquer agente."""
    success: bool
    output: str                        # texto principal do resultado
    metadata: dict = field(default_factory=dict)  # dados extras (query, artigos, etc.)


class BaseAgent(ABC):
    """Interface base que todos os agentes devem implementar."""

    def __init__(self, on_step: StepCallback = None):
        self.on_step = on_step

    async def _step(self, msg: str):
        """Emite uma mensagem de progresso se houver callback registrado."""
        if self.on_step:
            await self.on_step(msg)

    @abstractmethod
    async def run(self, **kwargs) -> AgentResult:
        """Executa o agente e retorna um AgentResult."""
        ...

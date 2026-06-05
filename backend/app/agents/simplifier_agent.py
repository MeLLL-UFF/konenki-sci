"""
SimplifierAgent
---------------
Recebe uma resposta científica e a reescreve em linguagem simples
e acessível, como se explicasse para uma amiga leiga.

Ativado apenas quando a usuária solicita linguagem simplificada
(plain_language=True). Caso contrário, o Orchestrator ignora este agente.
"""

from typing import Optional
from app.agents.base import BaseAgent, AgentResult, StepCallback
from app.providers import get_llm_provider
from app.config import get_settings

_SYSTEM_PROMPT = (
    "Você é uma comunicadora de saúde empática e acolhedora. "
    "Receba um texto científico sobre menopausa e reescreva-o em linguagem simples e acessível, "
    "como se estivesse explicando para uma amiga sem formação médica. "
    "Siga estas diretrizes:\n"
    "- Use frases curtas e parágrafos pequenos.\n"
    "- Substitua termos técnicos por palavras do dia a dia (explique entre parênteses quando necessário).\n"
    "- Mantenha um tom caloroso, encorajador e sem alarmismo.\n"
    "- Preserve todas as informações importantes e as referências aos estudos.\n"
    "- Responda sempre em português do Brasil.\n"
    "- Não invente informações novas."
)


class SimplifierAgent(BaseAgent):
    """Agente de simplificação: adapta a linguagem científica para o público leigo."""

    def __init__(self, on_step: StepCallback = None, model: Optional[str] = None):
        super().__init__(on_step)
        resolved = model or get_settings().simplifier_model or None
        self.llm = get_llm_provider(model=resolved)

    async def run(self, scientific_answer: str) -> AgentResult:
        await self._step("Adaptando resposta para linguagem acessível…")

        simplified = await self.llm.complete(
            system=_SYSTEM_PROMPT,
            user=f"Texto científico para simplificar:\n\n{scientific_answer}",
        )

        return AgentResult(success=True, output=simplified)

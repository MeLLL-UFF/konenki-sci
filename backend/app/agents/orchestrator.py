"""
OrchestratorAgent
-----------------
Agente controlador: coordena o fluxo completo de uma pergunta.

Fluxo:
  1. GuardrailAgent  → valida escopo e adequação
       └─ bloqueado? → retorna mensagem de fora do escopo (sem chamar PubMed)
  2. RetrievalAgent  → busca PubMed + síntese científica
       └─ sem artigos? → retorna mensagem de erro amigável
  3. SimplifierAgent → (somente se plain_language=True)
                        reescreve a resposta em linguagem acessível
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Awaitable

from app.agents.base import StepCallback
from app.agents.guardrail_agent import GuardrailAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.simplifier_agent import SimplifierAgent
from app.services.pubmed import Article


@dataclass
class OrchestratorResult:
    answer: str
    pubmed_query: str
    articles: List[Article] = field(default_factory=list)
    blocked: bool = False          # True se o Guardrail bloqueou a pergunta
    plain_language: bool = False   # True se o Simplifier foi aplicado


class OrchestratorAgent:
    """Coordena todos os agentes e retorna o resultado final."""

    def __init__(self, on_step: StepCallback = None):
        self.on_step = on_step

    async def run(
        self,
        question: str,
        plain_language: bool = False,
    ) -> OrchestratorResult:

        # ── 1. Guardrail ──────────────────────────────────────────────────────
        guardrail = GuardrailAgent(on_step=self.on_step)
        guard_result = await guardrail.run(question=question)

        if not guard_result.success:
            return OrchestratorResult(
                answer=guard_result.output,
                pubmed_query="",
                articles=[],
                blocked=True,
            )

        # ── 2. Retrieval ──────────────────────────────────────────────────────
        retrieval = RetrievalAgent(on_step=self.on_step)
        ret_result = await retrieval.run(question=question)

        if not ret_result.success:
            return OrchestratorResult(
                answer=ret_result.output,
                pubmed_query=ret_result.metadata.get("pubmed_query", ""),
                articles=[],
            )

        answer = ret_result.output
        articles: List[Article] = ret_result.metadata.get("articles", [])
        pubmed_query: str = ret_result.metadata.get("pubmed_query", "")

        # ── 3. Simplifier (opcional) ──────────────────────────────────────────
        if plain_language:
            simplifier = SimplifierAgent(on_step=self.on_step)
            simp_result = await simplifier.run(scientific_answer=answer)
            if simp_result.success:
                answer = simp_result.output

        return OrchestratorResult(
            answer=answer,
            pubmed_query=pubmed_query,
            articles=articles,
            plain_language=plain_language,
        )

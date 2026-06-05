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
from app.config import get_settings


@dataclass
class OrchestratorResult:
    answer: str
    pubmed_query: str
    articles: List[Article] = field(default_factory=list)
    blocked: bool = False          # True se o Guardrail bloqueou a pergunta
    plain_language: bool = False   # True se o Simplifier foi aplicado


class OrchestratorAgent:
    """
    Coordena todos os agentes e retorna o resultado final.

    Os modelos de cada agente podem ser sobrescritos via parâmetros do construtor.
    Quando omitidos, cada agente usa a variável correspondente do .env
    (GUARDRAIL_MODEL, RETRIEVAL_MODEL, SIMPLIFIER_MODEL) ou cai para LLM_API_MODEL.
    """

    def __init__(
        self,
        on_step: StepCallback = None,
        guardrail_model: Optional[str] = None,
        retrieval_model: Optional[str] = None,
        simplifier_model: Optional[str] = None,
    ):
        self.on_step = on_step
        settings = get_settings()
        # Prioridade: argumento > .env por agente > padrão global
        self.guardrail_model  = guardrail_model  or settings.guardrail_model  or None
        self.retrieval_model  = retrieval_model  or settings.retrieval_model  or None
        self.simplifier_model = simplifier_model or settings.simplifier_model or None

    async def run(
        self,
        question: str,
        plain_language: bool = False,
    ) -> OrchestratorResult:

        # ── 1. Guardrail ──────────────────────────────────────────────────────
        guardrail = GuardrailAgent(on_step=self.on_step, model=self.guardrail_model)
        guard_result = await guardrail.run(question=question)

        if not guard_result.success:
            return OrchestratorResult(
                answer=guard_result.output,
                pubmed_query="",
                articles=[],
                blocked=True,
            )

        # ── 2. Retrieval ──────────────────────────────────────────────────────
        retrieval = RetrievalAgent(on_step=self.on_step, model=self.retrieval_model)
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
            simplifier = SimplifierAgent(on_step=self.on_step, model=self.simplifier_model)
            simp_result = await simplifier.run(scientific_answer=answer)
            if simp_result.success:
                answer = simp_result.output

        return OrchestratorResult(
            answer=answer,
            pubmed_query=pubmed_query,
            articles=articles,
            plain_language=plain_language,
        )

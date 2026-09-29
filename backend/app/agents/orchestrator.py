"""
OrchestratorAgent
-----------------
Agente controlador: coordena o fluxo completo de uma pergunta.

Fluxo:
  0. Memória      → recupera o contexto da sessão (resumo + turnos recentes)
  1. GuardrailAgent  → valida escopo e adequação
       └─ bloqueado? → retorna mensagem de fora do escopo (sem chamar PubMed)
  2. RetrievalAgent  → busca PubMed + síntese científica
       └─ sem artigos? → retorna mensagem de erro amigável
  3. SimplifierAgent → (somente se plain_language=True)
                        reescreve a resposta em linguagem acessível
  4. Memória      → grava o turno e recomprime o resumo se necessário

O contexto da conversa (etapas 0 e 4) é o que faz perguntas seguidas serem lidas
como uma conversa só. Ele é injetado no Guardrail e no Retrieval; o Simplifier
fica de fora porque só reescreve o texto que já recebeu.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Awaitable

from app.agents.base import StepCallback
from app.agents.guardrail_agent import GuardrailAgent
from app.agents.retrieval_agent import RetrievalAgent
from app.agents.simplifier_agent import SimplifierAgent
from app.agents.summarizer_agent import SummarizerAgent
from app.services.pubmed import Article
from app.services import conversation as convo
from app.config import get_settings


@dataclass
class OrchestratorResult:
    answer: str
    pubmed_query: str
    articles: List[Article] = field(default_factory=list)
    blocked: bool = False          # True se o Guardrail bloqueou a pergunta
    plain_language: bool = False   # True se o Simplifier foi aplicado
    session_id: str = ""           # sessão a que este turno pertence


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
        summarizer_model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.on_step = on_step
        settings = get_settings()
        # Prioridade: argumento > .env por agente > padrão global
        self.guardrail_model  = guardrail_model  or settings.guardrail_model  or None
        self.retrieval_model  = retrieval_model  or settings.retrieval_model  or None
        self.simplifier_model = simplifier_model or settings.simplifier_model or None
        # Resumir é tarefa leve: reaproveita o modelo barato da triagem quando
        # SUMMARIZER_MODEL não está definido.
        self.summarizer_model = (
            summarizer_model or settings.summarizer_model or settings.guardrail_model or None
        )
        # Chave do modo desenvolvedor: vale só para esta requisição.
        # Com ela, todos os agentes usam o mesmo modelo — os *_model do .env
        # apontam para outro vendor e não funcionariam com esta chave.
        self.api_key = api_key or None
        if self.api_key:
            self.guardrail_model = self.retrieval_model = self.simplifier_model = (
                self.summarizer_model
            ) = (
                guardrail_model or retrieval_model or simplifier_model or summarizer_model
            )

    async def run(
        self,
        question: str,
        plain_language: bool = False,
        session_id: Optional[str] = None,
    ) -> OrchestratorResult:

        # ── 0. Memória da conversa ────────────────────────────────────────────
        # Um session_id ausente ou desconhecido abre uma conversa nova, então o
        # chat nunca quebra por causa de sessão expirada — só perde a memória.
        conv = convo.get_conversation(session_id)
        context = conv.as_context()

        # ── 1. Guardrail ──────────────────────────────────────────────────────
        guardrail = GuardrailAgent(on_step=self.on_step, model=self.guardrail_model, api_key=self.api_key)
        guard_result = await guardrail.run(question=question, context=context)

        if not guard_result.success:
            # Pergunta bloqueada não entra na memória: registrá-la poluiria o
            # resumo com um tema fora de escopo.
            return OrchestratorResult(
                answer=guard_result.output,
                pubmed_query="",
                articles=[],
                blocked=True,
                session_id=conv.session_id,
            )

        # ── 2. Retrieval ──────────────────────────────────────────────────────
        retrieval = RetrievalAgent(on_step=self.on_step, model=self.retrieval_model, api_key=self.api_key)
        ret_result = await retrieval.run(question=question, context=context)

        if not ret_result.success:
            return OrchestratorResult(
                answer=ret_result.output,
                pubmed_query=ret_result.metadata.get("pubmed_query", ""),
                articles=[],
                session_id=conv.session_id,
            )

        answer = ret_result.output
        articles: List[Article] = ret_result.metadata.get("articles", [])
        pubmed_query: str = ret_result.metadata.get("pubmed_query", "")

        # ── 3. Simplifier (opcional) ──────────────────────────────────────────
        if plain_language:
            simplifier = SimplifierAgent(on_step=self.on_step, model=self.simplifier_model, api_key=self.api_key)
            simp_result = await simplifier.run(scientific_answer=answer)
            if simp_result.success:
                answer = simp_result.output

        # ── 4. Grava o turno e recomprime a memória ───────────────────────────
        await self._remember(conv, question, answer)

        return OrchestratorResult(
            answer=answer,
            pubmed_query=pubmed_query,
            articles=articles,
            plain_language=plain_language,
            session_id=conv.session_id,
        )

    async def _remember(self, conv, question: str, answer: str) -> None:
        """
        Guarda o turno e, quando ele empurra outro para fora da janela de
        íntegra, reescreve o resumo.

        Uma falha aqui não pode derrubar uma resposta que já está pronta: no pior
        caso a conversa perde um pedaço de memória, e é melhor do que devolver
        erro para a usuária.
        """
        convo.record_turn(conv, question, answer)

        overflow = convo.turns_to_compress(conv)
        if not overflow:
            return

        try:
            summarizer = SummarizerAgent(
                on_step=None,            # etapa interna: não vira evento no chat
                model=self.summarizer_model,
                api_key=self.api_key,
            )
            summary = await summarizer.run(
                previous_summary=conv.summary,
                new_turns=overflow,
            )
            if summary.success:
                convo.apply_summary(conv, summary.output, overflow)
        except Exception as e:
            # Sem resumo o turno antigo simplesmente sai da memória; o contexto
            # recente continua valendo.
            print(f"[orchestrator] falha ao resumir conversa: {type(e).__name__}: {e}")
            convo.apply_summary(conv, conv.summary, overflow)

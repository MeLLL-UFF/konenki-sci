"""
RetrievalAgent
--------------
Responsável por:
  1. Traduzir a pergunta da usuária para uma query PubMed em inglês.
  2. Buscar artigos no PubMed com fallback progressivo.
  3. Recuperar os abstracts dos artigos encontrados.
  4. Sintetizar uma resposta científica com base nos artigos.

Retorna em metadata:
  - pubmed_query: query usada na busca final
  - articles: lista de objetos Article
"""

from typing import Optional
from app.agents.base import BaseAgent, AgentResult, StepCallback
from app.providers import get_llm_provider
from app.config import get_settings
from app.services.pubmed import search_pubmed_with_fallback, fetch_abstracts

_QUERY_SYSTEM = (
    "You are a biomedical search expert. "
    "Reply with only a concise PubMed English search query (max 8 keywords). "
    "No explanation, no quotes."
)

_ANSWER_SYSTEM = (
    "Você é uma assistente especializada em saúde feminina e menopausa, baseada em evidências. "
    "Responda de forma científica mas compreensível, citando os estudos com [1], [2], etc. "
    "Use parágrafos estruturados. "
    "Responda sempre em português do Brasil. "
    "Use apenas as informações dos artigos fornecidos. Não invente dados."
)


class RetrievalAgent(BaseAgent):
    """Agente de recuperação: busca evidências no PubMed e sintetiza resposta científica."""

    def __init__(self, on_step: StepCallback = None, model: Optional[str] = None):
        super().__init__(on_step)
        resolved = model or get_settings().retrieval_model or None
        self.llm = get_llm_provider(model=resolved)

    async def run(self, question: str) -> AgentResult:
        # ── Etapa 1: gerar query PubMed ──────────────────────────────────────
        await self._step("Traduzindo pergunta para query científica…")
        pubmed_query = await self.llm.complete(
            system=_QUERY_SYSTEM,
            user=f'Translate this menopause question to a PubMed search query: "{question}"',
        )
        pubmed_query = pubmed_query.strip().strip('"')

        # ── Etapa 2: buscar PMIDs ─────────────────────────────────────────────
        await self._step(f'Buscando no PubMed: "{pubmed_query}"…')
        ids, used_query = await search_pubmed_with_fallback(pubmed_query)

        if used_query != pubmed_query:
            await self._step(f'Refinando busca para: "{used_query}"…')

        if not ids:
            return AgentResult(
                success=False,
                output=(
                    "Não encontrei artigos científicos relevantes no PubMed para essa pergunta. "
                    "Tente reformular com outras palavras."
                ),
                metadata={"pubmed_query": pubmed_query, "articles": []},
            )

        # ── Etapa 3: recuperar abstracts ──────────────────────────────────────
        await self._step(f"Recuperando {len(ids)} artigo(s) científico(s)…")
        articles = await fetch_abstracts(ids)

        if not articles:
            return AgentResult(
                success=False,
                output="Encontrei referências mas não consegui recuperar os resumos. Tente novamente.",
                metadata={"pubmed_query": used_query, "articles": []},
            )

        # ── Etapa 4: sintetizar resposta científica ───────────────────────────
        await self._step("Sintetizando resposta com base nas evidências…")

        corpus = "\n\n".join(
            f"[{i+1}] {a.title} ({a.journal}, {a.year})\n{a.abstract}"
            for i, a in enumerate(articles)
        )

        answer = await self.llm.complete(
            system=_ANSWER_SYSTEM,
            user=(
                f'Pergunta: "{question}"\n\n'
                f"Artigos do PubMed:\n\n{corpus}\n\n"
                f"Responda à pergunta com base exclusivamente nesses artigos."
            ),
        )

        return AgentResult(
            success=True,
            output=answer,
            metadata={"pubmed_query": used_query, "articles": articles},
        )

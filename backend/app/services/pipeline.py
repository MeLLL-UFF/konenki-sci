from dataclasses import dataclass, field
from typing import List, Callable, Awaitable
from app.config import get_settings
from app.providers import get_llm_provider
from app.services.pubmed import search_pubmed, fetch_abstracts, Article

settings = get_settings()

StepCallback = Callable[[str], Awaitable[None]] | None

@dataclass
class PipelineResult:
    answer:      str
    pubmed_query: str
    articles:    List[Article] = field(default_factory=list)

async def run_pipeline(
    question: str,
    plain_language: bool = False,
    on_step: StepCallback = None,
) -> PipelineResult:
    print(f"[PIPELINE] Iniciando pipeline para pergunta: {question}")
    llm = get_llm_provider()
    print(f"[PIPELINE] Provedor LLM: {type(llm).__name__}")

    async def step(msg: str):
        print(f"[PIPELINE] Etapa: {msg}")
        if on_step:
            await on_step(msg)

    if not settings.enable_pubmed:
        await step("Modo temporário: busca PubMed desativada — gerando resposta direta do LLM…")
        pubmed_query = ""
        articles = []

        style = (
            "Responda em linguagem simples e acessível, como se explicasse para uma amiga leiga. "
            "Evite jargões. Use frases curtas. Seja empática e encorajadora."
            if plain_language else
            "Responda de forma científica mas compreensível, citando referências gerais quando possível. "
            "Use parágrafos estruturados."
        )

        system = (
            f"Você é uma assistente especializada em saúde feminina e menopausa, baseada em evidências. "
            f"{style} Responda sempre em português do Brasil. "
            f"Não pesquise no PubMed — responda com conhecimento consolidado e cite fontes gerais de saúde."
        )
        user = (
            f'Pergunta: "{question}"\n\n'
            f"Responda esta pergunta usando apenas o conhecimento técnico e médico disponível no modelo."
        )

        print("[PIPELINE] Chamando LLM para síntese direta de resposta (PubMed desativado)")
        answer = await llm.complete(system=system, user=user)
        print(f"[PIPELINE] Resposta gerada, comprimento: {len(answer)}")
        return PipelineResult(answer=answer, pubmed_query=pubmed_query, articles=articles)

    # ── Etapa 1: traduzir pergunta → query PubMed ────────
    await step("Traduzindo pergunta para query científica…")
    print("[PIPELINE] Chamando LLM para tradução de query PubMed")
    pubmed_query = await llm.complete(
        system="You are a biomedical search expert. Reply with only a concise PubMed English search query (max 8 keywords). No explanation, no quotes.",
        user=f'Translate this menopause question to a PubMed search query: "{question}"',
    )
    pubmed_query = pubmed_query.strip().strip('"')
    print(f"[PIPELINE] Query PubMed: {pubmed_query}")

    # ── Etapa 2: buscar PMIDs ────────────────────────────
    await step(f'Buscando no PubMed: "{pubmed_query}"…')    
    ids = await search_pubmed(pubmed_query)

    if not ids:
        return PipelineResult(
            answer="Não encontrei artigos científicos relevantes no PubMed para essa pergunta. Tente reformular.",
            pubmed_query=pubmed_query,
        )

    # ── Etapa 3: buscar abstracts ────────────────────────
    await step(f"Recuperando {len(ids)} artigo(s) científico(s)…")
    articles = await fetch_abstracts(ids)

    if not articles:
        return PipelineResult(
            answer="Encontrei referências mas não consegui recuperar os resumos. Tente novamente.",
            pubmed_query=pubmed_query,
        )

    # ── Etapa 4: sintetizar resposta ─────────────────────
    await step("Sintetizando resposta com base nas evidências…")

    corpus = "\n\n".join(
        f"[{i+1}] {a.title} ({a.journal}, {a.year})\n{a.abstract}"
        for i, a in enumerate(articles)
    )

    style = (
        "Responda em linguagem simples e acessível, como se explicasse para uma amiga leiga. "
        "Evite jargões. Use frases curtas. Seja empática e encorajadora."
        if plain_language else
        "Responda de forma científica mas compreensível, citando os estudos com [1], [2], etc. "
        "Use parágrafos estruturados."
    )

    system = (
        f"Você é uma assistente especializada em saúde feminina e menopausa, baseada em evidências. "
        f"{style} Responda sempre em português do Brasil. "
        f"Use apenas as informações dos artigos fornecidos. Não invente dados."
    )
    user = (
        f'Pergunta: "{question}"\n\n'
        f"Artigos do PubMed:\n\n{corpus}\n\n"
        f"Responda à pergunta com base exclusivamente nesses artigos."
    )

    print("[PIPELINE] Chamando LLM para síntese final de resposta")
    answer = await llm.complete(system=system, user=user)
    print(f"[PIPELINE] Resposta gerada, comprimento: {len(answer)}")
    return PipelineResult(answer=answer, pubmed_query=pubmed_query, articles=articles)
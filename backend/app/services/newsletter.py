from app.services.pubmed import fetch_recent_topics
from app.providers import get_llm_provider


async def generate_newsletter(days: int = 30, max_results: int = 8) -> dict:
    llm = get_llm_provider()
    articles = await fetch_recent_topics(days=days, max_results=max_results)

    if not articles:
        raise ValueError("Nenhum artigo encontrado no PubMed para o período solicitado.")

    corpus = "\n\n".join(
        f"[{i+1}] {a.title} ({a.journal}, {a.year})\n{a.abstract}"
        for i, a in enumerate(articles)
    )

    title = (await llm.complete(
        system=(
            "Você cria títulos de newsletter científica sobre menopausa. "
            "Retorne apenas o título, sem aspas, em português do Brasil. Seja direto e informativo."
        ),
        user=f"Crie um título para uma newsletter sobre estes artigos recentes:\n{corpus[:1500]}",
    )).strip()

    excerpt = (await llm.complete(
        system=(
            "Você escreve resumos curtos (1 frase, máximo 150 caracteres) para newsletters científicas "
            "sobre menopausa. Retorne apenas o resumo, sem aspas, em português do Brasil."
        ),
        user=f"Escreva um resumo de 1 frase para esta newsletter:\n{corpus[:800]}",
    )).strip()[:150]

    body = await llm.complete(
        system=(
            "Você é redatora de uma newsletter científica sobre menopausa para mulheres brasileiras. "
            "Escreva em Markdown. Use ## para seções, **negrito** para destaques, listas quando apropriado. "
            "Linguagem acessível mas precisa. Cite estudos como [1], [2], etc. "
            "Escreva em português do Brasil. Use apenas os artigos fornecidos — não invente dados."
        ),
        user=(
            f"Escreva uma edição completa da newsletter com base nos seguintes artigos do PubMed:\n\n{corpus}\n\n"
            "Estrutura sugerida: introdução, 2–3 seções temáticas, seção de referências ao final."
        ),
    )

    return {"title": title, "excerpt": excerpt, "body": body}

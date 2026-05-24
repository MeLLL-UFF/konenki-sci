from app.providers import get_llm_provider
from app.services.db_store import get_recent_articles, get_recent_trends


async def generate_newsletter(days: int = 30, max_results: int = 8) -> dict:
    llm = get_llm_provider()
    articles = get_recent_articles(days=days, max_results=max_results)
    trends = get_recent_trends(max_results=max_results)

    if not articles:
        raise ValueError("Nenhum artigo salvo no banco de dados para gerar a newsletter.")
    if not trends:
        p("Nenhuma trend salva no banco de dados para gerar a newsletter.")

    article_lines = []
    for i, a in enumerate(articles):
        summary = a.summary or (a.content or "").strip().replace("\n", " ")[:300]
        article_lines.append(f"[{i+1}] {a.title}\n{summary}")

    trend_lines = []
    for i, t in enumerate(trends):
        summary = t.summary or t.keyword
        trend_lines.append(f"[T{i+1}] {t.keyword}\n{summary}")

    corpus = (
        "ARTIGOS SALVOS NO BANCO:\n"
        + "\n\n".join(article_lines)
        + "\n\nTRENDS SALVAS NO BANCO:\n"
        + "\n\n".join(trend_lines)
    )

    title = (await llm.complete(
        system=(
            "Você cria títulos de newsletter científica sobre menopausa. "
            "Retorne apenas o título, sem aspas, em português do Brasil. Seja direto e informativo."
        ),
        user=f"Crie um título para uma newsletter com base nos artigos e tendências salvos no banco de dados:\n{corpus[:1500]}",
    )).strip()

    excerpt = (await llm.complete(
        system=(
            "Você escreve resumos curtos (1 frase, máximo 150 caracteres) para newsletters científicas "
            "sobre menopausa. Retorne apenas o resumo, sem aspas, em português do Brasil."
        ),
        user=f"Escreva um resumo de 1 frase para esta newsletter com base nos dados salvos no banco:\n{corpus[:800]}",
    )).strip()[:150]

    body = await llm.complete(
        system=(
            "Você é redatora de uma newsletter científica sobre menopausa para mulheres brasileiras. "
            "Escreva em Markdown. Use ## para seções, **negrito** para destaques, listas quando apropriado. "
            "Linguagem acessível mas precisa. Cite estudos como [1], [2], etc. "
            "Escreva em português do Brasil. Use apenas os artigos fornecidos — não invente dados."
        ),
        user=(
            f"Escreva uma edição completa da newsletter com base nos seguintes artigos e trends armazenados no banco de dados:\n\n{corpus}\n\n"
            "Estrutura sugerida: introdução, 2–3 seções temáticas, seção de referências ao final."
        ),
    )

    return {"title": title, "excerpt": excerpt, "body": body}

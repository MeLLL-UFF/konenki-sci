import argparse
import asyncio
from typing import List

from sqlalchemy import select

from app.config import get_settings
from app.services.db_store import extract_summary, record_fetch_log
from app.services.pubmed import fetch_recent_topics
from app.services.trends import fetch_trends
from db_connection import Article as ArticleModel, FetchType, Trend as TrendModel, get_db


def sync_pubmed_articles(articles: List[object]) -> tuple[int, int, int]:
    """Salva apenas artigos novos ou que tenham conteúdo diferente do salvo."""
    new_items = 0
    updated_items = 0
    unchanged_items = 0

    with get_db() as db:
        for article in articles:
            existing = db.scalar(select(ArticleModel).filter_by(pubmed_id=article.pmid))
            title = (article.title or "").strip()
            content = (article.abstract or "").strip()
            summary = extract_summary(content)

            if existing:
                if (existing.title or "").strip() != title or (existing.content or "").strip() != content:
                    existing.title = title
                    existing.content = content
                    existing.summary = summary
                    existing.published_by = article.authors or None
                    existing.published_at = article.pub_date
                    updated_items += 1
                else:
                    unchanged_items += 1
            else:
                db.add(
                    ArticleModel(
                        pubmed_id=article.pmid,
                        title=title,
                        content=content,
                        summary=summary,
                        published_by=article.authors or None,
                        published_at=article.pub_date,
                    )
                )
                new_items += 1

    return new_items, updated_items, unchanged_items


def sync_trends(items: List[dict], source: str = "newsapi") -> tuple[int, int, int]:
    """Salva apenas trends novas; atualiza content/summary se estiverem vazios."""
    new_items = 0
    updated_items = 0
    unchanged_items = 0

    seen: set[str] = set()
    with get_db() as db:
        for item in items:
            keyword = item["keyword"].strip()
            content = item.get("content", "").strip()
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)

            summary = extract_summary(content) if content else extract_summary(keyword)
            existing = db.scalar(select(TrendModel).filter_by(keyword=keyword, source=source))

            if existing:
                if not existing.content and content:
                    existing.content = content
                    existing.summary = summary
                    updated_items += 1
                else:
                    unchanged_items += 1
            else:
                db.add(
                    TrendModel(
                        source=source,
                        keyword=keyword,
                        content=content or None,
                        summary=summary,
                    )
                )
                new_items += 1

    return new_items, updated_items, unchanged_items


async def populate_database(
    pubmed_days: int = 30,
    pubmed_max_results: int = 8,
    trends_query: str = "menopause",
    trends_max_results: int = 10,
) -> dict:
    settings = get_settings()
    if not settings.db_host or not settings.db_name or not settings.db_user or not settings.db_password:
        raise RuntimeError("Variáveis de banco de dados não estão configuradas corretamente.")

    pubmed_articles = await fetch_recent_topics(days=pubmed_days, max_results=pubmed_max_results)
    pubmed_new, pubmed_updated, pubmed_unchanged = sync_pubmed_articles(pubmed_articles)

    news_keywords = await fetch_trends(query=trends_query, max_results=trends_max_results)
    trends_new, trends_updated, trends_unchanged = sync_trends(news_keywords, source="newsapi")

    record_fetch_log(FetchType.articles, new_items=pubmed_new + pubmed_updated)
    record_fetch_log(FetchType.trends, new_items=trends_new + trends_updated)

    result = {
        "pubmed": {
            "new": pubmed_new,
            "updated": pubmed_updated,
            "unchanged": pubmed_unchanged,
        },
        "trends": {
            "new": trends_new,
            "updated": trends_updated,
            "unchanged": trends_unchanged,
        },
    }

    return result


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza a base de dados com PubMed e NewsAPI apenas quando o conteúdo mudar."
    )
    parser.add_argument("--pubmed-days", type=int, default=30, help="Número de dias para buscar artigos no PubMed.")
    parser.add_argument("--pubmed-max-results", type=int, default=8, help="Número máximo de artigos PubMed a buscar.")
    parser.add_argument("--trends-query", type=str, default="menopause", help="Consulta para buscar trends no NewsAPI.")
    parser.add_argument("--trends-max-results", type=int, default=10, help="Número máximo de trends a buscar.")
    args = parser.parse_args()

    print("Iniciando sincronização de base de dados...")
    print(f"PubMed: últimos {args.pubmed_days} dias, max {args.pubmed_max_results} artigos")
    print(f"Trends: query='{args.trends_query}', max {args.trends_max_results} itens")

    result = await populate_database(
        pubmed_days=args.pubmed_days,
        pubmed_max_results=args.pubmed_max_results,
        trends_query=args.trends_query,
        trends_max_results=args.trends_max_results,
    )

    print(f"PubMed: {result['pubmed']['new']} novos, {result['pubmed']['updated']} atualizados, {result['pubmed']['unchanged']} inalterados")
    print(f"Trends: {result['trends']['new']} novas, {result['trends']['updated']} atualizadas, {result['trends']['unchanged']} inalteradas")
    print("Sincronização concluída com persistência no banco.")

    if result['pubmed']['new'] + result['pubmed']['updated'] == 0 and result['trends']['new'] + result['trends']['updated'] == 0:
        print("Nenhuma mudança detectada. A base de dados permanece inalterada.")


if __name__ == "__main__":
    asyncio.run(main())

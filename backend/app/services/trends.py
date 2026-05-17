import httpx
from typing import List
from app.config import get_settings
from app.services.db_store import save_trends, record_fetch_log
from db_connection import FetchType

NEWS_API_URL = "https://newsapi.org/v2/everything"


async def search_trends(query: str, language: str = "pt", max_results: int = 10) -> List[str]:
    settings = get_settings()

    if not settings.news_api_key:
        raise ValueError("NEWS_API_KEY não configurada")

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            NEWS_API_URL,
            params={
                "q": query,
                "language": language,
                "sortBy": "publishedAt",
                "pageSize": max_results,
            },
            headers={
                "X-Api-Key": settings.news_api_key,
                "User-Agent": "Mozilla/5.0",
            },
        )
        r.raise_for_status()
        data = r.json()

    articles = data.get("articles", [])
    titles = [
        article.get("title", "").strip()
        for article in articles
        if article.get("title")
    ][:max_results]

    save_trends(titles, source="newsapi")  # persiste trends no banco
    record_fetch_log(FetchType.trends, new_items=len(titles))
    return titles
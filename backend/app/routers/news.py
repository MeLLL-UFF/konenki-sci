from fastapi import APIRouter, HTTPException
from app.services import notion
from app.services.pubmed import fetch_recent_topics

router = APIRouter()


@router.get("/news")
async def list_news():
    posts = await notion.list_published()
    return {"posts": posts}


@router.get("/news/trends")
async def get_trends():
    articles = await fetch_recent_topics(days=30, max_results=8)
    return {
        "topics": [
            {
                "pmid":    a.pmid,
                "title":   a.title,
                "journal": a.journal,
                "year":    a.year,
            }
            for a in articles
        ]
    }


@router.get("/news/{slug}")
async def get_post(slug: str):
    post = await notion.get_post(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Edição não encontrada")
    return post

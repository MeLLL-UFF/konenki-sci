from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import posts
from app.services.db_store import (
    get_recent_trends,
    list_saved_articles,
    list_saved_trends,
    get_trend_by_id,
    save_subscriber,
)
from app.services.newsletter import generate_newsletter
from populate_database import populate_database
from send_newsletter import main as run_send_newsletter

router = APIRouter()


class SubscribeRequest(BaseModel):
    email: str


@router.post("/news/subscribe", status_code=201)
def subscribe(body: SubscribeRequest):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Email inválido")
    save_subscriber(email)
    return {"message": "Inscrição realizada com sucesso"}


@router.get("/news")
def list_news():
    articles = [
        {
            "id": a.id.hex,
            "slug": a.pubmed_id,
            "title": a.title,
            "summary": a.summary or "",
            "author": a.published_by or "",
            "date": a.published_at.date().isoformat() if a.published_at else None,
        }
        for a in list_saved_articles(max_results=100)
    ]
    trends = [
        {
            "id": t.id.hex,
            "keyword": t.keyword,
            "summary": t.summary or "",
            "source": t.source,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in list_saved_trends(max_results=100)
    ]
    return {"articles": articles, "trends": trends}


@router.get("/news/trends")
def get_trends():
    trends = get_recent_trends(max_results=8)
    return {
        "topics": [
            {
                "keyword": t.keyword,
                "summary": t.summary,
                "source": t.source,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in trends
        ]
    }


@router.get("/news/trends/{trend_id}")
def get_trend(trend_id: UUID):
    trend = get_trend_by_id(trend_id)
    if trend is None:
        raise HTTPException(status_code=404, detail="Trend não encontrada")
    return {
        "id": trend.id.hex,
        "keyword": trend.keyword,
        "summary": trend.summary,
        "content": trend.content,
        "source": trend.source,
        "created_at": trend.created_at.isoformat() if trend.created_at else None,
    }


@router.post("/news/generate", status_code=201)
async def generate_post():
    try:
        data = await generate_newsletter()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    slug = posts.save_post(data["title"], data["excerpt"], data["body"])
    return {"slug": slug, "title": data["title"]}


@router.get("/news/send-newsletter")
def send_newsletter():
    try:
        run_send_newsletter()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Newsletter enviada com sucesso"}


@router.get("/news/populate")
async def populate_news(
    pubmed_days: int = 30,
    pubmed_max_results: int = 8,
    trends_query: str = "menopause",
    trends_max_results: int = 10,
):
    try:
        result = await populate_database(
            pubmed_days=pubmed_days,
            pubmed_max_results=pubmed_max_results,
            trends_query=trends_query,
            trends_max_results=trends_max_results,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": "Base de dados sincronizada.",
        "result": result,
    }


@router.get("/news/{slug}")
async def get_post(slug: str):
    post = posts.get_post(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Edição não encontrada")
    return post

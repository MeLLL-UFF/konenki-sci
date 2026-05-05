from fastapi import APIRouter, HTTPException
from app.services import notion, markdown_store
from app.services.newsletter import generate_newsletter
from app.services.pubmed import fetch_recent_topics

router = APIRouter()


@router.get("/news")
async def list_news():
    local = markdown_store.list_posts()
    remote = await notion.list_published()
    seen: set = set()
    posts = []
    for p in local + remote:
        if p["slug"] not in seen:
            seen.add(p["slug"])
            posts.append(p)

    if not posts:
        try:
            data = await generate_newsletter()
            slug = markdown_store.save_post(data["title"], data["excerpt"], data["body"])
            posts = markdown_store.list_posts()
        except Exception:
            pass

    return {"posts": posts}


@router.get("/news/trends")
async def get_trends():
    articles = await fetch_recent_topics(days=30, max_results=8)
    return {
        "topics": [
            {"pmid": a.pmid, "title": a.title, "journal": a.journal, "year": a.year}
            for a in articles
        ]
    }


@router.post("/news/generate", status_code=201)
async def generate_post():
    try:
        data = await generate_newsletter()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    slug = markdown_store.save_post(data["title"], data["excerpt"], data["body"])
    return {"slug": slug, "title": data["title"]}


@router.get("/news/{slug}")
async def get_post(slug: str):
    post = markdown_store.get_post(slug) or await notion.get_post(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Edição não encontrada")
    return post

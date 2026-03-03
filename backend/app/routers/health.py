from fastapi import APIRouter
from app.config import get_settings

router = APIRouter()

@router.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "emb_provider": settings.emb_provider,
    }
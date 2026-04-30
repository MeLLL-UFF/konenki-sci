from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import ask, health, news

app = FastAPI(
    title="MenopausIA API",
    description="API agnética para perguntas sobre menopausa baseadas em evidências (PubMed).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Em produção: restrinja ao domínio do front
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(ask.router,    prefix="/api")
app.include_router(news.router,   prefix="/api")
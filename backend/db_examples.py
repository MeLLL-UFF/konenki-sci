# ============================================================
#  Exemplos de uso — db_examples.py
# ============================================================

from db_connection import get_db, Article, Trend, ChatSession, ChatMessage
from db_connection import SessionStage, MessageRole, FetchLog, FetchType, FetchStatus
from sqlalchemy import select
import numpy as np


# ------------------------------------------------------------
# 1. Inserir um artigo novo (vindo do PubMed)
# ------------------------------------------------------------
def save_article(pubmed_id: str, title: str, summary: str, content: str):
    with get_db() as db:
        article = Article(
            pubmed_id=pubmed_id,
            title=title,
            summary=summary,
            content=content,
        )
        db.add(article)
    print(f"Artigo salvo: {title[:60]}...")


# ------------------------------------------------------------
# 2. Buscar artigos pendentes de envio
# ------------------------------------------------------------
def get_pending_articles(limit: int = 10):
    with get_db() as db:
        result = db.execute(
            select(Article)
            .where(Article.sent == False)
            .order_by(Article.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# ------------------------------------------------------------
# 3. Marcar artigos como enviados após o digest
# ------------------------------------------------------------
def mark_articles_sent(article_ids: list):
    with get_db() as db:
        db.execute(
            Article.__table__.update()
            .where(Article.id.in_(article_ids))
            .values(sent=True, send_count=Article.send_count + 1)
        )


# ------------------------------------------------------------
# 6. Registrar execução do cron no fetch_log
# ------------------------------------------------------------
def log_fetch(type: str, new_items: int, status: str = "success", error: str = None):
    with get_db() as db:
        log = FetchLog(
            type=FetchType[type],
            new_items=new_items,
            status=FetchStatus[status],
            error_log=error,
        )
        db.add(log)


# ------------------------------------------------------------
# 7. Verificar quantos itens pendentes existem (para o cron diário)
# ------------------------------------------------------------
from sqlalchemy import func

def check_digest_readiness() -> dict:
    with get_db() as db:
        pending_articles = db.execute(
            select(func.count()).where(Article.sent == False)
        ).scalar()

        pending_trends = db.execute(
            select(func.count()).where(Trend.sent == False)
        ).scalar()

    return {
        "pending_articles": pending_articles,
        "pending_trends":   pending_trends,
        "ready":            pending_articles >= 5 or pending_trends >= 5,
    }

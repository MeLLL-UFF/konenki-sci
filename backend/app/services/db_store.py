from typing import Iterable, List

from sqlalchemy import select, func

from db_connection import (
    DigestArticle,
    DigestStatus,
    DigestTrend,
    EmailDigest,
    FetchLog,
    FetchStatus,
    FetchType,
    Subscriber,
    Trend as TrendModel,
    Article as ArticleModel,
    get_db,
)


def save_pubmed_article(article_data: object) -> ArticleModel:
    """Salva ou atualiza um artigo PubMed usando pubmed_id como chave única."""
    with get_db() as db:
        existing = db.scalar(select(ArticleModel).filter_by(pubmed_id=article_data.pmid))
        if existing:
            existing.title = article_data.title
            existing.content = article_data.abstract
            existing.summary = article_data.abstract[:700]
            return existing

        record = ArticleModel(
            pubmed_id=article_data.pmid,
            title=article_data.title,
            content=article_data.abstract,
            summary=article_data.abstract[:700],
        )
        db.add(record)
        db.flush()
        return record


def save_trend(keyword: str, source: str = "newsapi") -> TrendModel:
    """Salva uma tendência evitando duplicatas exatas de keyword+source."""
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("Trend keyword não pode ser vazia")

    with get_db() as db:
        existing = db.scalar(
            select(TrendModel).filter_by(keyword=keyword, source=source)
        )
        if existing:
            return existing

        record = TrendModel(source=source, keyword=keyword)
        db.add(record)
        db.flush()
        return record


def save_trends(keywords: Iterable[str], source: str = "newsapi") -> List[TrendModel]:
    """Persiste múltiplas tendências na base."""
    return [save_trend(keyword, source=source) for keyword in keywords]


def record_fetch_log(
    fetch_type: FetchType,
    new_items: int,
    status: FetchStatus = FetchStatus.success,
    error_log: str | None = None,
) -> FetchLog:
    """Registra o histórico de fetchs no banco."""
    with get_db() as db:
        log = FetchLog(
            type=fetch_type,
            new_items=new_items,
            status=status,
            error_log=error_log,
        )
        db.add(log)
        db.flush()
        return log


def save_subscriber(email: str) -> Subscriber:
    """Cria ou retorna um assinante existente."""
    email = email.strip().lower()
    if not email:
        raise ValueError("Email do assinante não pode ser vazio")

    with get_db() as db:
        existing = db.scalar(select(Subscriber).filter_by(email=email))
        if existing:
            return existing

        record = Subscriber(email=email)
        db.add(record)
        db.flush()
        return record


def get_active_subscriber_count() -> int:
    """Retorna contagem de assinantes ativos."""
    with get_db() as db:
        return db.scalar(select(func.count()).select_from(Subscriber).where(Subscriber.active == True)) or 0


def create_email_digest(
    article_pubmed_ids: List[str],
    trend_keywords: List[str],
    status: DigestStatus = DigestStatus.pending,
    subscriber_count: int = 0,
) -> EmailDigest:
    """Registra um digest de newsletter com as associações de artigos e trends."""
    with get_db() as db:
        articles = db.scalars(
            select(ArticleModel).filter(ArticleModel.pubmed_id.in_(article_pubmed_ids))
        ).all()
        trends = db.scalars(
            select(TrendModel).filter(TrendModel.keyword.in_(trend_keywords))
        ).all()

        digest = EmailDigest(
            subscriber_count=subscriber_count,
            status=status,
        )
        db.add(digest)
        db.flush()

        for article in articles:
            db.add(DigestArticle(digest_id=digest.id, article_id=article.id))
        for trend in trends:
            db.add(DigestTrend(digest_id=digest.id, trend_id=trend.id))

        return digest

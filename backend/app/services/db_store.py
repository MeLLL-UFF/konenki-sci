from datetime import datetime, timedelta
from typing import Iterable, List

from sqlalchemy import select, func, desc

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


def extract_summary(text: str) -> str:
    """Retorna a primeira frase do texto, até o primeiro ponto final."""
    if not text:
        return ""
    return text.strip().partition(".")[0].strip()


def save_pubmed_article(article_data: object) -> ArticleModel:
    """Salva ou atualiza um artigo PubMed usando pubmed_id como chave única."""
    with get_db() as db:
        existing = db.scalar(select(ArticleModel).filter_by(pubmed_id=article_data.pmid))
        if existing:
            existing.title = article_data.title
            existing.content = article_data.abstract
            existing.summary = extract_summary(article_data.abstract)
            return existing

        record = ArticleModel(
            pubmed_id=article_data.pmid,
            title=article_data.title,
            content=article_data.abstract,
            summary=extract_summary(article_data.abstract),
        )
        db.add(record)
        print(f"Salvando artigo PubMed ID {article_data.pmid} - {article_data.title}")
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
            if not existing.summary:
                existing.summary = extract_summary(keyword)
            return existing

        record = TrendModel(
            source=source,
            keyword=keyword,
            summary=extract_summary(keyword),
        )
        db.add(record)
        print(f"Salvando tendência '{keyword}' da fonte '{source}'")
        db.flush()
        return record


def save_trends(keywords: Iterable[str], source: str = "newsapi") -> List[TrendModel]:
    """Persiste múltiplas tendências na base."""
    return [save_trend(keyword, source=source) for keyword in keywords]


def list_saved_articles(max_results: int = 50) -> List[ArticleModel]:
    """Retorna todas as edições de newsletter salvas no banco."""
    with get_db() as db:
        result = db.execute(
            select(ArticleModel)
            .order_by(desc(ArticleModel.created_at))
            .limit(max_results)
        )
        return result.scalars().all()


def list_saved_trends(max_results: int = 50) -> List[TrendModel]:
    """Retorna todas as tendências salvas no banco."""
    with get_db() as db:
        result = db.execute(
            select(TrendModel)
            .order_by(desc(TrendModel.created_at))
            .limit(max_results)
        )
        return result.scalars().all()


def get_trend_by_id(trend_id: str) -> TrendModel | None:
    """Retorna uma trend por ID."""
    with get_db() as db:
        return db.scalar(select(TrendModel).where(TrendModel.id == trend_id))


def get_recent_articles(days: int = 30, max_results: int = 8) -> List[ArticleModel]:
    """Retorna artigos recentes salvos no banco ordenados pelo mais recente."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_db() as db:
        result = db.execute(
            select(ArticleModel)
            .where(ArticleModel.created_at >= cutoff)
            .order_by(desc(ArticleModel.created_at))
            .limit(max_results)
        )
        return result.scalars().all()


def get_recent_trends(max_results: int = 10, source: str | None = None) -> List[TrendModel]:
    """Retorna trends salvas no banco ordenadas pelo mais recente."""
    with get_db() as db:
        query = select(TrendModel)
        if source is not None:
            query = query.where(TrendModel.source == source)
        result = db.execute(
            query.order_by(desc(TrendModel.created_at)).limit(max_results)
        )
        return result.scalars().all()


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
        print(f"Salvando novo assinante: {email}")
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

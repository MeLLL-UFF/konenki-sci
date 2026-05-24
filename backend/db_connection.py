# ============================================================
#  Conexão com PostgreSQL 
#  Dependências: pip install psycopg2-binary sqlalchemy python-dotenv
# ============================================================

import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

# ============================================================
# 1. STRING DE CONEXÃO
#    Configure as variáveis no arquivo .env (veja .env.example)
# ============================================================
DATABASE_URL = (
    f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
)

# ============================================================
# 2. ENGINE  (pool de conexões reutilizáveis)
# ============================================================
engine = create_engine(
    DATABASE_URL,
    pool_size=5,          # conexões mantidas abertas
    max_overflow=10,      # conexões extras em pico
    pool_pre_ping=True,   # verifica se a conexão ainda está viva antes de usar
    echo=False,           # True para logar todas as queries (útil em dev)
)

# ============================================================
# 3. SESSION  (use para todas as operações ORM)
# ============================================================
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

@contextmanager
def get_db():
    """
    Context manager de sessão SQLAlchemy.
    Usa commit/rollback automático e fecha a sessão corretamente.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# ============================================================
# 4. BASE ORM  (todas as models herdam daqui)
# ============================================================
class Base(DeclarativeBase):
    pass

# ============================================================
# 5. MODELS  (espelham as tabelas do schema.sql)
# ============================================================
from sqlalchemy import (
    Column, String, Boolean, Integer, Text,
    DateTime, ForeignKey, UniqueConstraint, Enum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

class DigestStatus(enum.Enum):
    pending = "pending"
    sent    = "sent"
    failed  = "failed"
    partial = "partial"

class FetchType(enum.Enum):
    articles = "articles"
    trends   = "trends"

class FetchStatus(enum.Enum):
    success = "success"
    partial = "partial"
    error   = "error"


class Subscriber(Base):
    __tablename__ = "subscribers"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email             = Column(String(255), nullable=False, unique=True)
    active            = Column(Boolean, nullable=False, default=True)
    subscribed_at     = Column(DateTime(timezone=True), server_default=func.now())
    unsubscribed_at   = Column(DateTime(timezone=True))


class Article(Base):
    __tablename__ = "articles"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pubmed_id    = Column(String(32), nullable=False, unique=True)
    title        = Column(Text, nullable=False)
    content      = Column(Text)
    summary      = Column(Text)
    published_at = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    sent         = Column(Boolean, nullable=False, default=False)
    send_count   = Column(Integer, nullable=False, default=0)



class Trend(Base):
    __tablename__ = "trends"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source     = Column(String(100), nullable=False)
    keyword    = Column(String(255), nullable=False)
    summary    = Column(Text)
    content    = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent       = Column(Boolean, nullable=False, default=False)
    send_count = Column(Integer, nullable=False, default=0)



class EmailDigest(Base):
    __tablename__ = "email_digests"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sent_at          = Column(DateTime(timezone=True), server_default=func.now())
    subscriber_count = Column(Integer, nullable=False, default=0)
    status           = Column(Enum(DigestStatus), nullable=False, default=DigestStatus.pending)
    error_log        = Column(Text)

    articles = relationship("DigestArticle", back_populates="digest")
    trends   = relationship("DigestTrend",   back_populates="digest")


class DigestArticle(Base):
    __tablename__ = "digest_articles"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    digest_id  = Column(UUID(as_uuid=True), ForeignKey("email_digests.id", ondelete="CASCADE"), nullable=False)
    article_id = Column(UUID(as_uuid=True), ForeignKey("articles.id",      ondelete="CASCADE"), nullable=False)

    digest  = relationship("EmailDigest", back_populates="articles")
    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("digest_id", "article_id", name="uq_digest_article"),
    )


class DigestTrend(Base):
    __tablename__ = "digest_trends"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    digest_id = Column(UUID(as_uuid=True), ForeignKey("email_digests.id", ondelete="CASCADE"), nullable=False)
    trend_id  = Column(UUID(as_uuid=True), ForeignKey("trends.id",        ondelete="CASCADE"), nullable=False)

    digest = relationship("EmailDigest", back_populates="trends")
    trend  = relationship("Trend")

    __table_args__ = (
        UniqueConstraint("digest_id", "trend_id", name="uq_digest_trend"),
    )


class FetchLog(Base):
    __tablename__ = "fetch_log"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type       = Column(Enum(FetchType),   nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    new_items  = Column(Integer, nullable=False, default=0)
    status     = Column(Enum(FetchStatus), nullable=False, default=FetchStatus.success)
    error_log  = Column(Text)


# ============================================================
# 6. TESTE DE CONEXÃO  (rode direto: python db_connection.py)
# ============================================================
if __name__ == "__main__":
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            print("✅ Conectado ao PostgreSQL:", result.fetchone()[0])
    except Exception as e:
        print("❌ Falha na conexão:", e)

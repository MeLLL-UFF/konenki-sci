import re
import markdown as md
from datetime import date, datetime
from sqlalchemy import select, desc
from db_connection import get_db, Article


# ============================================================
#  posts.py  —  adaptado para PostgreSQL
#  Interface idêntica ao script original (mesmas funções e
#  retornos), mas persistindo em Article em vez de arquivos .md
# ============================================================


def _slug_from_title(title: str) -> str:
    """Gera slug a partir do título (mesmo comportamento do original)."""
    today = date.today().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    return f"{today}-{slug}"


def _article_to_post(article: Article) -> dict:
    """Converte um model Article no formato de post esperado pelo frontend."""
    return {
        "id":      str(article.id),
        "slug":    article.pubmed_id,        # pubmed_id é usado como slug único
        "title":   article.title,
        "excerpt": article.summary or "",
        "date":    article.published_at.date().isoformat() if article.published_at else "",
    }


def list_posts() -> list[dict]:
    """
    Retorna apenas as edições de newsletter salvas no banco, ordenadas do mais recente ao mais antigo.
    Filtra artigos que já possuem created_at, que é o campo preenchido no app.
    """
    with get_db() as db:
        result = db.execute(
            select(Article).order_by(desc(Article.created_at))
        )
        articles = result.scalars().all()
        return [_article_to_post(a) for a in articles]


def get_post(slug: str) -> dict | None:
    """
    Busca um post pelo slug (mapeado para pubmed_id).
    Antes: varria arquivos .md comparando o frontmatter slug.
    Agora:  query direta por pubmed_id (campo único no banco).
    """
    with get_db() as db:
        result = db.execute(
            select(Article).where(Article.pubmed_id == slug)
        )
        article = result.scalar_one_or_none()

        if article is None:
            return None

        post = _article_to_post(article)
        post["html"] = md.markdown(article.content or "", extensions=["extra"])  # converte markdown para HTML
        return post


def save_post(title: str, excerpt: str, body: str, slug: str | None = None) -> str:
    """
    Cria ou atualiza um post/artigo no banco.
    Antes: gravava arquivo .md em POSTS_DIR.
    Agora:  insere Article (ou atualiza se slug já existe — upsert por pubmed_id).

    Retorna o slug (pubmed_id) do artigo salvo.
    """
    if not slug:
        slug = _slug_from_title(title)

    with get_db() as db:
        # Tenta encontrar artigo existente para não duplicar
        result = db.execute(
            select(Article).where(Article.pubmed_id == slug)
        )
        article = result.scalar_one_or_none()

        if article:
            # Atualiza campos se o post já existe
            article.title        = title
            article.summary      = excerpt
            article.content      = body
            article.published_at = datetime.utcnow()
        else:
            # Insere novo artigo
            article = Article(
                pubmed_id    = slug,
                title        = title,
                summary      = excerpt,
                content      = body,
                published_at = datetime.utcnow(),
            )
            db.add(article)

    return slug
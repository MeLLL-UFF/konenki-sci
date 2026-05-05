import re
import markdown as md
from datetime import date
from pathlib import Path

POSTS_DIR = Path(__file__).parent.parent.parent / "data" / "posts"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("---", 3)
    if end == -1:
        return {}, text
    meta: dict = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()
    return meta, text[end + 3:].strip()


def list_posts() -> list[dict]:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    posts = []
    for f in sorted(POSTS_DIR.glob("*.md"), reverse=True):
        meta, _ = _parse_frontmatter(f.read_text(encoding="utf-8"))
        slug = meta.get("slug") or f.stem
        posts.append({
            "id":      f.stem,
            "slug":    slug,
            "title":   meta.get("title", slug),
            "excerpt": meta.get("excerpt", ""),
            "date":    meta.get("date", ""),
        })
    return posts


def get_post(slug: str) -> dict | None:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    for f in POSTS_DIR.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        if (meta.get("slug") or f.stem) == slug:
            return {
                "id":      f.stem,
                "slug":    slug,
                "title":   meta.get("title", slug),
                "excerpt": meta.get("excerpt", ""),
                "date":    meta.get("date", ""),
                "html":    md.markdown(body, extensions=["extra"]),
            }
    return None


def save_post(title: str, excerpt: str, body: str, slug: str | None = None) -> str:
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
        slug = f"{today}-{slug}"
    content = f"---\ntitle: {title}\nslug: {slug}\nexcerpt: {excerpt}\ndate: {today}\n---\n\n{body}\n"
    (POSTS_DIR / f"{slug}.md").write_text(content, encoding="utf-8")
    return slug

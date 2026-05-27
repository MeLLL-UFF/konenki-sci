import httpx
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from app.config import get_settings

settings = get_settings()

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

_MONTH_ABBR = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}

def _parse_pubdate(year_str: str, month_str: str, day_str: str) -> Optional[datetime]:
    if not year_str:
        return None
    try:
        year = int(year_str)
        month = int(month_str) if month_str.isdigit() else _MONTH_ABBR.get(month_str[:3].lower(), 1) if month_str else 1
        day = int(day_str) if day_str and day_str.isdigit() else 1
        return datetime(year, month, day)
    except (ValueError, TypeError):
        return None

@dataclass
class Article:
    pmid:     str
    title:    str
    abstract: str
    year:     str
    journal:  str
    authors:  str = ""
    pub_date: Optional[datetime] = None

async def search_pubmed(query: str) -> List[str]:
    """Retorna lista de PMIDs para a query."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(ESEARCH, params={
            "db": "pubmed",
            "term": f"{query} menopause",
            "retmax": settings.pubmed_max_results,
            "retmode": "json",
            "sort": "relevance",
        })
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])


async def search_pubmed_with_fallback(query: str) -> tuple[List[str], str]:
    """Busca com fallback progressivo: remove termos do fim até encontrar resultados."""
    terms = query.split()
    while len(terms) >= 2:
        ids = await search_pubmed(" ".join(terms))
        if ids:
            return ids, " ".join(terms)
        terms.pop()
    return [], query

async def fetch_recent_topics(days: int = 30, max_results: int = 8) -> List[Article]:
    """Retorna artigos recentes sobre menopausa para sugestão de tópicos."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(ESEARCH, params={
            "db":       "pubmed",
            "term":     "menopause[MeSH Terms] OR menopausal[tiab]",
            "retmax":   max_results,
            "retmode":  "json",
            "sort":     "pub_date",
            "datetype": "pdat",
            "reldate":  days,
        })
        r.raise_for_status()
        ids = r.json().get("esearchresult", {}).get("idlist", [])
    return await fetch_abstracts(ids)


async def fetch_abstracts(ids: List[str]) -> List[Article]:
    """Busca e parseia os abstracts dos PMIDs fornecidos."""
    if not ids:
        return []
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(EFETCH, params={
            "db": "pubmed",
            "id": ",".join(ids),
            "rettype": "abstract",
            "retmode": "xml",
        })
        r.raise_for_status()

    root = ET.fromstring(r.text)
    articles = []
    for art in root.findall(".//PubmedArticle"):
        def txt(path):
            el = art.find(path)
            return el.text.strip() if el is not None and el.text else ""

        abstract = " ".join(
            el.text.strip()
            for el in art.findall(".//AbstractText")
            if el.text
        )
        if len(abstract) < 50:
            continue

        author_els = art.findall(".//AuthorList/Author")
        author_parts = []
        for author_el in author_els[:3]:
            collective = author_el.findtext("CollectiveName")
            last = author_el.findtext("LastName") or ""
            initials = author_el.findtext("Initials") or ""
            if collective:
                author_parts.append(collective)
            elif last:
                author_parts.append(f"{last} {initials}".strip())
        authors_str = ", ".join(author_parts)
        if len(author_els) > 3:
            authors_str += " et al."

        # Prefere ArticleDate (epub date) sobre PubDate (data do issue da revista)
        article_date_el = art.find(".//ArticleDate[@DateType='Electronic']")
        if article_date_el is not None:
            def adate(tag):
                el = article_date_el.find(tag)
                return el.text.strip() if el is not None and el.text else ""
            year_str = adate("Year")
            pub_date = _parse_pubdate(year_str, adate("Month"), adate("Day"))
        else:
            year_str = txt(".//PubDate/Year")
            pub_date = _parse_pubdate(year_str, txt(".//PubDate/Month"), txt(".//PubDate/Day"))

        articles.append(Article(
            pmid     = txt(".//PMID"),
            title    = txt(".//ArticleTitle"),
            abstract = abstract,
            year     = year_str,
            journal  = txt(".//Journal/Title"),
            authors  = authors_str,
            pub_date = pub_date,
        ))

    return articles
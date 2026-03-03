import httpx
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List
from app.config import get_settings

settings = get_settings()

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

@dataclass
class Article:
    pmid:     str
    title:    str
    abstract: str
    year:     str
    journal:  str

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
        articles.append(Article(
            pmid    = txt(".//PMID"),
            title   = txt(".//ArticleTitle"),
            abstract= abstract[:700],
            year    = txt(".//PubDate/Year"),
            journal = txt(".//Journal/Title"),
        ))
    return articles
"""
Recuperação automática de palavras-chave e hashtags — apoio à geração de newsletters.

Abordagem HÍBRIDA (decisão do TCC):
  1. palavras-chave estruturadas (termos MeSH / keywords de autor vindos do PubMed)
     servem de "semente" autoritativa;
  2. um LLM consolida e traduz para pt-BR a partir do texto + da semente;
  3. se o LLM falhar (sem chave, offline, rate limit), cai para extração estatística
     determinística por frequência — o sistema nunca quebra por causa disso;
  4. as hashtags são derivadas das palavras-chave por normalização (#CamelCase).

A função pública `generate_keywords_and_hashtags` nunca levanta exceção.
"""
import re
import unicodedata
from typing import List, Optional, Tuple

from app.providers import get_llm_provider

# Stopwords mínimas (pt-BR + en) usadas apenas no fallback estatístico.
_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "e", "em",
    "no", "na", "nos", "nas", "por", "para", "com", "que", "se", "ao", "aos", "ou",
    "como", "mais", "menos", "entre", "sobre", "sua", "seu", "suas", "seus", "ser",
    "são", "pode", "podem", "após", "até", "esse", "essa", "este", "esta", "isso",
    "também", "the", "of", "and", "in", "to", "for", "with", "on", "an", "is",
    "are", "by", "from", "this", "that", "was", "were", "has", "have",
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )


def normalize_hashtag(term: str) -> str:
    """Converte uma palavra-chave/frase em hashtag #CamelCase (mantém acentos)."""
    words = [w for w in re.findall(r"[0-9A-Za-zÀ-ÿ]+", term) if w]
    if not words:
        return ""
    camel = "".join(w[:1].upper() + w[1:].lower() if len(w) > 1 else w.upper() for w in words)
    return "#" + camel


def keywords_to_hashtags(keywords: List[str], max_tags: int = 8) -> List[str]:
    """Deriva hashtags únicas a partir de uma lista de palavras-chave."""
    tags: List[str] = []
    seen = set()
    for kw in keywords:
        tag = normalize_hashtag(kw)
        if not tag:
            continue
        key = _strip_accents(tag).lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(tag)
        if len(tags) >= max_tags:
            break
    return tags


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        it = (it or "").strip()
        if not it:
            continue
        key = _strip_accents(it).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def statistical_keywords(text: str, max_keywords: int = 8) -> List[str]:
    """Fallback determinístico: termos (>=4 letras) mais frequentes, sem stopwords."""
    tokens = re.findall(r"[0-9A-Za-zÀ-ÿ]{4,}", (text or "").lower())
    freq: dict[str, int] = {}
    for tok in tokens:
        if tok in _STOPWORDS:
            continue
        freq[tok] = freq.get(tok, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:max_keywords]]


def _parse_llm_list(raw: str) -> List[str]:
    """Aceita lista separada por vírgula, ponto-e-vírgula ou quebra de linha."""
    parts = re.split(r"[,\n;]+", (raw or "").strip())
    cleaned: List[str] = []
    for p in parts:
        p = re.sub(r"^\s*\d+[\.\)]\s*", "", p)        # remove numeração "1." / "1)"
        p = p.strip().strip("-•*#").strip()
        if p:
            cleaned.append(p)
    return cleaned


async def generate_keywords_and_hashtags(
    title: str,
    content: str,
    seed_keywords: Optional[List[str]] = None,
    max_keywords: int = 8,
) -> Tuple[List[str], List[str]]:
    """
    Retorna (keywords, hashtags) para um item (artigo ou notícia).

    Híbrido: usa a semente MeSH como contexto para o LLM e como reserva; se o LLM
    não produzir nada, usa extração estatística. Nunca levanta exceção.
    """
    seed = _dedupe(seed_keywords or [])
    text = f"{title}\n\n{content}".strip()

    llm_keywords: List[str] = []
    try:
        llm = get_llm_provider()
        seed_hint = (
            f" Considere também estes termos técnicos (MeSH): {', '.join(seed[:12])}."
            if seed else ""
        )
        raw = await llm.complete(
            system=(
                "Você extrai palavras-chave para uma newsletter científica sobre menopausa. "
                "Responda APENAS com 5 a 8 palavras-chave em português do Brasil, separadas por "
                "vírgula. Cada uma com 1 a 3 palavras. Sem numeração, sem explicação, sem aspas."
            ),
            user=f"Texto:\n{text[:2000]}{seed_hint}",
        )
        llm_keywords = _parse_llm_list(raw)
    except Exception:
        llm_keywords = []

    # Preferência: keywords pt-BR do LLM; semente MeSH preenche o que faltar.
    keywords = _dedupe(llm_keywords + seed)
    if not keywords:
        keywords = statistical_keywords(text, max_keywords=max_keywords)
    keywords = keywords[:max_keywords]

    hashtags = keywords_to_hashtags(keywords, max_tags=max_keywords)
    return keywords, hashtags

"""
Verificação de idioma da resposta sintetizada (melhoria M5 dos testes adversariais).

O qwen2.5:7b às vezes troca de idioma no meio da síntese: começa em português,
"vaza" um turno de usuário inventado e continua em chinês, ou responde em inglês
porque os resumos do PubMed estão em inglês. Este módulo detecta os dois casos
sem depender de biblioteca externa nem de outra chamada ao modelo:

  - caracteres CJK (chinês, japonês, coreano): qualquer ocorrência reprova;
  - inglês: estima a proporção de palavras funcionais inglesas entre as
    palavras funcionais inglesas e portuguesas do texto. Palavras funcionais
    ("the", "of", "que", "não"…) não dependem do tema, então siglas e termos
    técnicos em inglês (HRT, MHT, "hot flashes") não pesam na conta.
"""

import re
from dataclasses import dataclass

# Hiragana/katakana, ideogramas CJK (+ extensão A), hangul, pontuação CJK e
# formas de largura total (":", "（" etc. que o modelo usa junto com o chinês).
_CJK = re.compile(
    "[　-〿぀-ヿ㐀-䶿一-鿿가-힯＀-￯]"
)

# Só palavras que não existem (ou são raríssimas) na outra língua: "a", "as",
# "no", "do", "me" ficam de fora porque são comuns nos dois idiomas.
_EN = frozenset(
    "the of and with is are was were be been being this that these those which "
    "who whom whose what when where why how it its they their them there here "
    "from by for to into than then also but not or if can could may might should "
    "would will shall has have had does did an at on such other more most some "
    "any each both between however therefore although because while after before "
    "about over under during".split()
)
_PT = frozenset(
    "de que e o os da das dos em um uma uns umas para com não por mais como mas "
    "ao aos na nas no nos se é são foi foram ser estar está estão pela pelo pelas "
    "pelos sua seu suas seus entre isso esta este essa esse também já quando "
    "muito pode podem sobre sem ou ainda nem há mesmo após antes durante porque "
    "embora assim então onde qual quais cada outro outra outros outras".split()
)
_PALAVRA = re.compile(r"[^\W\d_]+", re.UNICODE)

# Abaixo disso a amostra é pequena demais para dizer algo sobre o idioma.
MIN_PALAVRAS = 30
# Proporção de palavras em frases inglesas a partir da qual a resposta é
# regenerada. Calibrada nas execuções do qwen2.5:7b e do sabiá (914 respostas):
# as respostas em português ficam abaixo de 0,04, e as que têm uma frase ou um
# resumo inteiro em inglês ficam acima de 0,25 (ver tests/test_language.py).
LIMIAR_INGLES = 0.15


@dataclass
class LanguageCheck:
    ok: bool
    cjk_chars: int
    english_ratio: float
    reason: str = ""


def cjk_count(text: str) -> int:
    return len(_CJK.findall(text or ""))


_FRASE = re.compile(r"(?<=[.!?:;])\s+|\n+")


def english_ratio(text: str) -> float:
    """
    Fração das palavras do texto que estão em frases escritas em inglês.

    Cada frase é classificada pelas palavras funcionais: é inglesa quando tem
    ao menos 3 funcionais inglesas e mais inglesas que portuguesas. Assim uma
    frase em português com uma sigla ou um termo técnico em inglês não conta,
    mas uma frase inteira (ou um resumo colado) em inglês conta inteira.
    """
    # Títulos entre aspas são citações de artigos, não o idioma da resposta.
    sem_titulos = re.sub(r'"[^"\n]{0,300}"|“[^”\n]{0,300}”', " ", text or "")
    total = ingles = 0
    for frase in _FRASE.split(sem_titulos):
        # "[4] Menopausal hormone therapy and…:" é o título do artigo usado
        # como cabeçalho, não texto da resposta.
        if frase.rstrip(" *").endswith(":"):
            continue
        palavras = _PALAVRA.findall(frase.lower())
        en = sum(w in _EN for w in palavras)
        pt = sum(w in _PT for w in palavras)
        total += len(palavras)
        if en >= 3 and en > pt:
            ingles += len(palavras)
    if total < MIN_PALAVRAS:
        return 0.0
    return ingles / total


def check_language(text: str) -> LanguageCheck:
    cjk = cjk_count(text)
    ratio = english_ratio(text)
    if cjk:
        return LanguageCheck(False, cjk, ratio, f"{cjk} caractere(s) CJK")
    if ratio >= LIMIAR_INGLES:
        return LanguageCheck(False, cjk, ratio, f"{ratio:.0%} das palavras em frases em inglês")
    return LanguageCheck(True, cjk, ratio)


def strip_cjk_tail(text: str) -> str:
    """
    Corta a resposta no primeiro caractere CJK e volta até o fim da última frase
    completa. Último recurso quando nem a regeneração sai limpa: no padrão
    observado o trecho em português antes da troca de idioma está correto, e o
    que vem depois é um turno inventado ou a mesma resposta traduzida.
    """
    m = _CJK.search(text or "")
    if not m:
        return text
    head = text[: m.start()].rstrip()
    # Descarta o pedaço de frase interrompido e eventuais marcadores vazados
    # ("user"). O "4." de uma lista numerada não é fim de frase.
    fim = -1
    for p in _FIM_DE_FRASE.finditer(head):
        if not _MARCADOR_LISTA.fullmatch(head[head.rfind("\n", 0, p.start()) + 1 : p.end()]):
            fim = p.end()
    return head[:fim].rstrip() if fim >= 0 else ""


_FIM_DE_FRASE = re.compile(r"[.!?](?=\s|$)")
_MARCADOR_LISTA = re.compile(r"\s*\d+\.")

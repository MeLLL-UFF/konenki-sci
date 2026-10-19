"""
Filtro de pertinência dos resumos antes da síntese (melhoria M7).

Usam um LLM falso que devolve respostas pré-definidas, então rodam sem rede:

    cd backend
    python -m pytest tests -q
"""
import asyncio

import pytest

from app.agents import retrieval_agent as ra
from app.agents.retrieval_agent import RetrievalAgent, NO_EVIDENCE_MESSAGE
from app.services.pubmed import Article

SINTESE = "Segundo o estudo [1], a terapia hormonal transdérmica tem menor risco de trombose."

ARTIGOS = [
    Article(pmid="11", title="Transdermal estradiol and venous thromboembolism",
            abstract="Oral but not transdermal estrogen increased VTE risk in postmenopausal women.",
            year="2019", journal="BMJ"),
    Article(pmid="22", title="Adjuvant chemotherapy trends in ERBB2-negative breast cancer",
            abstract="Use of adjuvant chemotherapy declined among premenopausal women with node-negative tumors.",
            year="2020", journal="JAMA Oncol"),
    Article(pmid="33", title="Hormone therapy and cardiovascular outcomes",
            abstract="Menopausal hormone therapy was associated with stroke and VTE in older women.",
            year="2017", journal="Climacteric"),
]


class FakeLLM:
    """1ª resposta: query do PubMed; 2ª: notas de pertinência; depois: síntese."""

    def __init__(self, *respostas):
        self.respostas = ["transdermal hormone therapy thrombosis", *respostas]
        self.chamadas = []

    async def complete(self, system: str, user: str) -> str:
        self.chamadas.append((system, user))
        return self.respostas.pop(0)


def recuperacao(monkeypatch, *respostas, artigos=ARTIGOS):
    llm = FakeLLM(*respostas)
    monkeypatch.setattr(ra, "get_llm_provider", lambda model=None, api_key=None: llm)
    monkeypatch.setattr(ra.get_settings(), "relevance_filter", True)

    async def busca(q):
        return [a.pmid for a in artigos], q

    async def resumos(ids):
        return list(artigos)

    monkeypatch.setattr(ra, "search_pubmed_with_fallback", busca)
    monkeypatch.setattr(ra, "fetch_abstracts", resumos)
    return RetrievalAgent(), llm


def rodar(agente, pergunta="A TH transdérmica tem menos risco de trombose?", context=""):
    return asyncio.run(agente.run(question=pergunta, context=context))


# ── _parse_scores ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, esperado", [
    ('{"notas": {"1": 2, "2": 0, "3": 1}}', {1: 2, 2: 0, 3: 1}),
    ('Claro:\n```json\n{"notas": {"1": 0}}\n```', {1: 0}),
    ('{"notas": {"[1]": "2", "2": "x"}}', {1: 2}),          # chave com colchetes; nota ilegível ignorada
])
def test_parse_scores_validos(raw, esperado):
    assert RetrievalAgent._parse_scores(raw) == esperado


@pytest.mark.parametrize("raw", ["", "todos são relevantes", '{"1": 2}', '{"notas": [2, 0]}'])
def test_parse_scores_invalidos(raw):
    assert RetrievalAgent._parse_scores(raw) is None


# ── filtro na recuperação ─────────────────────────────────────────────────────

def test_descarta_resumo_irrelevante_antes_da_sintese(monkeypatch):
    agente, llm = recuperacao(monkeypatch, '{"notas": {"1": 2, "2": 0, "3": 1}}', SINTESE)
    r = rodar(agente)
    assert r.success and r.output == SINTESE
    assert [a.pmid for a in r.metadata["articles"]] == ["11", "33"]
    assert r.metadata["articles_discarded"] == 1
    sintese_user = llm.chamadas[2][1]
    assert "chemotherapy" not in sintese_user
    # as citações são renumeradas: o 3º artigo vira [2]
    assert "[2] Hormone therapy and cardiovascular outcomes" in sintese_user


def test_nenhum_pertinente_diz_que_a_busca_nao_encontrou_evidencia(monkeypatch):
    agente, llm = recuperacao(monkeypatch, '{"notas": {"1": 0, "2": 0, "3": 0}}')
    r = rodar(agente)
    assert not r.success
    assert r.output == NO_EVIDENCE_MESSAGE
    assert "a busca não encontrou evidência" in r.output
    assert r.metadata["no_evidence"] is True
    assert r.metadata["articles_discarded"] == 3
    assert r.metadata["articles"] == []
    assert len(llm.chamadas) == 2                 # não chega a sintetizar


def test_saida_ininterpretavel_mantem_todos(monkeypatch):
    agente, _ = recuperacao(monkeypatch, "todos parecem relevantes", SINTESE)
    r = rodar(agente)
    assert r.success
    assert len(r.metadata["articles"]) == 3
    assert r.metadata["articles_discarded"] == 0


def test_nota_ausente_mantem_o_resumo(monkeypatch):
    agente, _ = recuperacao(monkeypatch, '{"notas": {"2": 0}}', SINTESE)
    r = rodar(agente)
    assert [a.pmid for a in r.metadata["articles"]] == ["11", "33"]


def test_erro_do_provedor_no_filtro_mantem_todos(monkeypatch):
    agente, llm = recuperacao(monkeypatch, SINTESE)
    original = llm.complete

    async def falha_no_filtro(system, user):
        if system == ra._RELEVANCE_SYSTEM:
            raise TimeoutError("lento")
        return await original(system, user)

    llm.complete = falha_no_filtro
    r = rodar(agente)
    assert r.success and len(r.metadata["articles"]) == 3


def test_contexto_da_conversa_vai_para_o_filtro(monkeypatch):
    agente, llm = recuperacao(monkeypatch, '{"notas": {"1": 2, "2": 0, "3": 2}}', SINTESE)
    rodar(agente, pergunta="E depois dos 60?", context="Pergunta anterior: a TH aumenta o risco de trombose?")
    system, user = llm.chamadas[1]
    assert system == ra._RELEVANCE_SYSTEM
    assert "a TH aumenta o risco de trombose?" in user
    assert "E depois dos 60?" in user


def test_filtro_desligado_nao_chama_o_modelo(monkeypatch):
    agente, llm = recuperacao(monkeypatch, SINTESE)
    monkeypatch.setattr(ra.get_settings(), "relevance_filter", False)
    r = rodar(agente)
    assert r.success and len(r.metadata["articles"]) == 3
    assert len(llm.chamadas) == 2                 # query + síntese


def test_busca_sem_resultado_usa_a_mesma_mensagem(monkeypatch):
    agente, _ = recuperacao(monkeypatch, artigos=[])
    r = rodar(agente)
    assert r.output == NO_EVIDENCE_MESSAGE and r.metadata["no_evidence"] is True


def test_mensagem_distingue_ausencia_de_evidencia_de_evidencia_contraria():
    assert "não que a ciência mostre que algo é seguro, inseguro" in NO_EVIDENCE_MESSAGE


def test_sintese_admite_evidencia_indireta():
    assert "indireta ou parcial" in ra._ANSWER_SYSTEM

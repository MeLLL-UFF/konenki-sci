"""
Memória da conversa vista pela triagem (melhoria M6 dos testes adversariais).

Os cenários de cenarios_multiturno.xlsx medem o comportamento do modelo; estes
testes garantem a parte que não depende dele: o contexto dos turnos anteriores
chega à triagem com o mesmo session_id, e turnos bloqueados não entram na
memória. Rodam sem rede:

    cd backend
    python -m pytest tests -q
"""
import asyncio

from app.agents import guardrail_agent as ga
from app.agents import orchestrator as orq
from app.agents.base import AgentResult
from app.services import conversation as convo

PERMITIDA = '{"allowed": true, "urgent": false, "reason": ""}'
RECUSA = '{"allowed": false, "urgent": false, "reason": "saúde masculina"}'
URGENTE = '{"allowed": false, "urgent": true, "reason": "dor na perna"}'


class TriagemFalsa:
    """Devolve os vereditos na ordem dada e guarda o prompt de cada chamada."""

    def __init__(self, *vereditos):
        self.vereditos = list(vereditos)
        self.prompts = []

    async def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        return self.vereditos.pop(0)


class RecuperacaoFalsa:
    def __init__(self, *a, **k):
        pass

    async def run(self, question, context=""):
        return AgentResult(success=True, output=f"resposta sobre: {question}",
                           metadata={"pubmed_query": "q", "articles": []})


def conversa(monkeypatch, *vereditos):
    llm = TriagemFalsa(*vereditos)
    monkeypatch.setattr(ga, "get_llm_provider", lambda model=None, api_key=None: llm)
    monkeypatch.setattr(orq, "RetrievalAgent", RecuperacaoFalsa)
    return llm


def turno(pergunta, session_id=None):
    return asyncio.run(orq.OrchestratorAgent().run(pergunta, session_id=session_id))


def test_segundo_turno_chega_a_triagem_com_o_contexto(monkeypatch):
    llm = conversa(monkeypatch, PERMITIDA, PERMITIDA)
    r1 = turno("A terapia hormonal aumenta o risco de AVC?")
    r2 = turno("E se for por adesivo?", r1.session_id)
    assert r2.session_id == r1.session_id
    assert "Pergunta anterior:" not in llm.prompts[0]          # 1º turno sem contexto
    assert "Pergunta anterior: A terapia hormonal aumenta o risco de AVC?" in llm.prompts[1]
    convo.reset(r1.session_id)


def test_deslocamento_de_escopo_bloqueado_nao_entra_na_memoria(monkeypatch):
    llm = conversa(monkeypatch, PERMITIDA, RECUSA, PERMITIDA)
    r1 = turno("O que é a terapia hormonal da menopausa?")
    r2 = turno("E para os homens?", r1.session_id)
    assert r2.blocked and not r2.urgent
    turno("E ela melhora a libido?", r1.session_id)
    # o 3º turno vê o 1º, mas não o turno bloqueado
    assert "O que é a terapia hormonal da menopausa?" in llm.prompts[2]
    assert "E para os homens?" not in llm.prompts[2]
    assert [t.question for t in convo.get_conversation(r1.session_id).turns] == [
        "O que é a terapia hormonal da menopausa?", "E ela melhora a libido?"]
    convo.reset(r1.session_id)


def test_urgencia_no_meio_da_conversa(monkeypatch):
    conversa(monkeypatch, PERMITIDA, URGENTE)
    r1 = turno("A terapia hormonal aumenta o risco de trombose?")
    r2 = turno("Comecei há um mês e minha perna está inchada e doendo.", r1.session_id)
    assert r2.blocked and r2.urgent
    assert r2.answer == ga.URGENT_MESSAGE
    assert len(convo.get_conversation(r1.session_id).turns) == 1
    convo.reset(r1.session_id)


def test_sessoes_diferentes_nao_compartilham_memoria(monkeypatch):
    llm = conversa(monkeypatch, PERMITIDA, PERMITIDA)
    r1 = turno("A soja ajuda nos fogachos?")
    r2 = turno("Quais alimentos têm mais isoflavona?")          # sem session_id: conversa nova
    assert r2.session_id != r1.session_id
    assert "Pergunta anterior:" not in llm.prompts[1]
    convo.reset(r1.session_id)
    convo.reset(r2.session_id)


def test_prompt_da_triagem_tem_a_regra_de_precedencia():
    assert "PRECEDÊNCIA" in ga._SYSTEM_PROMPT
    assert "e para os homens?" in ga._SYSTEM_PROMPT

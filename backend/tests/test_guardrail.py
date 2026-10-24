"""
Testes do agente de triagem (melhorias M1 e M2 dos testes adversariais).

Usam um LLM falso que devolve respostas pré-definidas, então rodam sem rede,
sem Ollama e sem chave de API:

    cd backend
    python -m pytest tests -q
"""
import asyncio

import pytest

from app.agents import guardrail_agent as ga
from app.agents.guardrail_agent import GuardrailAgent, URGENT_MESSAGE, UNAVAILABLE_MESSAGE


class FakeLLM:
    """Devolve as respostas na ordem dada e conta as chamadas."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = 0

    async def complete(self, system: str, user: str) -> str:
        self.chamadas += 1
        return self.respostas.pop(0)


def triagem(monkeypatch, *respostas):
    llm = FakeLLM(*respostas)
    monkeypatch.setattr(ga, "get_llm_provider", lambda model=None, api_key=None: llm)
    return GuardrailAgent(), llm


def rodar(agente, pergunta="pergunta qualquer"):
    return asyncio.run(agente.run(question=pergunta))


# ── _parse ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw, esperado", [
    ('{"allowed": true, "urgent": false, "reason": ""}', (True, False, "")),
    ('{"allowed": false, "reason": "fora do escopo"}', (False, False, "fora do escopo")),
    ('Claro! Aqui está:\n```json\n{"allowed": true, "urgent": true}\n```', (True, True, "")),
    ('{"allowed": "false", "urgent": "true", "reason": "x"}', (False, True, "x")),
    # texto com chaves antes do JSON de verdade
    ('Avaliei {com cuidado} a pergunta: {"allowed": true}', (True, False, "")),
])
def test_parse_validos(raw, esperado):
    assert GuardrailAgent._parse(raw) == esperado


@pytest.mark.parametrize("raw", [
    "",
    "A pergunta está dentro do escopo.",          # sem JSON
    '{"allowed": true, "reason": ',               # JSON truncado
    '{"urgent": false, "reason": ""}',            # sem "allowed"
    '{"allowed": "talvez"}',                      # "allowed" não booleano
    '{"allowed": 1}',
    '[true]',
])
def test_parse_invalidos_devolvem_none(raw):
    assert GuardrailAgent._parse(raw) is None


# ── M2: falha fechada ─────────────────────────────────────────────────────────

def test_saida_invalida_duas_vezes_bloqueia(monkeypatch):
    agente, llm = triagem(monkeypatch, "não sei", "também não sei")
    r = rodar(agente)
    assert not r.success
    assert r.output == UNAVAILABLE_MESSAGE
    assert r.metadata.get("unparseable") is True
    assert llm.chamadas == 2


def test_saida_invalida_e_depois_valida_segue(monkeypatch):
    agente, llm = triagem(monkeypatch, "lixo", '{"allowed": true, "urgent": false}')
    r = rodar(agente, "a terapia hormonal aumenta o risco de AVC?")
    assert r.success
    assert r.output == "a terapia hormonal aumenta o risco de AVC?"
    assert llm.chamadas == 2


def test_saida_valida_nao_repete_chamada(monkeypatch):
    agente, llm = triagem(monkeypatch, '{"allowed": true}')
    assert rodar(agente).success
    assert llm.chamadas == 1


# ── M1: veredito de urgência ──────────────────────────────────────────────────

def test_urgente_devolve_mensagem_fixa(monkeypatch):
    agente, _ = triagem(monkeypatch, '{"allowed": false, "urgent": true, "reason": "dor no peito"}')
    r = rodar(agente, "to com dor forte no peito e tomo hormonio, pode ser só coisa da menopausa?")
    assert not r.success
    assert r.output == URGENT_MESSAGE
    assert r.metadata["urgent"] is True


def test_urgente_prevalece_sobre_allowed(monkeypatch):
    # sinal de alarme relatado é urgente mesmo que o modelo considere a pergunta em escopo
    agente, _ = triagem(monkeypatch, '{"allowed": true, "urgent": true}')
    r = rodar(agente)
    assert not r.success
    assert r.output == URGENT_MESSAGE


def test_mensagem_urgente_nao_depende_do_motivo_do_modelo(monkeypatch):
    agente, _ = triagem(monkeypatch, '{"allowed": false, "urgent": true, "reason": "TEXTO DO MODELO"}')
    r = rodar(agente)
    assert "TEXTO DO MODELO" not in r.output
    for trecho in ("SAMU (192)", "CVV (188)", "pronto-socorro"):
        assert trecho in URGENT_MESSAGE


def test_fora_de_escopo_mantem_mensagem_com_motivo(monkeypatch):
    agente, _ = triagem(monkeypatch, '{"allowed": false, "urgent": false, "reason": "tema de esportes"}')
    r = rodar(agente)
    assert not r.success
    assert "tema de esportes" in r.output
    assert r.output != URGENT_MESSAGE
    assert not r.metadata.get("urgent")


def test_prompt_pede_o_campo_urgent():
    assert '"urgent"' in ga._SYSTEM_PROMPT


def test_prompt_detalha_criterio_de_urgencia():
    # Falsos urgentes da rodada M3 (N = 3): A8 relato (evento passado),
    # C2 formal (piora de fogacho + dose) e F4 sem_marcador (dor pélvica sem ser nova).
    p = ga._SYSTEM_PROMPT
    assert "TRÊS condições" in p
    assert "NÃO são urgentes" in p
    assert "nova, súbita ou acompanhada de febre" in p
    assert 'nem "allowed"\n  nem "urgent"' in p


def test_exemplos_de_urgencia_tem_os_dois_lados():
    import re
    bloco = ga._SYSTEM_PROMPT.split("Exemplos de urgência:")[1].split("Regras de formato:")[0]
    vereditos = [GuardrailAgent._parse(e) for e in re.findall(r"→ (\{.*\})", bloco)]
    assert any(urgent for _, urgent, _ in vereditos)
    assert any(not urgent for _, urgent, _ in vereditos)


# ── M3: regra de bloqueio mais precisa ────────────────────────────────────────

def test_prompt_bloqueia_dose_e_prescricao_inclusive_hipotetica():
    p = ga._SYSTEM_PROMPT
    for trecho in ("dose", "prescrição", "hipoteticamente", "como se fosse médica"):
        assert trecho in p


def test_prompt_permite_terceira_pessoa_e_premissa_falsa():
    p = ga._SYSTEM_PROMPT
    assert "perguntar sobre\n      outra pessoa não é pedir diagnóstico" in p
    assert "Perguntas com premissa falsa" in p
    assert "não muda o veredito" in p


def test_exemplos_do_prompt_sao_json_validos():
    # Os exemplos ensinam o formato; um exemplo malformado ensinaria o erro.
    import re
    exemplos = re.findall(r"→ (\{.*\})", ga._SYSTEM_PROMPT)
    assert len(exemplos) >= 6
    for e in exemplos:
        assert GuardrailAgent._parse(e) is not None


def test_sintese_proibe_dose_e_corrige_premissa():
    from app.agents import retrieval_agent as ra
    assert "Nunca indique dose" in ra._ANSWER_SYSTEM
    assert "premissa falsa" in ra._ANSWER_SYSTEM

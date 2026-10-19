"""
O veredito de urgência precisa chegar até a resposta da API e interromper o
pipeline antes da recuperação no PubMed.
"""
import asyncio

from app.agents import guardrail_agent as ga
from app.agents import orchestrator as orq
from app.agents.guardrail_agent import URGENT_MESSAGE
from app.routers.ask import _to_response


class FakeLLM:
    def __init__(self, resposta):
        self.resposta = resposta

    async def complete(self, system: str, user: str) -> str:
        return self.resposta


def preparar(monkeypatch, veredito):
    monkeypatch.setattr(ga, "get_llm_provider", lambda model=None, api_key=None: FakeLLM(veredito))

    class RetrievalProibido:
        def __init__(self, *a, **k):
            pass

        async def run(self, *a, **k):
            raise AssertionError("a recuperação não deveria rodar para pergunta bloqueada")

    monkeypatch.setattr(orq, "RetrievalAgent", RetrievalProibido)


def test_urgencia_chega_na_resposta_da_api(monkeypatch):
    preparar(monkeypatch, '{"allowed": false, "urgent": true, "reason": "dor no peito"}')
    resultado = asyncio.run(orq.OrchestratorAgent().run("estou com dor forte no peito"))
    assert resultado.blocked and resultado.urgent
    resposta = _to_response(resultado)
    assert resposta.urgent is True
    assert resposta.answer == URGENT_MESSAGE
    assert resposta.articles == []


def test_bloqueio_comum_nao_e_urgente(monkeypatch):
    preparar(monkeypatch, '{"allowed": false, "urgent": false, "reason": "esportes"}')
    resultado = asyncio.run(orq.OrchestratorAgent().run("quem ganhou o jogo?"))
    assert resultado.blocked and not resultado.urgent
    assert _to_response(resultado).urgent is False


def test_saida_ilegivel_bloqueia_sem_buscar(monkeypatch):
    preparar(monkeypatch, "resposta sem JSON")
    resultado = asyncio.run(orq.OrchestratorAgent().run("pergunta qualquer"))
    assert resultado.blocked and not resultado.urgent

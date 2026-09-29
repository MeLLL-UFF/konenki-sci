"""
SummarizerAgent
---------------
Comprime os turnos antigos de uma conversa num resumo curto, que o Orchestrator
injeta nos prompts dos turnos seguintes.

É o que permite manter contexto sem reenviar a conversa inteira a cada pergunta:
o resumo é reescrito de forma incremental — recebe o resumo anterior mais os
turnos que saíram da janela de íntegra e devolve um resumo novo, sempre dentro
do mesmo orçamento de palavras.

Roda depois de a resposta já ter sido entregue à usuária, então sua latência não
aparece no chat.
"""

from typing import List, Optional

from app.agents.base import BaseAgent, AgentResult, StepCallback
from app.providers import get_llm_provider
from app.config import get_settings
from app.services.conversation import Turn, MAX_CHARS_PER_TURN, _truncate

# O limite de palavras é a peça que segura o custo em tokens: sem ele o resumo
# cresce a cada turno e o problema de custo volta pela porta dos fundos.
MAX_SUMMARY_WORDS = 150

_SYSTEM_PROMPT = (
    "Você mantém a memória de uma conversa sobre menopausa entre uma usuária e uma "
    "assistente científica.\n"
    "Reescreva o resumo da conversa incorporando os novos turnos fornecidos.\n"
    "Regras:\n"
    f"- No máximo {MAX_SUMMARY_WORDS} palavras. Este limite é rígido.\n"
    "- Registre os temas já perguntados, o que já foi respondido e o perfil da usuária "
    "quando ela o revelar (idade, sintomas, se usa terapia hormonal, preferências).\n"
    "- Priorize o que ajuda a entender perguntas futuras; descarte detalhes de estudos "
    "e números específicos.\n"
    "- Escreva em português do Brasil, em texto corrido e impessoal.\n"
    "- Não faça perguntas, não dê conselhos médicos e não acrescente nada que não "
    "esteja nos turnos."
)


class SummarizerAgent(BaseAgent):
    """Agente de memória: mantém o resumo rolante da conversa."""

    def __init__(
        self,
        on_step: StepCallback = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(on_step)
        settings = get_settings()
        # Tarefa simples: aceita o modelo mais barato configurado.
        resolved = model or settings.summarizer_model or settings.guardrail_model or None
        self.llm = get_llm_provider(model=resolved, api_key=api_key)

    async def run(self, previous_summary: str, new_turns: List[Turn]) -> AgentResult:
        if not new_turns:
            return AgentResult(success=True, output=previous_summary or "")

        block = "\n\n".join(
            f"Pergunta: {t.question}\nResposta: {_truncate(t.answer, MAX_CHARS_PER_TURN)}"
            for t in new_turns
        )

        prior = previous_summary.strip() or "(ainda não há resumo; este é o início da conversa)"

        summary = await self.llm.complete(
            system=_SYSTEM_PROMPT,
            user=(
                f"Resumo atual:\n{prior}\n\n"
                f"Novos turnos a incorporar:\n\n{block}\n\n"
                f"Escreva o resumo atualizado em no máximo {MAX_SUMMARY_WORDS} palavras."
            ),
        )

        summary = summary.strip()

        # Rede de proteção: se o modelo ignorar o limite, cortamos no cliente —
        # o orçamento de tokens do contexto não pode depender da obediência dele.
        words = summary.split()
        if len(words) > MAX_SUMMARY_WORDS:
            summary = " ".join(words[:MAX_SUMMARY_WORDS]) + "…"

        return AgentResult(success=True, output=summary)

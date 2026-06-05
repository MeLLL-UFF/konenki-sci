"""
GuardrailAgent
--------------
Avalia se a pergunta da usuária é adequada e dentro do escopo
da plataforma (saúde feminina, menopausa e temas relacionados).

Retorna:
  - success=True  → pergunta permitida, fluxo segue normalmente.
  - success=False → pergunta fora do escopo ou inadequada;
                    output contém mensagem amigável para a usuária.
"""

from typing import Optional
from app.agents.base import BaseAgent, AgentResult, StepCallback
from app.providers import get_llm_provider
from app.config import get_settings

_SYSTEM_PROMPT = """
Você é um agente de triagem de uma plataforma de saúde feminina especializada em menopausa
e temas relacionados (climatério, hormônios, saúde óssea, saúde cardiovascular,
saúde mental, sexualidade, envelhecimento saudável e qualidade de vida da mulher).

Avalie a pergunta da usuária e responda APENAS com um JSON no seguinte formato:
{
  "allowed": true,
  "reason": ""
}

Regras:
- "allowed" deve ser true se a pergunta for sobre saúde feminina, menopausa ou temas diretamente relacionados.
- "allowed" deve ser false se a pergunta:
    * For sobre temas completamente alheios à saúde feminina (ex: política, esportes, receitas, tecnologia).
    * Contiver linguagem ofensiva, discriminatória ou abusiva.
    * Solicitar diagnósticos médicos pessoais definitivos.
    * For sobre saúde masculina exclusiva ou saúde infantil.
- "reason" deve conter, em português, uma breve explicação APENAS quando allowed=false.
- Não adicione nada além do JSON.
""".strip()


class GuardrailAgent(BaseAgent):
    """Agente de guarda: valida escopo e adequação da pergunta."""

    def __init__(self, on_step: StepCallback = None, model: Optional[str] = None):
        super().__init__(on_step)
        resolved = model or get_settings().guardrail_model or None
        self.llm = get_llm_provider(model=resolved)

    async def run(self, question: str) -> AgentResult:
        await self._step("Verificando se a pergunta está dentro do escopo…")

        raw = await self.llm.complete(
            system=_SYSTEM_PROMPT,
            user=f'Pergunta: "{question}"',
        )

        allowed, reason = self._parse(raw)

        if allowed:
            return AgentResult(success=True, output=question)

        # Monta mensagem amigável para a usuária
        message = (
            "Oi! 😊 Sou especializada em saúde feminina e menopausa e, infelizmente, "
            "não consigo ajudar com essa pergunta.\n\n"
            f"**Motivo:** {reason}\n\n"
            "Fique à vontade para perguntar sobre menopausa, climatério, saúde hormonal, "
            "saúde óssea, bem-estar e outros temas relacionados à saúde da mulher. 💜"
        )
        return AgentResult(success=False, output=message, metadata={"reason": reason})

    @staticmethod
    def _parse(raw: str) -> tuple:
        """Extrai allowed e reason do JSON retornado pelo LLM."""
        import json, re

        # Tenta extrair JSON mesmo que o modelo adicione texto extra
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return bool(data.get("allowed", True)), data.get("reason", "")
            except json.JSONDecodeError:
                pass

        # Fallback seguro: se não conseguiu parsear, deixa passar
        return True, ""

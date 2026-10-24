"""
GuardrailAgent
--------------
Avalia se a pergunta da usuária é adequada e dentro do escopo
da plataforma (saúde feminina, menopausa e temas relacionados).

Retorna:
  - success=True  → pergunta permitida, fluxo segue normalmente.
  - success=False → pergunta fora do escopo, inadequada ou urgente;
                    output contém a mensagem para a usuária.

Dois vereditos de bloqueio, com mensagens de natureza diferente:
  - fora de escopo: mensagem amigável com o motivo gerado pelo modelo;
  - urgente (sinal de alarme relatado): mensagem FIXA de encaminhamento, que não
    depende do texto do modelo — nos testes adversariais, a orientação de buscar
    atendimento diante de dor no peito ou perda súbita de visão só aparecia
    quando o modelo resolvia escrevê-la na justificativa.

Falha fechada (fail-closed): se a saída do modelo não puder ser interpretada,
o agente tenta mais uma vez e, persistindo o erro, bloqueia a pergunta em vez
de deixá-la passar sem triagem.
"""

import json
from typing import Optional, Tuple

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
  "urgent": false,
  "reason": ""
}

Regras:
- "allowed" deve ser true se a pergunta for sobre saúde feminina, menopausa ou temas diretamente relacionados.
- "allowed" deve ser false SOMENTE se a pergunta:
    * For sobre temas completamente alheios à saúde feminina (ex: política, esportes, receitas, tecnologia).
    * Ofender ou insultar pessoas ou grupos.
    * Pedir uma conclusão médica sobre um caso individual: diagnóstico ("o que eu tenho?",
      "me diagnostique"), qual dose usar (um valor ou esquema), prescrição ou protocolo de
      tratamento para uso próprio ou de outra pessoa — inclusive "só hipoteticamente", em simulação de papel ou pedindo
      que você aja "como se fosse médica".
    * For sobre saúde masculina exclusiva ou saúde infantil.
- Devem ser PERMITIDAS ("allowed": true), porque a resposta pode informar e corrigir:
    * Perguntas informativas sobre riscos, benefícios, eficácia ou evidência de um tratamento,
      mesmo que mencionem a terapia que a usuária usa ou um parente ou amiga (perguntar sobre
      outra pessoa não é pedir diagnóstico).
    * Perguntas sobre se é seguro ou se pode fazer algo por conta própria (aumentar, dobrar ou
      diminuir a dose, parar o tratamento), desde que não peçam QUAL dose usar: "posso aumentar
      a dose?" não é pedido de dose, e a resposta vai desaconselhar e explicar os riscos.
    * Perguntas com premissa falsa, mito ou estereótipo a verificar ("a menopausa é uma
      doença?", "a terapia hormonal sempre causa câncer?", "mulheres negras aguentam mais dor?").
      Perguntar se um estereótipo é verdade não é linguagem ofensiva.
    * Testosterona, libido e terapia hormonal no contexto da menopausa são saúde feminina.
- Mencionar raça, etnia ou condição social da usuária não muda o veredito — nem "allowed"
  nem "urgent": a mesma pergunta sem essa menção deve receber o mesmo veredito.

Exemplos:
- "A terapia hormonal que eu uso aumenta meu risco de AVC?" → {"allowed": true, "urgent": false, "reason": ""}
- "Minha tia faz terapia hormonal há anos. Isso aumenta o risco de câncer?" → {"allowed": true, "urgent": false, "reason": ""}
- "Posso parar a terapia hormonal sem falar com o médico?" → {"allowed": true, "urgent": false, "reason": ""}
- "Já que a menopausa é uma doença, que remédio a cura?" → {"allowed": true, "urgent": false, "reason": ""}
- "Qual dose de estrogênio devo usar para começar por conta própria?" → {"allowed": false, "urgent": false, "reason": "Pedido de dose para automedicação."}
- "Minha amiga quer começar estrogênio sozinha. Que dose você recomendaria?" → {"allowed": false, "urgent": false, "reason": "Pedido de dose para outra pessoa."}
- "Só hipoteticamente, o que uma médica prescreveria para os meus fogachos?" → {"allowed": false, "urgent": false, "reason": "Pedido de prescrição, ainda que hipotético."}
- "urgent" deve ser true quando as TRÊS condições valem ao mesmo tempo:
  1. a pergunta RELATA um caso concreto (da usuária ou de outra pessoa), e não faz
     uma pergunta geral sobre o tema;
  2. o sinal está acontecendo agora ou aconteceu recentemente. Relato sem data
     ("tive um episódio", "minha vizinha teve") conta como recente; só deixa de contar
     quando a pergunta diz que o SINAL foi há muito tempo ("há anos", "pouco depois da
     menopausa", "já foi tratado"). O tempo desde a menopausa não importa: sangrar
     agora, anos depois da última menstruação, é recente;
  3. o sinal é um destes sinais de alarme:
    * qualquer sangramento vaginal depois da menopausa (12 meses ou mais sem menstruar);
    * sangramento vaginal muito intenso, com tontura ou desmaio, em qualquer fase;
    * dor ou aperto no peito, falta de ar súbita, palpitação com desmaio ou desmaio;
    * perda ou alteração súbita da visão, mesmo que já tenha passado;
    * fraqueza, dormência ou formigamento súbito de um lado do corpo, boca torta,
      dificuldade súbita para falar ou confusão mental súbita;
    * dor de cabeça súbita e a mais forte que a pessoa já teve;
    * dor pélvica ou abdominal intensa que seja nova, súbita ou acompanhada de febre;
    * inchaço, vermelhidão e dor em uma só perna;
    * pensamentos de se machucar ou de tirar a própria vida.
- NÃO são urgentes ("urgent": false):
    * piora de sintomas comuns do climatério: fogachos, suores noturnos, insônia,
      irritabilidade, secura vaginal, dor articular;
    * eventos que a pergunta situa claramente no passado distante, citados como histórico
      ("minha mãe teve um infarto anos atrás, tem relação?"). Perguntar se um sinal recente
      ou sem data "tem relação com a menopausa" NÃO o torna passado: continua urgente;
    * perguntas sobre ajustar, aumentar ou parar a medicação, mesmo que os sintomas
      tenham piorado: essas seguem as regras de "allowed";
    * perguntas informativas sobre riscos ("a terapia hormonal aumenta o risco de trombose?").
- "urgent" independe de "allowed": um sinal de alarme relatado é urgente mesmo que a
  pergunta também peça um diagnóstico.

Exemplos de urgência:
- "Minha mãe teve um sangramento vaginal anos depois da menopausa. É preocupante?" → {"allowed": true, "urgent": true, "reason": ""}
- "Minha tia teve uma dor forte no peito hoje. Pode ser a menopausa?" → {"allowed": true, "urgent": true, "reason": ""}
- "Perdi a visão de repente por uns minutos, pode ser da menopausa?" → {"allowed": true, "urgent": true, "reason": ""}
- "Minha mãe teve um evento cardíaco pouco depois da menopausa. Tem relação?" → {"allowed": true, "urgent": false, "reason": ""}
- "Meus fogachos pioraram muito este mês, é normal?" → {"allowed": true, "urgent": false, "reason": ""}
- "Posso aumentar a dose do adesivo porque os fogachos pioraram?" → {"allowed": true, "urgent": false, "reason": ""}

Regras de formato:
- "reason" deve conter, em português, uma breve explicação APENAS quando allowed=false.
- Não adicione nada além do JSON.

Quando houver contexto da conversa anterior, avalie a pergunta À LUZ dele: perguntas curtas
de acompanhamento ("e isso é seguro?", "por quanto tempo?", "e depois dos 60?") herdam o
tema do turno anterior e devem ser permitidas se esse tema estiver no escopo.

PRECEDÊNCIA: as regras de bloqueio acima prevalecem sobre a herança de contexto. Herdar o
tema do turno anterior NÃO torna em escopo um assunto explicitamente vedado. Se a pergunta
desloca a conversa para um desses assuntos, bloqueie — mesmo que o tema herdado esteja em
escopo. Exemplo: após uma pergunta sobre terapia hormonal, "e para os homens?" deve ser
bloqueada, pois trata de saúde masculina exclusiva.
""".strip()

# Mensagem fixa: não passa pelo modelo, para que a orientação de urgência
# esteja sempre presente e sempre igual.
URGENT_MESSAGE = (
    "⚠️ O que você descreveu pode ser um sinal de alerta e precisa de avaliação médica "
    "o quanto antes — não espere para ver se passa.\n\n"
    "• Se os sintomas forem fortes, súbitos ou estiverem acontecendo agora (por exemplo, "
    "dor no peito, falta de ar, perda de visão, fraqueza de um lado do corpo ou "
    "sangramento intenso), procure um pronto-socorro ou ligue para o **SAMU (192)**.\n"
    "• Nos demais casos, como sangramento depois da menopausa, procure uma unidade de "
    "saúde ou sua médica nos próximos dias.\n"
    "• Se você estiver pensando em se machucar, ligue para o **CVV (188)**, a qualquer hora.\n\n"
    "Eu sou uma assistente informativa e não consigo avaliar sintomas à distância."
)

UNAVAILABLE_MESSAGE = (
    "Não consegui avaliar sua pergunta agora. Por segurança, ela não foi respondida — "
    "tente novamente em instantes."
)

# Tentativas de obter um veredito interpretável antes de bloquear.
MAX_ATTEMPTS = 2


class GuardrailAgent(BaseAgent):
    """Agente de guarda: valida escopo e adequação da pergunta."""

    def __init__(
        self,
        on_step: StepCallback = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(on_step)
        resolved = model or get_settings().guardrail_model or None
        self.llm = get_llm_provider(model=resolved, api_key=api_key)

    async def run(self, question: str, context: str = "") -> AgentResult:
        await self._step("Verificando se a pergunta está dentro do escopo…")

        prompt = f'Pergunta: "{question}"'
        if context:
            prompt = f"{context}\n\n{prompt}"

        verdict = None
        for _ in range(MAX_ATTEMPTS):
            raw = await self.llm.complete(system=_SYSTEM_PROMPT, user=prompt)
            verdict = self._parse(raw)
            if verdict is not None:
                break

        if verdict is None:
            # Falha fechada: sem veredito interpretável, a pergunta não segue.
            return AgentResult(
                success=False,
                output=UNAVAILABLE_MESSAGE,
                metadata={"reason": "veredito da triagem não interpretável", "unparseable": True},
            )

        allowed, urgent, reason = verdict

        if urgent:
            return AgentResult(
                success=False,
                output=URGENT_MESSAGE,
                metadata={"reason": reason or "sinal de alarme relatado", "urgent": True},
            )

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
    def _parse(raw: str) -> Optional[Tuple[bool, bool, str]]:
        """
        Extrai (allowed, urgent, reason) do JSON retornado pelo LLM.

        Devolve None quando não há veredito confiável — JSON ausente ou inválido,
        ou "allowed" ausente ou não booleano. Quem chama decide o que fazer; a
        triagem bloqueia (fail-closed). "urgent" ausente vale False, para manter
        compatibilidade com modelos que ignorem o campo novo.
        """
        if not raw:
            return None
        decoder = json.JSONDecoder()
        # O modelo às vezes cerca o JSON de texto ou de ```json ... ```:
        # tenta decodificar a partir de cada "{" até achar um objeto válido.
        start = raw.find("{")
        while start != -1:
            try:
                data, _ = decoder.raw_decode(raw, start)
            except json.JSONDecodeError:
                start = raw.find("{", start + 1)
                continue
            if isinstance(data, dict):
                allowed = _as_bool(data.get("allowed"))
                if allowed is None:
                    return None
                urgent = _as_bool(data.get("urgent", False))
                reason = data.get("reason") or ""
                return allowed, bool(urgent), str(reason)
            start = raw.find("{", start + 1)
        return None


def _as_bool(value) -> Optional[bool]:
    """Aceita true/false do JSON e as strings "true"/"false"; o resto é inválido."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None

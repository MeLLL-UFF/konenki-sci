"""
Memória de conversa
-------------------
Guarda o contexto de cada sessão de chat para que os agentes reconheçam o que
já foi perguntado antes. Sem isto cada pergunta chega ao LLM como se fosse a
primeira da conversa.

Estratégia de compressão — o ponto central deste módulo:

  • Os 2 turnos mais recentes ficam na íntegra (pergunta + resposta), porque é
    neles que moram os pronomes das perguntas de acompanhamento
    ("e isso é seguro?", "mas e depois dos 60?").
  • Todo o resto é comprimido num resumo de no máximo ~150 palavras, reescrito
    a cada novo turno pelo próprio LLM.

Assim o custo em tokens fica praticamente constante — não cresce com o número
de perguntas —, em vez de crescer linearmente como um histórico completo.

O armazenamento é em memória do processo, com expiração por inatividade: uma
conversa de TCC dura minutos, e isto evita mexer no schema do banco. O efeito
colateral é que reiniciar o servidor (deploy no Render, por exemplo) esvazia as
conversas em andamento.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Quantos turnos recentes mandamos sem comprimir.
VERBATIM_TURNS = 2

# Acima disso, o texto de um turno é truncado antes de entrar no contexto —
# uma resposta científica inteira gastaria mais tokens do que agrega.
MAX_CHARS_PER_TURN = 700

# Conversa sem uso por este tempo é descartada.
TTL = timedelta(hours=2)

# Trava simples contra crescimento indefinido do dicionário em memória.
MAX_SESSIONS = 500


@dataclass
class Turn:
    """Uma rodada de pergunta e resposta."""
    question: str
    answer: str


@dataclass
class Conversation:
    session_id: str
    summary: str = ""                       # resumo dos turnos já comprimidos
    turns: List[Turn] = field(default_factory=list)   # turnos ainda na íntegra
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def is_empty(self) -> bool:
        return not self.summary and not self.turns

    def as_context(self) -> str:
        """
        Monta o bloco de contexto que vai nos prompts dos agentes.

        Retorna string vazia quando a conversa acabou de começar, para que o
        primeiro turno não carregue cabeçalho nenhum.
        """
        if self.is_empty():
            return ""

        parts: List[str] = []

        if self.summary:
            parts.append(f"Resumo da conversa até aqui:\n{self.summary}")

        if self.turns:
            recent = "\n\n".join(
                f"Pergunta anterior: {t.question}\n"
                f"Resposta anterior: {_truncate(t.answer)}"
                for t in self.turns
            )
            parts.append(f"Turnos mais recentes:\n{recent}")

        return "\n\n".join(parts)


def _truncate(text: str, limit: int = MAX_CHARS_PER_TURN) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " […]"


# ── Store em memória ──────────────────────────────────────────────────────────

_sessions: Dict[str, Conversation] = {}


def _purge_expired() -> None:
    limit = datetime.now(timezone.utc) - TTL
    for sid in [s for s, c in _sessions.items() if c.updated_at < limit]:
        _sessions.pop(sid, None)


def new_session_id() -> str:
    return uuid.uuid4().hex


def get_conversation(session_id: Optional[str]) -> Conversation:
    """
    Devolve a conversa da sessão, criando-a quando o id é novo ou ausente.

    Um id desconhecido (servidor reiniciado, sessão expirada) não é erro: vira
    uma conversa vazia com aquele mesmo id, e o chat continua funcionando —
    apenas sem lembrar o que veio antes.
    """
    _purge_expired()

    if session_id and session_id in _sessions:
        conv = _sessions[session_id]
        conv.touch()
        return conv

    sid = session_id or new_session_id()

    # Store cheio: abre espaço descartando as conversas mais antigas.
    if len(_sessions) >= MAX_SESSIONS:
        for old, _ in sorted(_sessions.items(), key=lambda kv: kv[1].updated_at)[:50]:
            _sessions.pop(old, None)

    conv = Conversation(session_id=sid)
    _sessions[sid] = conv
    return conv


def record_turn(conv: Conversation, question: str, answer: str) -> None:
    """Acrescenta um turno à conversa, mantendo apenas os mais recentes."""
    conv.turns.append(Turn(question=question.strip(), answer=(answer or "").strip()))
    conv.touch()


def turns_to_compress(conv: Conversation) -> List[Turn]:
    """Turnos que passaram da janela de íntegra e devem entrar no resumo."""
    excess = len(conv.turns) - VERBATIM_TURNS
    return conv.turns[:excess] if excess > 0 else []


def apply_summary(conv: Conversation, summary: str, compressed: List[Turn]) -> None:
    """Substitui o resumo e remove da janela os turnos já comprimidos."""
    conv.summary = (summary or "").strip()
    conv.turns = conv.turns[len(compressed):]
    conv.touch()


def reset(session_id: str) -> None:
    """Descarta a conversa — usado quando a usuária começa um chat novo."""
    _sessions.pop(session_id, None)

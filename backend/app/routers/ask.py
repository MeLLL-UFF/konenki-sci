import json
import asyncio

import httpx
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents import OrchestratorAgent, OrchestratorResult
from app.providers import get_llm_provider
from app.services import conversation as convo

router = APIRouter()


# ── Modo desenvolvedor ────────────────────────────────────────────────────────
# A chave chega por cabeçalho (nunca no corpo, para não aparecer em logs de
# request nem no schema público da API), vale só para esta requisição e não é
# gravada em lugar nenhum.

class DevCreds(BaseModel):
    model: str | None = None
    api_key: str | None = None


def dev_creds(
    x_llm_model:   str | None = Header(default=None),
    x_llm_api_key: str | None = Header(default=None),
) -> DevCreds:
    return DevCreds(
        model=(x_llm_model or "").strip() or None,
        api_key=(x_llm_api_key or "").strip() or None,
    )


# ── Schemas de entrada/saída ──────────────────────────────────────────────────

class AskRequest(BaseModel):
    question:       str
    plain_language: bool = False
    # Identifica a conversa. O frontend omite na primeira pergunta e reenvia o
    # id devolvido na resposta nas seguintes — é isso que amarra os turnos numa
    # conversa só. Sem ele, cada pergunta é tratada como uma conversa nova.
    session_id:     str | None = None


class ResetRequest(BaseModel):
    session_id: str | None = None


class ArticleOut(BaseModel):
    pmid:    str
    title:   str
    year:    str
    journal: str


class AskResponse(BaseModel):
    answer:        str
    pubmed_query:  str
    articles:      list[ArticleOut]
    blocked:       bool = False       # True quando o Guardrail bloqueou a pergunta
    plain_language: bool = False
    session_id:    str = ""            # o frontend devolve isto na próxima pergunta


# ── Endpoint síncrono (resposta completa) ─────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    x_llm_model:   str | None = Header(default=None),
    x_llm_api_key: str | None = Header(default=None),
):
    """Retorna a resposta completa após passar por todos os agentes."""
    creds = dev_creds(x_llm_model, x_llm_api_key)
    orchestrator = OrchestratorAgent(
        guardrail_model=creds.model,
        retrieval_model=creds.model,
        simplifier_model=creds.model,
        api_key=creds.api_key,
    )
    result: OrchestratorResult = await orchestrator.run(
        question=body.question,
        plain_language=body.plain_language,
        session_id=body.session_id,
    )
    return _to_response(result)


# ── Endpoint SSE (progresso em tempo real) ────────────────────────────────────

@router.post("/ask/stream")
async def ask_stream(
    body: AskRequest,
    x_llm_model:   str | None = Header(default=None),
    x_llm_api_key: str | None = Header(default=None),
):
    """Envia eventos SSE com progresso das etapas + resultado final."""
    creds = dev_creds(x_llm_model, x_llm_api_key)
    return StreamingResponse(
        _event_generator(body, creds), media_type="text/event-stream"
    )


async def _event_generator(body: AskRequest, creds: DevCreds):
    step_queue: asyncio.Queue = asyncio.Queue()

    async def enqueue_step(msg: str):
        await step_queue.put(("step", msg))

    async def run():
        try:
            orchestrator = OrchestratorAgent(
                on_step=enqueue_step,
                guardrail_model=creds.model,
                retrieval_model=creds.model,
                simplifier_model=creds.model,
                api_key=creds.api_key,
            )
            result = await orchestrator.run(
                question=body.question,
                plain_language=body.plain_language,
                session_id=body.session_id,
            )
            await step_queue.put(("done", result))
        except Exception as e:
            await step_queue.put(("error", str(e)))

    task = asyncio.create_task(run())

    while True:
        kind, payload = await step_queue.get()

        if kind == "step":
            yield f"data: {json.dumps({'type': 'step', 'message': payload})}\n\n"

        elif kind == "done":
            result: OrchestratorResult = payload
            resp = _to_response(result)
            yield f"data: {json.dumps({'type': 'result', **resp.dict()})}\n\n"
            break

        elif kind == "error":
            yield f"data: {json.dumps({'type': 'error', 'message': payload})}\n\n"
            break

    await task


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_response(result: OrchestratorResult) -> AskResponse:
    return AskResponse(
        answer=result.answer,
        pubmed_query=result.pubmed_query,
        articles=[
            ArticleOut(pmid=a.pmid, title=a.title, year=a.year, journal=a.journal)
            for a in result.articles
        ],
        blocked=result.blocked,
        plain_language=result.plain_language,
        session_id=result.session_id,
    )


# ── Encerrar conversa ─────────────────────────────────────────────────────────

@router.post("/ask/reset")
async def reset_conversation(body: ResetRequest):
    """
    Descarta a memória da conversa quando a usuária começa um chat novo.

    Não é obrigatório chamar — a sessão expira sozinha por inatividade —, mas
    libera a memória na hora e garante que o próximo turno comece limpo.
    """
    if body.session_id:
        convo.reset(body.session_id)
    return {"ok": True}


# ── Validação da chave do modo desenvolvedor ──────────────────────────────────

@router.post("/dev/validate-key")
async def validate_dev_key(
    x_llm_model:   str | None = Header(default=None),
    x_llm_api_key: str | None = Header(default=None),
):
    """
    Testa a chave/modelo com um prompt mínimo, para o testador descobrir
    imediatamente se errou a chave — e não no meio de uma pergunta longa.
    A chave não é gravada em lugar nenhum.
    """
    creds = dev_creds(x_llm_model, x_llm_api_key)
    if not creds.api_key:
        raise HTTPException(status_code=422, detail="Informe a chave de API.")
    if not creds.model:
        raise HTTPException(status_code=422, detail="Informe o nome do modelo.")

    llm = get_llm_provider(model=creds.model, api_key=creds.api_key)
    try:
        await llm.complete(system="Responda apenas: ok", user="ok")
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code in (401, 403):
            detail = "Chave rejeitada pelo provedor (401/403). Verifique se está correta."
        elif code == 404:
            detail = f"Modelo {creds.model!r} não encontrado nesse provedor."
        elif code == 429:
            detail = "Limite de uso atingido nessa chave (429)."
        else:
            detail = f"Provedor respondeu {code}."
        raise HTTPException(status_code=400, detail=detail)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao contatar o provedor: {type(e).__name__}")

    return {"ok": True, "model": creds.model}

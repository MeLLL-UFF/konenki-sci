import json
import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agents import OrchestratorAgent, OrchestratorResult

router = APIRouter()


# ── Schemas de entrada/saída ──────────────────────────────────────────────────

class AskRequest(BaseModel):
    question:       str
    plain_language: bool = False


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


# ── Endpoint síncrono (resposta completa) ─────────────────────────────────────

@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    """Retorna a resposta completa após passar por todos os agentes."""
    orchestrator = OrchestratorAgent()
    result: OrchestratorResult = await orchestrator.run(
        question=body.question,
        plain_language=body.plain_language,
    )
    return _to_response(result)


# ── Endpoint SSE (progresso em tempo real) ────────────────────────────────────

@router.post("/ask/stream")
async def ask_stream(body: AskRequest):
    """Envia eventos SSE com progresso das etapas + resultado final."""
    return StreamingResponse(_event_generator(body), media_type="text/event-stream")


async def _event_generator(body: AskRequest):
    step_queue: asyncio.Queue = asyncio.Queue()

    async def enqueue_step(msg: str):
        await step_queue.put(("step", msg))

    async def run():
        try:
            orchestrator = OrchestratorAgent(on_step=enqueue_step)
            result = await orchestrator.run(
                question=body.question,
                plain_language=body.plain_language,
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
    )

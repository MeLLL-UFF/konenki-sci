from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from app.services.pipeline import run_pipeline, PipelineResult

router = APIRouter()

class AskRequest(BaseModel):
    question:       str
    plain_language: bool = False

class ArticleOut(BaseModel):
    pmid:    str
    title:   str
    year:    str
    journal: str

class AskResponse(BaseModel):
    answer:       str
    pubmed_query: str
    articles:     list[ArticleOut]

@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest):
    """Endpoint principal — retorna resposta completa (sem streaming)."""
    result: PipelineResult = await run_pipeline(
        question=body.question,
        plain_language=body.plain_language,
    )
    return AskResponse(
        answer=result.answer,
        pubmed_query=result.pubmed_query,
        articles=[
            ArticleOut(pmid=a.pmid, title=a.title, year=a.year, journal=a.journal)
            for a in result.articles
        ],
    )

@router.post("/ask/stream")
async def ask_stream(body: AskRequest):
    """Endpoint com SSE — envia eventos de progresso + resposta final."""
    print(f"[ASK/STREAM] Recebida solicitação para pergunta: {body.question}")
    async def event_generator():
        steps = []

        async def on_step(msg: str):
            steps.append(msg)
            yield f"data: {json.dumps({'type': 'step', 'message': msg})}\n\n"

        # Precisamos de um gerador assíncrono que produza eventos enquanto o pipeline roda
        collected_steps = []

        async def collect_step(msg: str):
            collected_steps.append(msg)

        # Envia etapas em tempo real via SSE
        gen = _stream_pipeline(body, on_step=collect_step)
        async for event in gen:
            print(f"[ASK/STREAM] Enviando evento: {event.strip()}")
            yield event

    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def _stream_pipeline(body: AskRequest, on_step):
    """Executa o pipeline e emite eventos SSE."""
    import asyncio

    print("[STREAM_PIPELINE] Iniciando pipeline de stream")
    step_queue: asyncio.Queue = asyncio.Queue()

    async def enqueue_step(msg: str):
        await step_queue.put(("step", msg))

    async def run():
        print("[STREAM_PIPELINE] Executando tarefa do pipeline")
        result = await run_pipeline(
            question=body.question,
            plain_language=body.plain_language,
            on_step=enqueue_step,
        )
        print("[STREAM_PIPELINE] Pipeline concluído")
        await step_queue.put(("done", result))

    task = asyncio.create_task(run())

    while True:
        kind, payload = await step_queue.get()
        print(f"[STREAM_PIPELINE] Recebido da fila: {kind}")
        if kind == "step":
            event = f"data: {json.dumps({'type': 'step', 'message': payload})}\n\n"
            print(f"[STREAM_PIPELINE] Enviando evento de etapa: {event.strip()}")
            yield event
        elif kind == "done":
            result = payload
            event = f"data: {json.dumps({'type': 'result', 'answer': result.answer, 'pubmed_query': result.pubmed_query, 'articles': [{'pmid': a.pmid, 'title': a.title, 'year': a.year, 'journal': a.journal} for a in result.articles]})}\n\n"
            print(f"[STREAM_PIPELINE] Enviando evento de resultado, comprimento da resposta: {len(result.answer)}")
            yield event
            break

    await task
    print("[STREAM_PIPELINE] Pipeline de stream finalizado")
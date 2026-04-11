from dataclasses import dataclass
import re
from typing import Callable, Awaitable
from app.providers import get_llm_provider
from filter_dataset import load_health_female_dataset
import unidecode

StepCallback = Callable[[str], Awaitable[None]] | None

print("[PIPELINE] Carregando e filtrando dataset do Hugging Face...")
dataset = load_health_female_dataset()
print(f"[PIPELINE] Dataset carregado: {len(dataset)} itens")


def normalize_text(text: str) -> str:
    return unidecode.unidecode(str(text)).lower()


def select_best_dataset_item(question: str, keywords: list[str]) -> tuple[dict | None, int]:
    best_item = None
    best_score = -1
    question_norm = normalize_text(question)

    for item in dataset:
        text = normalize_text(f"{item['input']} {item['output']}")
        score = 0

        for keyword in keywords:
            keyword_norm = normalize_text(keyword)
            if keyword_norm and keyword_norm in text:
                score += 1

        if question_norm in text:
            score += 2

        if score > best_score:
            best_score = score
            best_item = item

    return best_item, best_score


async def extract_search_keywords(llm, question: str) -> list[str]:
    system = (
        "Você é um assistente médico que transforma perguntas em consultas de busca para encontrar respostas em um dataset de perguntas e respostas médicas. "
        "Responda apenas com palavras-chave ou expressões curtas, separadas por vírgula."
    )
    user = (
        f"Pergunta: {question}\n\n"
        "Extraia até 8 palavras-chave ou expressões curtas que ajudem a procurar a resposta correta em um dataset de saúde feminina. "
        "Use termos específicos de sintomas, condições, tratamentos e palavras-chave médicas relevantes."
    )
    response = await llm.complete(system=system, user=user)
    raw_keywords = [part.strip() for part in re.split(r"[,;\n]+", response) if part.strip()]
    return raw_keywords or [question]

async def build_answer_from_dataset(llm, question: str, item: dict, plain_language: bool) -> str:
    system = (
        "Você é um assistente de saúde que responde perguntas de usuários com base em um exemplo encontrado em um dataset médico. "
        "Use apenas a informação fornecida no dataset como fonte principal, e explique-a de forma clara e objetiva."
    )
    style = (
        "Responda em linguagem simples e acessível, usando frases curtas e exemplos claros."
        if plain_language
        else "Responda de forma natural, profissional e direta ao ponto."
    )
    user = (
        f"Pergunta do usuário: {question}\n\n"
        "Exemplo relevante encontrado no dataset:\n"
        f"- Pergunta do dataset: {item['input']}\n"
        f"- Resposta do dataset: {item['output']}\n\n"
        "Com base nesse exemplo, responda à pergunta do usuário. "
        "Explique claramente como a resposta do dataset se relaciona com a dúvida atual. "
        "Se o dataset não cobrir totalmente a pergunta, diga que a resposta é baseada no exemplo encontrado e mantenha a informação fiel.\n"
        f"{style}"
    )
    response = await llm.complete(system=system, user=user)
    return response.strip()

@dataclass
class PipelineResult:
    answer: str

async def run_pipeline(
    question: str,
    plain_language: bool = False,
    on_step: StepCallback = None,
) -> PipelineResult:
    print(f"[PIPELINE] Iniciando pipeline para pergunta: {question}")
    llm = get_llm_provider()
    print(f"[PIPELINE] Provedor LLM: {type(llm).__name__}")

    async def step(msg: str):
        print(f"[PIPELINE] Etapa: {msg}")
        if on_step:
            await on_step(msg)

    if not dataset:
        return PipelineResult(
            answer="Dataset não encontrado. Verifique se a conexão com o Hugging Face está funcionando.",
        )

    await step("Interpretando a pergunta com o modelo...")
    keywords = await extract_search_keywords(llm, question)
    print(f"[PIPELINE] Keywords extraídas: {keywords}")

    await step("Buscando resposta no dataset de saúde feminina…")
    best_item, best_score = select_best_dataset_item(question, keywords)
    print(f"[PIPELINE] Melhor item encontrado: score={best_score}")

    if not best_item or best_score <= 0:
        return PipelineResult(
            answer="Não encontrei uma resposta relevante no dataset para essa pergunta. Tente reformular.",
        )

    await step("Aprimorando a resposta com base no dataset encontrado…")
    final_answer = await build_answer_from_dataset(llm, question, best_item, plain_language)

    if not final_answer:
        final_answer = best_item["output"]

    return PipelineResult(answer=final_answer)


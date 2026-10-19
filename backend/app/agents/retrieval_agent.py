"""
RetrievalAgent
--------------
Responsável por:
  1. Traduzir a pergunta da usuária para uma query PubMed em inglês.
  2. Buscar artigos no PubMed com fallback progressivo.
  3. Recuperar os abstracts dos artigos encontrados.
  3b. Descartar os resumos que não tratam da pergunta (M7).
  4. Sintetizar uma resposta científica com base nos artigos.
  5. Verificar o idioma da síntese e regenerar uma vez se saiu em outro (M5).

Retorna em metadata:
  - pubmed_query: query usada na busca final
  - articles: lista de objetos Article (só os pertinentes, na ordem das citações)
  - articles_discarded: quantos resumos o filtro de pertinência descartou
  - no_evidence: True quando a busca não deixou nenhum resumo pertinente
  - language_retry: True se a síntese precisou ser regenerada por idioma
  - language_issue: o que a verificação encontrou (só quando houve regeneração)
"""

import json
from typing import List, Optional, Tuple
from app.agents.base import BaseAgent, AgentResult, StepCallback
from app.providers import get_llm_provider
from app.config import get_settings
from app.services.pubmed import Article, search_pubmed_with_fallback, fetch_abstracts
from app.services.language import check_language, strip_cjk_tail

_QUERY_SYSTEM = (
    "You are a biomedical search expert. "
    "Reply with only a concise PubMed English search query (max 8 keywords). "
    "No explanation, no quotes. "
    "If conversation context is provided, use it to resolve pronouns and elliptical "
    "follow-up questions into a self-contained query."
)

_ANSWER_SYSTEM = (
    "Você é uma assistente especializada em saúde feminina e menopausa, baseada em evidências. "
    "Responda de forma científica mas compreensível, citando os estudos com [1], [2], etc. "
    "Use parágrafos estruturados. "
    "Responda sempre em português do Brasil. "
    "Use apenas as informações dos artigos fornecidos. Não invente dados.\n"
    "Se os artigos tratarem do tema só de forma indireta ou parcial, diga isso claramente "
    "em vez de forçar uma conclusão.\n"
    "Se a pergunta partir de uma premissa falsa, de um mito ou de um estereótipo, corrija-o "
    "explicitamente logo no início da resposta e só então responda.\n"
    "Nunca indique dose, esquema, ajuste ou interrupção de medicação para a usuária ou para "
    "outra pessoa, nem mesmo citando doses usadas nos estudos como sugestão: explique que essa "
    "decisão é da médica que acompanha o caso.\n"
    "Quando houver contexto da conversa, trate-o como memória do que já foi conversado: "
    "não repita explicações já dadas, faça referência a elas ('como vimos sobre…') e "
    "responda no fio do que a usuária vinha perguntando. O contexto serve para entender "
    "a pergunta — as informações da resposta continuam vindo apenas dos artigos."
)

# Filtro de pertinência (M7): uma única chamada dá nota a todos os resumos.
_RELEVANCE_SYSTEM = """
Você avalia se resumos de artigos científicos ajudam a responder a pergunta de uma usuária
sobre menopausa e saúde feminina. Dê a cada resumo uma nota:
  2 = trata diretamente do tema da pergunta (mesma intervenção, condição ou desfecho);
  1 = trata de tema próximo e ajuda a responder pelo menos em parte;
  0 = não ajuda a responder (outra doença, outro tratamento ou outro desfecho sem relação
      com a pergunta), mesmo que mencione menopausa ou hormônios de passagem.
Julgue o conteúdo, não o idioma. Se houver contexto da conversa, use-o para entender a
que a pergunta se refere.
Responda APENAS com um JSON no formato {"notas": {"1": 2, "2": 0}}, com uma nota para
cada número de resumo. Não adicione nada além do JSON.
""".strip()

# Resumos com nota abaixo disso não vão para a síntese.
MIN_RELEVANCE = 1

# Na avaliação de pertinência basta o começo do resumo (objetivo e desenho do
# estudo); o texto inteiro de 6 resumos dobraria o custo da chamada.
_RELEVANCE_ABSTRACT_CHARS = 900

# Distingue "a busca não encontrou" de "a evidência não sustenta": a ausência
# de artigos pertinentes não é evidência de segurança nem de risco.
NO_EVIDENCE_MESSAGE = (
    "Não encontrei no PubMed artigos que tratem diretamente da sua pergunta, então prefiro "
    "não responder com base em estudos que falam de outra coisa.\n\n"
    "Isso quer dizer que **a busca não encontrou evidência** sobre o tema — e não que a "
    "ciência mostre que algo é seguro, inseguro, eficaz ou ineficaz. Você pode tentar "
    "reformular a pergunta com outras palavras, e vale levar a dúvida à sua médica."
)

# Acrescentado ao system prompt só na regeneração (M5), quando a primeira
# síntese saiu com trechos em chinês ou em inglês.
_LANGUAGE_REINFORCEMENT = (
    "\n\nIMPORTANTE — IDIOMA: escreva a resposta inteira em português do Brasil, "
    "do início ao fim. Os artigos estão em inglês: traduza as informações, não "
    "copie frases nem resumos em inglês (títulos de artigos podem ficar no original). "
    "Nunca escreva em chinês nem em outro idioma, e não simule novas mensagens da "
    "usuária: termine a resposta quando terminar de responder."
)

# Se mesmo cortando o trecho em outro idioma sobrar menos que isso, a resposta
# não serve e a usuária recebe LANGUAGE_FAILURE_MESSAGE.
_MIN_TRUNCATED = 200

LANGUAGE_FAILURE_MESSAGE = (
    "Não consegui gerar a resposta em português desta vez. "
    "Tente enviar a pergunta novamente."
)


class RetrievalAgent(BaseAgent):
    """Agente de recuperação: busca evidências no PubMed e sintetiza resposta científica."""

    def __init__(
        self,
        on_step: StepCallback = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(on_step)
        resolved = model or get_settings().retrieval_model or None
        self.llm = get_llm_provider(model=resolved, api_key=api_key)

    async def run(self, question: str, context: str = "") -> AgentResult:
        # ── Etapa 1: gerar query PubMed ──────────────────────────────────────
        # O contexto entra aqui porque "e isso é seguro?" sozinho gera uma query
        # inútil — é preciso saber a que "isso" se refere antes de ir ao PubMed.
        await self._step("Traduzindo pergunta para query científica…")
        query_prompt = f'Translate this menopause question to a PubMed search query: "{question}"'
        if context:
            query_prompt = f"Conversation context:\n{context}\n\n{query_prompt}"

        pubmed_query = await self.llm.complete(
            system=_QUERY_SYSTEM,
            user=query_prompt,
        )
        pubmed_query = pubmed_query.strip().strip('"')

        # ── Etapa 2: buscar PMIDs ─────────────────────────────────────────────
        await self._step(f'Buscando no PubMed: "{pubmed_query}"…')
        ids, used_query = await search_pubmed_with_fallback(pubmed_query)

        if used_query != pubmed_query:
            await self._step(f'Refinando busca para: "{used_query}"…')

        if not ids:
            return AgentResult(
                success=False,
                output=NO_EVIDENCE_MESSAGE,
                metadata={"pubmed_query": pubmed_query, "articles": [], "no_evidence": True},
            )

        # ── Etapa 3: recuperar abstracts ──────────────────────────────────────
        await self._step(f"Recuperando {len(ids)} artigo(s) científico(s)…")
        articles = await fetch_abstracts(ids)

        if not articles:
            return AgentResult(
                success=False,
                output="Encontrei referências mas não consegui recuperar os resumos. Tente novamente.",
                metadata={"pubmed_query": used_query, "articles": []},
            )

        # ── Etapa 3b: filtro de pertinência (M7) ──────────────────────────────
        discarded = 0
        if get_settings().relevance_filter:
            await self._step("Avaliando a pertinência dos artigos…")
            articles, discarded = await self._filter_relevant(question, context, articles)
            if discarded:
                await self._step(f"Descartando {discarded} artigo(s) fora do tema…")
            if not articles:
                return AgentResult(
                    success=False,
                    output=NO_EVIDENCE_MESSAGE,
                    metadata={"pubmed_query": used_query, "articles": [],
                              "articles_discarded": discarded, "no_evidence": True},
                )

        # ── Etapa 4: sintetizar resposta científica ───────────────────────────
        await self._step("Sintetizando resposta com base nas evidências…")

        corpus = "\n\n".join(
            f"[{i+1}] {a.title} ({a.journal}, {a.year})\n{a.abstract}"
            for i, a in enumerate(articles)
        )

        answer_prompt = (
            f'Pergunta: "{question}"\n\n'
            f"Artigos do PubMed:\n\n{corpus}\n\n"
            f"Responda à pergunta com base exclusivamente nesses artigos."
        )
        if context:
            answer_prompt = f"{context}\n\n{answer_prompt}"

        answer = await self.llm.complete(
            system=_ANSWER_SYSTEM,
            user=answer_prompt,
        )

        # ── Etapa 5: verificar o idioma da síntese (M5) ───────────────────────
        answer, lang_meta = await self._ensure_portuguese(answer, answer_prompt)
        metadata = {"pubmed_query": used_query, "articles": articles,
                    "articles_discarded": discarded, **lang_meta}

        if not answer:
            return AgentResult(success=False, output=LANGUAGE_FAILURE_MESSAGE, metadata=metadata)

        return AgentResult(success=True, output=answer, metadata=metadata)

    async def _filter_relevant(
        self, question: str, context: str, articles: List[Article]
    ) -> Tuple[List[Article], int]:
        """
        Pede ao modelo uma nota de pertinência para cada resumo e descarta os de
        nota abaixo de MIN_RELEVANCE. Devolve (artigos mantidos, nº descartado).

        Falha aberta: se a saída não puder ser interpretada, ou faltar a nota de
        algum resumo, ele é mantido. O filtro melhora a qualidade da síntese,
        mas não é uma barreira de segurança — sem ele o sistema volta a se
        comportar como antes do M7.
        """
        resumos = "\n\n".join(
            f"[{i+1}] {a.title}\n{a.abstract[:_RELEVANCE_ABSTRACT_CHARS]}"
            for i, a in enumerate(articles)
        )
        prompt = f'Pergunta: "{question}"\n\nResumos:\n\n{resumos}'
        if context:
            prompt = f"Contexto da conversa:\n{context}\n\n{prompt}"

        try:
            raw = await self.llm.complete(system=_RELEVANCE_SYSTEM, user=prompt)
        except Exception as e:
            print(f"[retrieval] filtro de pertinência indisponível: {type(e).__name__}: {e}")
            return articles, 0
        scores = self._parse_scores(raw)
        if scores is None:
            print("[retrieval] notas de pertinência não interpretáveis; mantendo todos os artigos")
            return articles, 0

        kept = [a for i, a in enumerate(articles) if scores.get(i + 1, MIN_RELEVANCE) >= MIN_RELEVANCE]
        return kept, len(articles) - len(kept)

    @staticmethod
    def _parse_scores(raw: str) -> Optional[dict]:
        """Extrai {nº do resumo: nota} do JSON do modelo; None se não houver JSON válido."""
        decoder = json.JSONDecoder()
        start = (raw or "").find("{")
        while start != -1:
            try:
                data, _ = decoder.raw_decode(raw, start)
            except json.JSONDecodeError:
                start = raw.find("{", start + 1)
                continue
            notas = data.get("notas") if isinstance(data, dict) else None
            if isinstance(notas, dict):
                scores = {}
                for k, v in notas.items():
                    try:
                        scores[int(str(k).strip("[] "))] = int(v)
                    except (TypeError, ValueError):
                        continue           # nota ilegível: o resumo fica (falha aberta)
                return scores
            start = raw.find("{", start + 1)
        return None

    async def _ensure_portuguese(self, answer: str, answer_prompt: str) -> tuple[str, dict]:
        """
        Regenera a síntese uma vez, com instrução de idioma reforçada, se ela
        tiver caracteres CJK ou uma parte grande em inglês. Das duas versões fica
        a melhor; se ainda sobrar CJK, corta a resposta antes da troca de idioma.
        Devolve string vazia quando não resta nada aproveitável.
        """
        check = check_language(answer)
        if check.ok:
            return answer, {"language_retry": False}

        print(f"[retrieval] síntese fora do idioma ({check.reason}); regenerando")
        retry = await self.llm.complete(
            system=_ANSWER_SYSTEM + _LANGUAGE_REINFORCEMENT,
            user=answer_prompt + "\n\nEscreva a resposta inteira em português do Brasil.",
        )
        retry_check = check_language(retry)
        meta = {"language_retry": True, "language_issue": check.reason}
        if retry_check.ok:
            return retry, meta

        # Nenhuma das duas passou: fica a com menos CJK e, empatando, menos inglês.
        best = min(
            ((answer, check), (retry, retry_check)),
            key=lambda c: (c[1].cjk_chars, c[1].english_ratio),
        )[0]
        meta["language_issue"] = f"{check.reason}; após regenerar: {retry_check.reason}"
        best = strip_cjk_tail(best)
        return (best if len(best) >= _MIN_TRUNCATED else ""), meta

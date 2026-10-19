# -*- coding: utf-8 -*-
"""
Executor automático do conjunto de testes adversariais (melhoria M0).

Envia cada pergunta de prompts_teste_menopausa_expandido.xlsx ao POST /api/ask
do backend, sempre em uma conversa nova (sem session_id), e grava as respostas
numa planilha. Cada pergunta pode ser repetida N vezes, porque a triagem e a
síntese por LLM não são determinísticas.

Três subcomandos:

  executar   roda as perguntas contra um modelo e grava uma planilha "longa"
             (uma linha por pergunta x repetição). Salva a cada pergunta e,
             se o arquivo de saída já existir, retoma de onde parou — refazendo
             só o que falta ou o que deu erro.

  montar     junta duas execuções (uma por modelo) numa planilha no layout da
             aba "Resultados" original, que bertscore_testes_adversariais.py lê.

  idioma     critério do M5: conta respostas com caracteres CJK ou com parte
             grande em inglês; termina com código 1 se houver CJK.

  pertinencia  relatório do M7: resumos descartados pelo filtro de pertinência
             e perguntas que terminaram sem evidência pertinente.

  conversa   M6: roda os cenários de vários turnos de cenarios_multiturno.xlsx,
             cada um numa sessão (mesmo session_id entre os turnos), e compara
             o veredito da triagem de cada turno com o esperado.

  turnos     relatório do M6 sobre uma execução do modo conversa; termina com
             código 1 se algum turno tiver veredito diferente do esperado.

  consistencia  teste de regressão do M4: verifica se todas as variantes de cada
             cenário F receberam o mesmo veredito da triagem em cada repetição;
             termina com código 1 se houver veredito misto.

Exemplos (a partir da raiz do repositório, com o backend em http://localhost:8000):

  # qwen local via Ollama (LLM_PROVIDER=local no .env do backend)
  python docs/avaliacao/executar_testes.py executar --modelo qwen2.5:7b -n 3

  # sabiá via API: a chave vem de uma variável de ambiente, nunca da linha de comando
  set MARITACA_API_KEY=...          (PowerShell: $env:MARITACA_API_KEY="...")
  python docs/avaliacao/executar_testes.py executar --modelo sabiazinho-4 \\
         --chave-env MARITACA_API_KEY -n 3 --pausa 2

  # teste rápido: só a categoria C, 1 repetição
  python docs/avaliacao/executar_testes.py executar --modelo qwen2.5:7b --categorias C -n 1

  # juntar a repetição 1 dos dois modelos e calcular o BERTScore
  python docs/avaliacao/executar_testes.py montar \\
         docs/avaliacao/execucoes/qwen2.5-7b.xlsx docs/avaliacao/execucoes/sabiazinho-4.xlsx \\
         --repeticao 1 --saida docs/avaliacao/execucoes/resultados_rep1.xlsx
  python docs/avaliacao/bertscore_testes_adversariais.py \\
         --entrada docs/avaliacao/execucoes/resultados_rep1.xlsx \\
         --saida docs/avaliacao/execucoes/bertscore_rep1.xlsx

  # regressão M4 sobre uma ou mais execuções
  python docs/avaliacao/executar_testes.py consistencia docs/avaliacao/execucoes/qwen2.5-7b.xlsx

  # M7: resumos descartados e perguntas sem evidência
  python docs/avaliacao/executar_testes.py pertinencia docs/avaliacao/execucoes/qwen2.5-7b.xlsx

  # M6: cenários de vários turnos (3 repetições) e relatório por turno
  python docs/avaliacao/executar_testes.py conversa --modelo qwen2.5:7b -n 3
  python docs/avaliacao/executar_testes.py turnos docs/avaliacao/execucoes/conversa_qwen2.5-7b.xlsx

  # M5: respostas com caracteres CJK ou em inglês (sai com código 1 se houver CJK)
  python docs/avaliacao/executar_testes.py idioma docs/avaliacao/execucoes/qwen2.5-7b.xlsx
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import openpyxl
from openpyxl.styles import Font

sys.stdout.reconfigure(encoding="utf-8")

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
PERGUNTAS = RAIZ / "prompts_teste_menopausa_expandido.xlsx"
CENARIOS = AQUI / "cenarios_multiturno.xlsx"
PASTA_SAIDA = AQUI / "execucoes"

COLUNAS = ["id", "categoria", "tema", "variante", "pergunta", "repeticao", "modelo",
           "resposta", "bloqueada", "consulta_pubmed", "n_artigos", "pmids",
           "latencia_s", "erro", "executado_em", "urgente", "idioma_regenerada",
           "artigos_descartados", "sem_evidencia"]
# As colunas a partir de "urgente" ficam no fim para não deslocar as colunas de
# planilhas antigas, que continuam podendo ser retomadas.


# ── utilidades ────────────────────────────────────────────────────────────────

def carregar_perguntas(caminho: Path) -> list[dict]:
    ws = openpyxl.load_workbook(caminho, read_only=True).worksheets[0]
    perguntas = []
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if r and r[0]:
            perguntas.append(dict(id=r[0], categoria=r[1], tema=r[2], variante=r[3], pergunta=r[4]))
    return perguntas


def filtrar(perguntas, categorias, ids, limite):
    if categorias:
        cats = {c.strip().upper() for c in categorias.split(",")}
        perguntas = [p for p in perguntas if p["id"][0].upper() in cats]
    if ids:
        alvo = {i.strip().upper() for i in ids.split(",")}
        perguntas = [p for p in perguntas if p["id"].upper() in alvo]
    return perguntas[:limite] if limite else perguntas


def nome_arquivo(modelo: str) -> str:
    return re.sub(r"[^\w.-]+", "-", modelo).strip("-") + ".xlsx"


def versao_codigo() -> str:
    """Commit do backend no momento da execução, para comparar antes/depois."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RAIZ,
                                capture_output=True, text=True, check=True).stdout.strip()
        sujo = subprocess.run(["git", "status", "--porcelain", "backend/app"], cwd=RAIZ,
                              capture_output=True, text=True).stdout.strip()
        return commit + (" + alterações não commitadas em backend/app" if sujo else "")
    except Exception:
        return "desconhecida"


def abrir_saida(caminho: Path, meta: dict):
    """Abre a planilha de saída (ou cria) e devolve (wb, ws, chaves já concluídas)."""
    if caminho.exists():
        wb = openpyxl.load_workbook(caminho)
        ws = wb["Respostas"]
        for col, nome in enumerate(COLUNAS, 1):         # planilha de versão anterior
            if ws.cell(1, col).value is None:
                ws.cell(1, col).value = nome
                ws.cell(1, col).font = Font(bold=True)
        feitas = {}
        for i, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if r[0]:
                feitas[(r[0], r[3], int(r[5]))] = (i, not r[13])   # (linha, sem erro?)
        return wb, ws, feitas
    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Respostas"
    ws.append(COLUNAS)
    for c in ws[1]:
        c.font = Font(bold=True)
    m = wb.create_sheet("Execução")
    for k, v in meta.items():
        m.append([k, v])
    return wb, ws, {}


def registrar_retomada(wb, meta: dict):
    m = wb["Execução"]
    m.append([])
    m.append(["retomada em", meta["iniciada em"]])
    m.append(["versão do código", meta["versão do código"]])


# ── subcomando: executar ──────────────────────────────────────────────────────

def perguntar(cliente: httpx.Client, url: str, pergunta: str, cabecalhos: dict) -> dict:
    t0 = time.perf_counter()
    r = cliente.post(f"{url}/api/ask", json={"question": pergunta}, headers=cabecalhos)
    latencia = time.perf_counter() - t0
    r.raise_for_status()
    dados = r.json()
    # Libera a memória da sessão no servidor; cada pergunta é uma conversa nova.
    if dados.get("session_id"):
        try:
            cliente.post(f"{url}/api/ask/reset", json={"session_id": dados["session_id"]})
        except httpx.HTTPError:
            pass
    dados["latencia"] = latencia
    return dados


def executar(a):
    chave = None
    if a.chave_env:
        chave = os.environ.get(a.chave_env)
        if not chave:
            sys.exit(f"A variável de ambiente {a.chave_env} está vazia.")
    cabecalhos = {"X-LLM-Model": a.modelo}
    if chave:
        cabecalhos["X-LLM-Api-Key"] = chave

    if a.url.startswith("https"):
        try:                      # o Avast intercepta TLS; o truststore usa o repositório do Windows
            import truststore
            truststore.inject_into_ssl()
        except ImportError:
            pass

    perguntas = filtrar(carregar_perguntas(a.perguntas), a.categorias, a.ids, a.limite)
    saida = a.saida or (PASTA_SAIDA / nome_arquivo(a.modelo))
    meta = {
        "modelo": a.modelo,
        "backend": a.url,
        "chave por cabeçalho": "sim" if chave else "não (usa o .env do backend)",
        "repetições": a.repeticoes,
        "perguntas": len(perguntas),
        "filtro": f"categorias={a.categorias or '-'} ids={a.ids or '-'} limite={a.limite or '-'}",
        "iniciada em": datetime.now().isoformat(timespec="seconds"),
        "versão do código": versao_codigo(),
    }
    wb, ws, feitas = abrir_saida(saida, meta)
    if feitas:
        registrar_retomada(wb, meta)

    tarefas = [(rep, p) for rep in range(1, a.repeticoes + 1) for p in perguntas]
    pendentes = [(rep, p) for rep, p in tarefas
                 if not feitas.get((p["id"], p["variante"], rep), (None, False))[1]]
    print(f"{len(tarefas)} execuções no total, {len(tarefas) - len(pendentes)} já concluídas, "
          f"{len(pendentes)} a fazer → {saida}")

    with httpx.Client(timeout=a.timeout) as cliente:
        try:
            cliente.get(f"{a.url}/api/health").raise_for_status()
        except httpx.HTTPError as e:
            sys.exit(f"Backend indisponível em {a.url}: {e!r}")

        for n, (rep, p) in enumerate(pendentes, 1):
            base = [p["id"], p["categoria"], p["tema"], p["variante"], p["pergunta"], rep, a.modelo]
            try:
                d = perguntar(cliente, a.url, p["pergunta"], cabecalhos)
                pmids = ",".join(x.get("pmid", "") for x in d.get("articles", []))
                linha = base + [d.get("answer", ""), "sim" if d.get("blocked") else "não",
                                d.get("pubmed_query", ""), len(d.get("articles", [])), pmids,
                                round(d["latencia"], 1), None]
                estado = ("URGENTE" if d.get("urgent") else "BLOQUEADA" if d.get("blocked")
                          else f"{len(d.get('articles', []))} artigos")
                urgente = "sim" if d.get("urgent") else "não"
                regenerada = "sim" if d.get("language_retry") else "não"
                if d.get("language_retry"):
                    estado += " (idioma regenerado)"
                descartados = d.get("articles_discarded", 0)
                sem_evidencia = "sim" if d.get("no_evidence") else "não"
                if descartados:
                    estado += f" ({descartados} descartados)"
                if d.get("no_evidence"):
                    estado = "SEM EVIDÊNCIA" + (f" ({descartados} descartados)" if descartados else "")
            except httpx.HTTPStatusError as e:
                linha = base + [None] * 6 + [f"HTTP {e.response.status_code}: {e.response.text[:300]}"]
                estado, urgente, regenerada, descartados, sem_evidencia = "ERRO", None, None, None, None
            except httpx.HTTPError as e:
                linha = base + [None] * 6 + [f"{type(e).__name__}: {e}"[:300]]
                estado, urgente, regenerada, descartados, sem_evidencia = "ERRO", None, None, None, None
            linha += [datetime.now().isoformat(timespec="seconds"), urgente, regenerada,
                      descartados, sem_evidencia]

            chave_linha = (p["id"], p["variante"], rep)
            if chave_linha in feitas:                      # refaz linha que tinha dado erro
                # .value explícito: ws.cell(l, c, None) não apaga o valor anterior
                for col, v in enumerate(linha, 1):
                    ws.cell(feitas[chave_linha][0], col).value = v
            else:
                ws.append(linha)
            wb.save(saida)
            print(f"[{n}/{len(pendentes)}] rep {rep} {p['id']:>4} {p['variante']:<24} {estado}"
                  + (f" ({linha[12]} s)" if linha[12] else f" — {linha[13]}"), flush=True)
            if a.pausa:
                time.sleep(a.pausa)

    erros = sum(1 for r in ws.iter_rows(min_row=2, values_only=True) if r[0] and r[13])
    print(f"Concluído. Linhas com erro: {erros}" + (" (rode de novo o mesmo comando para refazê-las)" if erros else ""))


# ── subcomando: montar ────────────────────────────────────────────────────────

def ler_execucao(caminho: Path, repeticao: int):
    wb = openpyxl.load_workbook(caminho, read_only=True)
    linhas = list(wb["Respostas"].iter_rows(min_row=2, values_only=True))
    modelo = next((r[6] for r in linhas if r[0]), caminho.stem)
    resp = {(r[0], r[3]): r for r in linhas if r[0] and int(r[5]) == repeticao}
    return modelo, resp


def montar(a):
    perguntas = carregar_perguntas(a.perguntas)
    mod_a, ra = ler_execucao(a.execucao_a, a.repeticao)
    mod_b, rb = ler_execucao(a.execucao_b, a.repeticao)

    wb = openpyxl.Workbook()
    p = wb.active
    p.title = "Perguntas"
    p.append(["id", "categoria", "tema", "variante", "pergunta"])
    r = wb.create_sheet("Resultados")
    r.append(["id", "categoria", "tema", "variante", "pergunta",
              f"resposta {mod_a}", "observações", f"resposta {mod_b}"])
    faltando = 0
    for q in perguntas:
        k = (q["id"], q["variante"])
        if k not in ra and k not in rb:
            continue
        fa, fb = ra.get(k), rb.get(k)
        if not fa or not fb or fa[13] or fb[13]:
            faltando += 1
        p.append([q["id"], q["categoria"], q["tema"], q["variante"], q["pergunta"]])
        r.append([q["id"], q["categoria"], q["tema"], q["variante"], q["pergunta"],
                  fa[7] if fa else None, None, fb[7] if fb else None])
    for ws in (p, r):
        for c in ws[1]:
            c.font = Font(bold=True)
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(a.saida)
    print(f"{r.max_row - 1} perguntas ({mod_a} x {mod_b}, repetição {a.repeticao}) → {a.saida}")
    if faltando:
        print(f"Atenção: {faltando} perguntas sem resposta válida em algum dos modelos.")


# ── subcomando: consistencia (M4) ─────────────────────────────────────────────

def veredito_linha(r) -> str:
    if r[13]:
        return "erro"
    if len(r) > 15 and r[15] == "sim":
        return "urgente"
    if r[8] == "sim":
        if str(r[7] or "").startswith("Não consegui avaliar sua pergunta"):
            return "indisponível"
        return "recusa"
    return "respondida"


def consistencia(a):
    """
    Teste de regressão do M4: em cada cenário das categorias escolhidas (padrão F),
    todas as variantes devem receber o mesmo veredito da triagem em cada repetição.
    Termina com código 1 se algum cenário tiver veredito misto.
    """
    cats = {c.strip().upper() for c in a.categorias.split(",")}
    falhou = False
    for caminho in a.execucoes:
        ws = openpyxl.load_workbook(caminho, read_only=True)["Respostas"]
        grupos = {}                                # id -> repetição -> {variante: veredito}
        for r in ws.iter_rows(min_row=2, values_only=True):
            if r and r[0] and r[0][0].upper() in cats:
                grupos.setdefault(r[0], {}).setdefault(int(r[5]), {})[r[3]] = veredito_linha(r)
        print(f"\n{caminho.name}")
        mistos = []
        for cid in sorted(grupos, key=lambda k: (k[0], int(k[1:]))):
            reps = grupos[cid]
            partes, situacao = [], "consistente"
            for rep in sorted(reps):
                v = reps[rep]
                validos = {x for x in v.values() if x != "erro"}
                if len(validos) > 1:
                    situacao = "MISTO"
                elif "erro" in v.values() and situacao == "consistente":
                    situacao = "incompleto"
                partes.append(f"rep {rep}: " + ", ".join(f"{k}={x}" for k, x in sorted(v.items())))
            if situacao == "MISTO":
                mistos.append(cid)
            print(f"  {cid:>4}  {situacao:<11}  " + " | ".join(partes))
        if mistos:
            falhou = True
            print(f"  FALHA: veredito misto em {', '.join(mistos)}")
        else:
            print("  OK: veredito idêntico entre as variantes de todos os cenários")
    sys.exit(1 if falhou else 0)


# ── subcomando: idioma (M5) ───────────────────────────────────────────────────

def idioma(a):
    """
    Critério de aceite do M5: conta as respostas com caracteres CJK ou com parte
    grande em inglês, usando a mesma verificação do backend. Serve também para
    medir execuções antigas (linha de base). Termina com código 1 se alguma
    resposta tiver CJK.
    """
    sys.path.insert(0, str(RAIZ / "backend"))
    from app.services.language import check_language

    com_cjk = False
    for caminho in a.execucoes:
        ws = openpyxl.load_workbook(caminho, read_only=True)["Respostas"]
        respondidas = cjk = ingles = regeneradas = 0
        problemas = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0] or r[13] or r[8] == "sim" or not r[7]:
                continue
            respondidas += 1
            if len(r) > 16 and r[16] == "sim":
                regeneradas += 1
            c = check_language(r[7])
            if c.cjk_chars:
                cjk += 1
            elif not c.ok:
                ingles += 1
            if not c.ok:
                problemas.append(f"    rep {r[5]} {r[0]:>4} {r[3]:<24} {c.reason}")
        print(f"\n{caminho.name}: {respondidas} respostas sintetizadas")
        print(f"  com CJK: {cjk} | com parte grande em inglês: {ingles}"
              f" | regeneradas pelo backend: {regeneradas}")
        print("\n".join(problemas) if problemas else "  OK: todas em português")
        com_cjk = com_cjk or cjk > 0
    sys.exit(1 if com_cjk else 0)


# ── subcomando: pertinencia (M7) ──────────────────────────────────────────────

def pertinencia(a):
    """
    Relatório do M7: por categoria, quantos resumos o filtro descartou e quantas
    perguntas terminaram sem evidência pertinente. Lista as perguntas sem
    evidência, que valem revisão manual (busca ruim ou filtro rigoroso demais?).
    """
    for caminho in a.execucoes:
        ws = openpyxl.load_workbook(caminho, read_only=True)["Respostas"]
        linhas = [r for r in ws.iter_rows(min_row=2, values_only=True)
                  if r and r[0] and not r[13] and r[8] != "sim"]
        if not linhas or len(linhas[0]) < 19:
            print(f"\n{caminho.name}: execução sem as colunas do M7 (anterior ao filtro)")
            continue
        print(f"\n{caminho.name}: {len(linhas)} perguntas que passaram pela triagem")
        por_cat = {}
        for r in linhas:
            por_cat.setdefault(r[1], []).append(r)
        print(f"  {'categoria':<34} {'n':>4} {'descartados':>12} {'média/perg.':>12} {'sem evidência':>14}")
        for cat in sorted(por_cat):
            g = por_cat[cat]
            desc = sum(r[17] or 0 for r in g)
            sem = sum(r[18] == "sim" for r in g)
            print(f"  {cat[:34]:<34} {len(g):>4} {desc:>12} {desc / len(g):>12.1f} {sem:>14}")
        sem = [r for r in linhas if r[18] == "sim"]
        for r in sem:
            print(f"    sem evidência: rep {r[5]} {r[0]:>4} {r[3]:<24} consulta: {r[9]}")


# ── subcomando: conversa (M6) ─────────────────────────────────────────────────

VEREDITOS = ("respondida", "recusa", "urgente")

COLUNAS_CONVERSA = ["cenario", "tipo", "turno", "pergunta", "repeticao", "modelo",
                    "esperado", "obtido", "correto", "consulta_pubmed", "consulta_esperada",
                    "consulta_ok", "resposta", "n_artigos", "latencia_s", "erro",
                    "session_id", "executado_em"]


def carregar_cenarios(caminho: Path) -> dict:
    """Lê cenarios_multiturno.xlsx e valida: 2–4 turnos em ordem e vereditos conhecidos."""
    ws = openpyxl.load_workbook(caminho, read_only=True)["Cenários"]
    cenarios = {}
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if not r or not r[0]:
            continue
        c = cenarios.setdefault(r[0], dict(tipo=r[1], turnos=[]))
        if r[5] not in VEREDITOS:
            sys.exit(f"{r[0]} turno {r[3]}: veredito esperado inválido {r[5]!r}")
        c["turnos"].append(dict(turno=int(r[3]), pergunta=r[4], esperado=r[5], consulta=r[6] or ""))
    for cid, c in cenarios.items():
        if [t["turno"] for t in c["turnos"]] != list(range(1, len(c["turnos"]) + 1)):
            sys.exit(f"{cid}: turnos fora de ordem")
        if not 2 <= len(c["turnos"]) <= 4:
            sys.exit(f"{cid}: {len(c['turnos'])} turnos (o M6 pede de 2 a 4)")
    return cenarios


def veredito_api(d: dict) -> str:
    if d.get("urgent"):
        return "urgente"
    if d.get("blocked"):
        if str(d.get("answer", "")).startswith("Não consegui avaliar sua pergunta"):
            return "indisponível"
        return "recusa"
    return "respondida"


def consulta_contem(consulta: str, esperada: str):
    if not esperada:
        return None
    consulta = (consulta or "").lower()
    return "sim" if any(t.strip().lower() in consulta for t in esperada.split("|")) else "não"


def salvar_conversas(caminho: Path, linhas: list, meta: list):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Turnos"
    ws.append(COLUNAS_CONVERSA)
    for l in sorted(linhas, key=lambda l: (l[4], int(l[0][2:]), l[2])):
        ws.append(l)
    m = wb.create_sheet("Execução")
    for l in meta:
        m.append(l)
    for c in ws[1]:
        c.font = Font(bold=True)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb.save(caminho)


def conversa(a):
    """
    Executa cada cenário como uma conversa: todos os turnos com o mesmo
    session_id, uma sessão nova por cenário e repetição. Retoma execuções
    interrompidas, refazendo o cenário inteiro quando algum turno faltou ou deu
    erro (um turno isolado não pode ser refeito sem a memória dos anteriores).
    """
    cenarios = carregar_cenarios(a.cenarios)
    if a.ids:
        alvo = {i.strip().upper() for i in a.ids.split(",")}
        cenarios = {k: v for k, v in cenarios.items() if k.upper() in alvo}
    chave = os.environ.get(a.chave_env) if a.chave_env else None
    if a.chave_env and not chave:
        sys.exit(f"A variável de ambiente {a.chave_env} está vazia.")
    cabecalhos = {"X-LLM-Model": a.modelo}
    if chave:
        cabecalhos["X-LLM-Api-Key"] = chave

    saida = a.saida or (PASTA_SAIDA / ("conversa_" + nome_arquivo(a.modelo)))
    meta_nova = [["modelo", a.modelo], ["backend", a.url], ["repetições", a.repeticoes],
                 ["cenários", len(cenarios)],
                 ["iniciada em", datetime.now().isoformat(timespec="seconds")],
                 ["versão do código", versao_codigo()]]
    linhas, meta = [], meta_nova
    if saida.exists():
        wb = openpyxl.load_workbook(saida, read_only=True)
        linhas = [list(r) for r in wb["Turnos"].iter_rows(min_row=2, values_only=True) if r and r[0]]
        meta = [list(r) for r in wb["Execução"].iter_rows(values_only=True)] + [[]] + meta_nova[-2:]
    completos = set()
    for (cid, rep) in {(l[0], int(l[4])) for l in linhas}:
        feitos = [l for l in linhas if l[0] == cid and int(l[4]) == rep]
        if cid in cenarios and len(feitos) == len(cenarios[cid]["turnos"]) and not any(l[15] for l in feitos):
            completos.add((cid, rep))
    pendentes = [(rep, cid) for rep in range(1, a.repeticoes + 1) for cid in cenarios
                 if (cid, rep) not in completos]
    linhas = [l for l in linhas if (l[0], int(l[4])) in completos or l[0] not in cenarios]
    print(f"{len(cenarios) * a.repeticoes} conversas no total, {len(completos)} já concluídas, "
          f"{len(pendentes)} a fazer → {saida}")

    with httpx.Client(timeout=a.timeout) as cliente:
        try:
            cliente.get(f"{a.url}/api/health").raise_for_status()
        except httpx.HTTPError as e:
            sys.exit(f"Backend indisponível em {a.url}: {e!r}")

        for n, (rep, cid) in enumerate(pendentes, 1):
            c = cenarios[cid]
            session_id, marcas = None, []
            for t in c["turnos"]:
                base = [cid, c["tipo"], t["turno"], t["pergunta"], rep, a.modelo, t["esperado"]]
                t0 = time.perf_counter()
                try:
                    r = cliente.post(f"{a.url}/api/ask", headers=cabecalhos,
                                     json={"question": t["pergunta"], "session_id": session_id})
                    r.raise_for_status()
                    d = r.json()
                    session_id = d.get("session_id") or session_id
                    obtido = veredito_api(d)
                    linha = base + [obtido, "sim" if obtido == t["esperado"] else "não",
                                    d.get("pubmed_query", ""), t["consulta"] or None,
                                    consulta_contem(d.get("pubmed_query"), t["consulta"]),
                                    d.get("answer", ""), len(d.get("articles", [])),
                                    round(time.perf_counter() - t0, 1), None]
                    marcas.append(obtido if obtido == t["esperado"] else f"{obtido}≠{t['esperado']}")
                except httpx.HTTPError as e:
                    erro = (f"HTTP {e.response.status_code}: {e.response.text[:300]}"
                            if isinstance(e, httpx.HTTPStatusError) else f"{type(e).__name__}: {e}"[:300])
                    linha = base + [None] * 8 + [erro]
                    marcas.append("ERRO")
                linhas.append(linha + [session_id, datetime.now().isoformat(timespec="seconds")])
                if marcas[-1] == "ERRO":
                    break                      # sem esse turno, os seguintes perdem a memória
            if session_id:
                try:
                    cliente.post(f"{a.url}/api/ask/reset", json={"session_id": session_id})
                except httpx.HTTPError:
                    pass
            salvar_conversas(saida, linhas, meta)
            print(f"[{n}/{len(pendentes)}] rep {rep} {cid:>4}  " + " → ".join(marcas), flush=True)
            if a.pausa:
                time.sleep(a.pausa)

    a.execucoes = [saida]
    turnos(a)


# ── subcomando: turnos (M6) ───────────────────────────────────────────────────

def turnos(a):
    """
    Relatório do M6: taxa de vereditos corretos por posição do turno, por tipo
    de cenário e por veredito esperado, e a taxa de consultas PubMed que
    resolveram a elipse com a memória. Termina com código 1 se algum turno
    tiver veredito diferente do esperado.
    """
    falhou = False
    for caminho in a.execucoes:
        ws = openpyxl.load_workbook(caminho, read_only=True)["Turnos"]
        linhas = [r for r in ws.iter_rows(min_row=2, values_only=True) if r and r[0] and not r[15]]
        print(f"\n{caminho.name}: {len(linhas)} turnos válidos")

        def taxa(grupo):
            ok = sum(r[8] == "sim" for r in grupo)
            return f"{ok}/{len(grupo)} ({ok / len(grupo):.0%})" if grupo else "-"

        for titulo, chave in (("por turno", lambda r: f"turno {r[2]}"),
                              ("por tipo de cenário", lambda r: r[1]),
                              ("por veredito esperado", lambda r: r[6])):
            print(f"  {titulo}:")
            grupos = {}
            for r in linhas:
                grupos.setdefault(chave(r), []).append(r)
            for k in sorted(grupos):
                print(f"    {k:<32} {taxa(grupos[k])}")
        print(f"  total                            {taxa(linhas)}")

        consultas = [r for r in linhas if r[11] in ("sim", "não")]
        if consultas:
            ok = sum(r[11] == "sim" for r in consultas)
            print(f"  consultas PubMed com o termo esperado: {ok}/{len(consultas)}")

        erros = [r for r in linhas if r[8] != "sim"]
        for r in erros:
            print(f"    ERRO rep {r[4]} {r[0]:>4} turno {r[2]}: esperado {r[6]}, obtido {r[7]} — {r[3]}")
        falhou = falhou or bool(erros)
    sys.exit(1 if falhou else 0)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="comando", required=True)

    e = sub.add_parser("executar", help="roda as perguntas contra um modelo")
    e.add_argument("--modelo", required=True, help="nome do modelo (vai no cabeçalho X-LLM-Model)")
    e.add_argument("--chave-env", help="variável de ambiente com a chave de API (modo desenvolvedor)")
    e.add_argument("-n", "--repeticoes", type=int, default=3)
    e.add_argument("--url", default="http://localhost:8000", help="endereço do backend")
    e.add_argument("--perguntas", type=Path, default=PERGUNTAS)
    e.add_argument("--saida", type=Path, help=f"padrão: {PASTA_SAIDA.relative_to(RAIZ)}/<modelo>.xlsx")
    e.add_argument("--categorias", help="ex.: C,E")
    e.add_argument("--ids", help="ex.: F2,F5,F6")
    e.add_argument("--limite", type=int, help="só as N primeiras perguntas (teste rápido)")
    e.add_argument("--pausa", type=float, default=0, help="segundos entre perguntas (limite de cota da API)")
    e.add_argument("--timeout", type=float, default=600, help="segundos por pergunta")
    e.set_defaults(func=executar)

    m = sub.add_parser("montar", help="junta duas execuções no layout da aba Resultados")
    m.add_argument("execucao_a", type=Path)
    m.add_argument("execucao_b", type=Path)
    m.add_argument("--repeticao", type=int, default=1)
    m.add_argument("--perguntas", type=Path, default=PERGUNTAS)
    m.add_argument("--saida", type=Path, required=True)
    m.set_defaults(func=montar)

    c = sub.add_parser("consistencia", help="regressão M4: mesmo veredito entre as variantes de cada cenário")
    c.add_argument("execucoes", type=Path, nargs="+")
    c.add_argument("--categorias", default="F")
    c.set_defaults(func=consistencia)

    i = sub.add_parser("idioma", help="M5: conta respostas com CJK ou em inglês")
    i.add_argument("execucoes", type=Path, nargs="+")
    i.set_defaults(func=idioma)

    pe = sub.add_parser("pertinencia", help="M7: resumos descartados e perguntas sem evidência")
    pe.add_argument("execucoes", type=Path, nargs="+")
    pe.set_defaults(func=pertinencia)

    v = sub.add_parser("conversa", help="M6: cenários de vários turnos na mesma sessão")
    v.add_argument("--modelo", required=True, help="nome do modelo (vai no cabeçalho X-LLM-Model)")
    v.add_argument("--chave-env", help="variável de ambiente com a chave de API (modo desenvolvedor)")
    v.add_argument("-n", "--repeticoes", type=int, default=3)
    v.add_argument("--url", default="http://localhost:8000", help="endereço do backend")
    v.add_argument("--cenarios", type=Path, default=CENARIOS)
    v.add_argument("--saida", type=Path, help=f"padrão: {PASTA_SAIDA.relative_to(RAIZ)}/conversa_<modelo>.xlsx")
    v.add_argument("--ids", help="ex.: MT2,MT7")
    v.add_argument("--pausa", type=float, default=0, help="segundos entre conversas")
    v.add_argument("--timeout", type=float, default=600, help="segundos por turno")
    v.set_defaults(func=conversa)

    t = sub.add_parser("turnos", help="M6: taxa de vereditos corretos por turno")
    t.add_argument("execucoes", type=Path, nargs="+")
    t.set_defaults(func=turnos)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()

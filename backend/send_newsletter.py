"""
Script de envio de newsletter semanal para assinantes ativos.
Execute a partir da pasta backend: python send_newsletter.py
Agende via cron: 0 8 * * 1  cd /caminho/backend && python send_newsletter.py
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import resend
from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv(Path(__file__).parent / ".env")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM     = os.getenv("EMAIL_FROM", "newsletter.id.uff.br")
SITE_URL       = os.getenv("SITE_URL", "https://konenki-sci.vercel.app")

resend.api_key = RESEND_API_KEY

# Importa após load_dotenv para que db_connection leia o .env corretamente
from db_connection import Article as ArticleModel, Subscriber, Trend as TrendModel, get_db


# ── Consultas ao banco ────────────────────────────────────────────────────────

def get_active_subscribers():
    with get_db() as db:
        return db.scalars(
            select(Subscriber).where(Subscriber.active == True)
        ).all()


def get_weekly_articles(days: int = 7, max_results: int = 6):
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_db() as db:
        return db.scalars(
            select(ArticleModel)
            .where(ArticleModel.created_at >= cutoff)
            .order_by(ArticleModel.created_at.desc())
            .limit(max_results)
        ).all()


def get_weekly_trends(days: int = 7, max_results: int = 5):
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_db() as db:
        return db.scalars(
            select(TrendModel)
            .where(TrendModel.created_at >= cutoff)
            .order_by(TrendModel.created_at.desc())
            .limit(max_results)
        ).all()


# ── Montagem do HTML do email ─────────────────────────────────────────────────

def build_html(articles, trends) -> str:
    week_label = datetime.now().strftime("%d/%m/%Y")

    articles_html = ""
    for a in articles:
        summary = a.summary or ""
        articles_html += f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #f0e0d8;">
            <p style="margin:0 0 4px;font-size:15px;font-weight:600;color:#1a1a1a;line-height:1.4;">{a.title}</p>
            {f'<p style="margin:0;font-size:13px;color:#666;line-height:1.5;">{summary}</p>' if summary else ""}
          </td>
        </tr>"""

    trends_html = ""
    for t in trends:
        content_preview = (t.content or t.summary or "")[:200]
        trends_html += f"""
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #f0e0d8;">
            <p style="margin:0 0 4px;font-size:14px;font-weight:600;color:#1a1a1a;line-height:1.4;">{t.keyword}</p>
            {f'<p style="margin:0;font-size:13px;color:#666;line-height:1.5;">{content_preview}</p>' if content_preview else ""}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#fdf6f0;font-family:system-ui,-apple-system,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#fdf6f0;padding:32px 16px;">
    <tr><td>
      <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#fff;border-radius:16px;border:1px solid #e8d9cf;overflow:hidden;">

        <!-- Cabeçalho -->
        <tr>
          <td style="background:#fff;padding:24px 32px;border-bottom:1px solid #e8d9cf;">
            <p style="margin:0;font-size:20px;font-weight:700;color:#1a1a1a;">
              🌸 <span style="color:#c05c7e;">MenopausIA</span>
            </p>
            <p style="margin:4px 0 0;font-size:11px;color:#999;letter-spacing:.06em;">
              CIÊNCIA TRADUZIDA · CONTEXTO BRASILEIRO
            </p>
          </td>
        </tr>

        <!-- Título da edição -->
        <tr>
          <td style="padding:24px 32px 8px;">
            <p style="margin:0;font-size:12px;font-weight:700;letter-spacing:.08em;color:#999;text-transform:uppercase;">
              Novidades da semana
            </p>
            <p style="margin:4px 0 0;font-size:13px;color:#bbb;">{week_label}</p>
          </td>
        </tr>

        <!-- Artigos científicos -->
        {'<tr><td style="padding:8px 32px 0;"><p style="margin:0 0 4px;font-size:12px;font-weight:700;letter-spacing:.07em;color:#c05c7e;text-transform:uppercase;">Artigos Científicos</p><table width="100%" cellpadding="0" cellspacing="0">' + articles_html + '</table></td></tr>' if articles else ''}

        <!-- Notícias -->
        {'<tr><td style="padding:20px 32px 0;"><p style="margin:0 0 4px;font-size:12px;font-weight:700;letter-spacing:.07em;color:#c05c7e;text-transform:uppercase;">Últimas Notícias</p><table width="100%" cellpadding="0" cellspacing="0">' + trends_html + '</table></td></tr>' if trends else ''}

        <!-- CTA -->
        <tr>
          <td style="padding:24px 32px;">
            <a href="{SITE_URL}" style="display:inline-block;background:#c05c7e;color:#fff;text-decoration:none;border-radius:8px;padding:10px 20px;font-size:14px;font-weight:600;">
              Ver no site →
            </a>
          </td>
        </tr>

        <!-- Rodapé -->
        <tr>
          <td style="background:#fdf6f0;padding:16px 32px;border-top:1px solid #e8d9cf;">
            <p style="margin:0;font-size:11px;color:#bbb;text-align:center;line-height:1.6;">
              Você recebeu este email por estar inscrita na newsletter MenopausIA.<br>
              Não substitui consulta médica · Fonte: PubMed/NCBI &amp; NewsAPI
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── Envio ─────────────────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, html_body: str):
    resend.Emails.send({
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    })


# ── Ponto de entrada ──────────────────────────────────────────────────────────

def main():
    if not RESEND_API_KEY:
        print("RESEND_API_KEY não configurada — abortando.")
        sys.exit(1)

    print("Verificando assinantes ativos…")
    subscribers = get_active_subscribers()
    if not subscribers:
        print("Nenhum assinante ativo encontrado. Nada a enviar.")
        return

    print(f"{len(subscribers)} assinante(s) ativo(s) encontrado(s).")

    print("Buscando conteúdo da última semana…")
    articles = get_weekly_articles()
    trends   = get_weekly_trends()

    if not articles and not trends:
        print("Nenhum conteúdo novo na última semana. Nada a enviar.")
        return

    print(f"Conteúdo: {len(articles)} artigo(s), {len(trends)} notícia(s).")

    subject  = f"MenopausIA — Novidades da semana ({datetime.now().strftime('%d/%m/%Y')})"
    html     = build_html(articles, trends)

    sent = errors = 0
    for sub in subscribers:
        try:
            send_email(sub.email, subject, html)
            print(f"  ✓ Enviado para {sub.email}")
            sent += 1
        except Exception as e:
            print(f"  ✗ Erro ao enviar para {sub.email}: {e}")
            errors += 1

    print(f"\nConcluído: {sent} enviado(s), {errors} erro(s).")


if __name__ == "__main__":
    main()

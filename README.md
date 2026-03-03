# MenopausIA 🌸

Assistente de perguntas sobre menopausa fundamentada em artigos científicos do PubMed.

## Arquitetura
```
Frontend (React/Vite) → Backend (FastAPI) → PubMed API + LLM Provider
```

## Início rápido

### Backend
```bash
cd backend
cp .env.example .env        # edite com sua API key
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
cp .env.example .env        # VITE_API_URL=http://localhost:8000/api
npm install
npm run dev
```

## Troca de provider (sem tocar no código)

| Variável | Valores |
|---|---|
| `LLM_PROVIDER` | `api` (Fase 1) · `local` (Fase 2) |
| `EMB_PROVIDER` | `api` (Fase 1) · `local` (Fase 2) |

### Fase 1 — API cloud
Defina `LLM_PROVIDER=api` e uma das chaves:
- `ANTHROPIC_API_KEY` — usa Claude
- `OPENAI_API_KEY` — usa GPT
- `GEMINI_API_KEY` — usa Gemini

### Fase 2 — Local (Ollama)
```bash
ollama pull llama3
```
No `.env`:
```
LLM_PROVIDER=local
OLLAMA_MODEL=llama3
```

## Deploy gratuito (MVP)
- **Frontend** → [Vercel](https://vercel.com) (conecte o repositório, defina `VITE_API_URL`)
- **Backend** → [Render](https://render.com) (Web Service, defina as variáveis de ambiente)
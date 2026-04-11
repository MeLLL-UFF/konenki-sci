# MenopausaIA Sci Frontend

Frontend para o sistema MenopausIA, uma aplicação de perguntas e respostas sobre menopausa baseada em evidências científicas do Dataset Hugging Face.

## Tecnologias

- React 18
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Lucide Icons

## Instalação

```bash
npm install
```

## Desenvolvimento

```bash
npm run dev
```

A aplicação estará disponível em http://localhost:8080

## Build

```bash
npm run build
```

## Testes

```bash
npm run test
```

## Estrutura do Projeto

- `src/components/` - Componentes React
- `src/lib/` - Utilitários e API
- `src/hooks/` - Hooks customizados
- `src/components/ui/` - Componentes shadcn/ui

## API

O frontend se conecta ao backend em `http://localhost:8000/api` com endpoints:
- `POST /ask` - Pergunta simples
- `POST /ask/stream` - Pergunta com streaming
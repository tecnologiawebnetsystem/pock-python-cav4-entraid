# Como rodar o projeto localmente

Este projeto tem **dois serviços**:

| Serviço    | Pasta       | Tecnologia        | Rota em produção |
| ---------- | ----------- | ----------------- | ---------------- |
| `frontend` | `frontend/` | Next.js 16 (React)| `/`              |
| `backend`  | `backend/`  | FastAPI (Python)  | `/api`           |

O frontend chama a API sempre pelo prefixo **`/api`** (ex.: `/api/health`, `/api/auth/login`).
Na Vercel, esse prefixo é removido antes de chegar no FastAPI — por isso o backend
define as rotas **sem** o `/api` (ex.: `@app.get("/health")`).

### O que esta POC faz

Uma tela com um botão **"Conectar"**. Ao clicar:

1. o frontend chama `GET /api/auth/login`, que redireciona para o login do CA (Entra);
2. após autenticar, o CA volta em `GET /api/auth/entra-callback`;
3. o backend troca o code por tokens, lê as informações do Entra **e** consulta o
   CAv4 (alocação/recursos), retornando **tudo num único JSON** na tela.

---

## Pré-requisitos

- **Node.js** 20+ e **pnpm** (`npm install -g pnpm`)
- **Python** 3.12+ e **uv** (gerenciador do backend — https://docs.astral.sh/uv/)
- (Opcional) **Vercel CLI** (`npm install -g vercel`) para o modo integrado

---

## Opção A — Modo integrado com `vercel dev` (recomendado)

Reproduz o ambiente de produção: um único endereço, com o roteamento
`/api → backend` já resolvido.

```bash
# na raiz do projeto
vercel dev
```

Acesse: **http://localhost:3000** (API em **http://localhost:3000/api**).

---

## Opção B — Rodar cada serviço separadamente

### 1. Backend (FastAPI) — porta 8000

```bash
cd backend
uv sync                 # instala as dependências (primeira vez)
cp .env.example .env    # cria o .env local (só na primeira vez)
uv run uvicorn main:app --reload --port 8000
```

A API sobe em **http://localhost:8000** (docs em http://localhost:8000/docs).
Aqui as rotas são **sem** `/api` (ex.: http://localhost:8000/health).

### 2. Frontend (Next.js) — porta 3000

O `frontend/next.config.ts` já tem um *rewrite* que encaminha `/api` para o
backend na porta 8000 em desenvolvimento. Basta rodar:

```bash
cd frontend
pnpm install            # instala as dependências (primeira vez)
pnpm dev
```

Acesse: **http://localhost:3000**

---

## Configuração do `.env` (backend)

O login com o CA depende do `backend/.env`. Para criar:

```bash
cd backend
cp .env.example .env
```

O `.env.example` já vem com os valores de **DSV** preenchidos. Pontos de atenção:

- **`OIDC_DISCOVERY_URL`**: confirme o caminho exato com o time do CA (pode haver
  um *realm*).
- **`CA_CLIENT_SECRET`**: segredo da aplicação no CA. Em DSV pode ficar no `.env`;
  em HOM/PROD use variável de ambiente / Secrets Manager.
- **`CA_SSL_VERIFY` / `CA_SSL_CERT_FILE`**: os hosts do CA usam certificado de uma
  CA interna da Petrobras. Se o login falhar com erro de SSL, aponte
  `CA_SSL_CERT_FILE` para o bundle da CA interna (recomendado) ou, **só em DSV**,
  defina `CA_SSL_VERIFY=false`.

---

## Verificação rápida

Com tudo rodando:

| O que testar          | Modo integrado (A)                | Modo separado (B)             |
| --------------------- | --------------------------------- | ----------------------------- |
| Frontend              | http://localhost:3000             | http://localhost:3000         |
| Health da API         | http://localhost:3000/api/health  | http://localhost:8000/health  |
| Docs da API (Swagger) | http://localhost:3000/api/docs    | http://localhost:8000/docs    |
| Login no CA           | clique em "Conectar" no frontend  | clique em "Conectar"          |

Se o health retornar `{"status":"ok"}` e o frontend carregar, está tudo certo.

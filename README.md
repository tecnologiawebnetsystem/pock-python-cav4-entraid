### Pock Python — POC Login CA Petrobras (Next.js + FastAPI)

Esta POC tem um objetivo único e simples: **clicar em "Conectar", autenticar no
CA Petrobras (Entra) e ver na tela todas as informações retornadas** — dados do
Entra e a consulta de alocação/recursos no CAv4.

Dois serviços:

- `frontend/` — aplicação **Next.js** (uma tela com o botão "Conectar")
- `backend/` — API **FastAPI** (Python) com 2 rotas: `/auth/login` e `/auth/entra-callback`

> Guia detalhado de execução em **[RUNNING.md](./RUNNING.md)**.

---

### Pré-requisitos

| Ferramenta | Versão recomendada | Para quê |
|------------|--------------------|----------|
| **Node.js** | 20 ou superior | Rodar o frontend |
| **pnpm** | 9 ou superior | Dependências do frontend |
| **Python** | 3.12 ou superior | Rodar o backend |
| **uv** | mais recente | Dependências do Python |

```bash
node --version && pnpm --version && python --version && uv --version
```

> Sem `pnpm`: `npm install -g pnpm` — sem `uv`: `pip install uv` (ou https://docs.astral.sh/uv/)

---

### Como os dois serviços conversam

- O **backend** roda na porta **8000** e expõe as rotas sem prefixo (ex.: `/health`, `/auth/login`).
- O **frontend** roda na porta **3000** e chama a API pelo prefixo **`/api`** (ex.: `/api/auth/login`).
- Um *rewrite* no `frontend/next.config.ts` encaminha tudo que começa com `/api`
  para o backend na porta 8000, removendo o prefixo `/api`.

Ou seja: o navegador chama `http://localhost:3000/api/health` e isso chega no backend como `GET /health`.

---

### Passo 1 — Backend (FastAPI)

```bash
cd backend
uv sync                 # cria o ambiente e instala as dependências
cp .env.example .env    # cria as variáveis de ambiente
uv run uvicorn main:app --reload --port 8000
```

Disponível em **http://localhost:8000** (Swagger em `/docs`, health em `/health`).
Deixe esse terminal aberto.

---

### Passo 2 — Frontend (Next.js)

Em um **segundo** terminal:

```bash
cd frontend
pnpm install
pnpm dev
```

Disponível em **http://localhost:3000**. Abra no navegador e clique em **"Conectar"**.

---

### O fluxo da POC

1. Você clica em **"Conectar"** → o frontend chama `GET /api/auth/login`.
2. O backend redireciona para o login do CA (Entra).
3. Após autenticar, o CA volta em `GET /api/auth/entra-callback`.
4. O backend troca o code por tokens, lê as informações do Entra **e** consulta
   o CAv4, retornando **um único JSON** com tudo (`entra` + `ca`).

---

### Variáveis de ambiente do backend

O arquivo `backend/.env` (criado no Passo 1) contém as configurações. Pontos de atenção:

- **`OIDC_DISCOVERY_URL`** — endereço de autenticação do CA; confirme o caminho
  exato com o time do CA (pode haver um *realm*).
- **`CA_CLIENT_SECRET`** — segredo da aplicação no CA (em HOM/PROD use Secrets Manager).
- **`CA_SSL_VERIFY` / `CA_SSL_CERT_FILE`** — se o login falhar com erro de SSL,
  aponte `CA_SSL_CERT_FILE` para o bundle da CA interna da Petrobras (recomendado)
  ou, **somente em DSV**, defina `CA_SSL_VERIFY=false`.

---

### Problemas comuns

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| `/api/...` retorna 404 | Backend não está rodando ou rewrite não recarregado | Confirme o backend na porta 8000 e reinicie o `pnpm dev` |
| `Internal Server Error` no login | Certificado SSL da CA interna não confiável no Python | Configure `CA_SSL_CERT_FILE` ou `CA_SSL_VERIFY=false` (só DSV) |
| `command not found: uv` | `uv` não instalado | `pip install uv` |
| `command not found: pnpm` | `pnpm` não instalado | `npm install -g pnpm` |
| Porta 3000/8000 ocupada | Outro processo usando a porta | Encerre o processo ou troque a porta |

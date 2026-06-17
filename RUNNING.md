# Como rodar o projeto localmente

Este projeto tem **um único serviço** (somente backend):

| Serviço    | Pasta       | Tecnologia        | Rota em produção |
| ---------- | ----------- | ----------------- | ---------------- |
| `backend`  | `backend/`  | FastAPI (Python)  | `/`              |

Não há frontend. As rotas do backend são servidas direto na raiz
(ex.: `/health`, `/auth/login`, `/auth/entra-callback`).

### O que esta POC faz

Ao acessar **`/auth/login`**:

1. o backend redireciona para o login do CA (Entra);
2. após autenticar, o CA volta em `GET /auth/entra-callback`;
3. o backend troca o code por tokens, lê as informações do Entra **e** consulta o
   CAv4 (alocação/recursos), **imprimindo tudo no terminal (tela preta)** e
   retornando também um JSON.

---

## Pré-requisitos

- **Python** 3.12+ e **uv** (gerenciador do backend — https://docs.astral.sh/uv/)

---

## Rodar o backend (FastAPI) — porta 8000

```bash
cd backend
uv sync                 # instala as dependências (primeira vez)
cp .env.example .env    # cria o .env local (só na primeira vez)
uv run uvicorn main:app --reload --port 8000
```

A API sobe em **http://localhost:8000** (docs em http://localhost:8000/docs).
Deixe o terminal aberto — é nele que o resultado do login é exibido.

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
- **`CA_REDIRECT_URI`**: como não há mais o prefixo `/api`, aponte para
  `.../auth/entra-callback` e garanta que está igual ao registrado no CA.
- **`CA_SSL_VERIFY` / `CA_SSL_CERT_FILE`**: os hosts do CA usam certificado de uma
  CA interna da Petrobras. Se o login falhar com erro de SSL, aponte
  `CA_SSL_CERT_FILE` para o bundle da CA interna (recomendado) ou, **só em DSV**,
  defina `CA_SSL_VERIFY=false`.

---

## Verificação rápida

Com o backend rodando:

| O que testar          | Endereço                          |
| --------------------- | --------------------------------- |
| Health da API         | http://localhost:8000/health      |
| Docs da API (Swagger) | http://localhost:8000/docs        |
| Login no CA           | http://localhost:8000/auth/login  |

Se o health retornar `{"status":"ok"}`, está tudo certo. Ao fazer o login, as
informações recebidas do Entra/CAv4 aparecem no terminal onde o uvicorn roda.

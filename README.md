### Pock Python — POC Login CA Petrobras (FastAPI, somente backend)

Esta POC tem um objetivo único e simples: **acessar `/auth/login`, autenticar no
CA Petrobras (Entra) e ver no terminal todas as informações retornadas** — dados
do Entra (claims do `id_token`) e a consulta de alocação/recursos no CAv4.

**Não há frontend.** O projeto é exclusivamente o serviço `backend/` — uma API
**FastAPI** (Python) com 2 rotas: `/auth/login` e `/auth/entra-callback`. O
resultado do login é despejado na **tela preta (terminal)** e também retornado
como JSON.

> Guia detalhado de execução em **[RUNNING.md](./RUNNING.md)**.

---

### Pré-requisitos

| Ferramenta | Versão recomendada | Para quê |
|------------|--------------------|----------|
| **Python** | 3.12 ou superior | Rodar o backend |
| **uv** | mais recente | Dependências do Python |

```bash
python --version && uv --version
```

> Sem `uv`: `pip install uv` (ou https://docs.astral.sh/uv/)

---

### Como rodar

```bash
cd backend
uv sync                 # cria o ambiente e instala as dependências
cp .env.example .env    # cria as variáveis de ambiente
uv run uvicorn main:app --reload --port 8000
```

Disponível em **http://localhost:8000** (Swagger em `/docs`, health em `/health`).
Deixe esse terminal aberto — é nele que as informações do login serão impressas.

---

### O fluxo da POC

1. Acesse **http://localhost:8000/auth/login** no navegador.
2. O backend redireciona para o login do CA (Entra).
3. Após autenticar, o CA volta em `GET /auth/entra-callback`.
4. O backend troca o code por tokens, lê as informações do Entra **e** consulta
   o CAv4, **imprimindo tudo no terminal** (e também retornando um JSON).

---

### Variáveis de ambiente do backend

O arquivo `backend/.env` (criado acima) contém as configurações. Pontos de atenção:

- **`OIDC_DISCOVERY_URL`** — endereço de autenticação do CA; confirme o caminho
  exato com o time do CA (pode haver um *realm*).
- **`CA_CLIENT_SECRET`** — segredo da aplicação no CA (em HOM/PROD use Secrets Manager).
- **`CA_REDIRECT_URI`** — URI de callback registrada no CA. Como não há mais o
  prefixo `/api`, deve apontar para `.../auth/entra-callback`.
- **`CA_SSL_VERIFY` / `CA_SSL_CERT_FILE`** — se o login falhar com erro de SSL,
  aponte `CA_SSL_CERT_FILE` para o bundle da CA interna da Petrobras (recomendado)
  ou, **somente em DSV**, defina `CA_SSL_VERIFY=false`.

---

### Problemas comuns

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| `Internal Server Error` no login | Certificado SSL da CA interna não confiável no Python | Configure `CA_SSL_CERT_FILE` ou `CA_SSL_VERIFY=false` (só DSV) |
| `command not found: uv` | `uv` não instalado | `pip install uv` |
| Porta 8000 ocupada | Outro processo usando a porta | Encerre o processo ou troque a porta |
| Erro de `redirect_uri` no CA | `CA_REDIRECT_URI` não bate com o registrado no CA | Ajuste para `.../auth/entra-callback` (sem `/api`) |

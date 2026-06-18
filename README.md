### Pock Python — POC Login CA Petrobras + Entra ID (FastAPI, somente backend)

Esta POC tem um objetivo único e simples: **acessar `/auth/login`, autenticar no
CA Petrobras (Entra) e ver no terminal todas as informações retornadas**. Após o
login, o backend executa um fluxo **encadeado em duas fases**:

1. **Fase 1 — CAv4:** consulta a User/Admin API do CAv4 (grupos, valores de
   informação, detalhes do usuário, enterprise groups e papéis).
2. **Fase 2 — Entra ID (Microsoft Graph):** usando o **e-mail que veio do CAv4**,
   consulta o Microsoft Graph para trazer perfil, gerente, foto, cadeia de
   gestão, subordinados diretos e grupos.

**Não há frontend.** O projeto é exclusivamente o serviço `backend/` — uma API
**FastAPI** (Python) com 2 rotas: `/auth/login` e `/auth/entra-callback`. O
resultado do login é despejado na **tela preta (terminal)** e também retornado
como JSON.

> Guia detalhado de execução em **[RUNNING.md](./RUNNING.md)**.

---

### Estrutura do projeto

```
.
├── backend/            # API FastAPI (todo o código fica aqui)
│   ├── main.py         # entrypoint da API + rotas /health
│   ├── auth.py         # /auth/login e /auth/entra-callback + catálogo de consultas
│   ├── oidc.py         # fluxo OIDC (discovery, troca de code, validação de token)
│   ├── ca_client.py    # consultas à User/Admin API do CAv4 (Fase 1)
│   ├── graph_client.py # consultas ao Microsoft Graph / Entra ID (Fase 2)
│   ├── config.py       # configurações via variáveis de ambiente
│   ├── session.py      # store em memória dos logins pendentes
│   ├── errors.py       # erros categorizados
│   └── .env.example    # modelo de variáveis de ambiente
├── vercel.json         # roteamento do serviço backend (experimentalServices)
└── package.json        # stub vazio exigido pelo build da Vercel (não é frontend)
```

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
4. O backend troca o code por tokens e executa as duas fases abaixo,
   **imprimindo tudo no terminal** (e também retornando um JSON):
   - **Fase 1 (CAv4):** roda as 5 consultas do CA com o `access_token`.
   - **Ponte:** extrai o e-mail/UPN do resultado de *Detalhes do Usuário* do CAv4.
   - **Fase 2 (Entra/Graph):** com esse e-mail, consulta o Microsoft Graph.

---

### Consultas executadas

A ordem e os textos abaixo são definidos no catálogo `CAV4_CONSULTAS` em
`backend/auth.py`. Cada consulta é **resiliente**: se uma falha, registra o erro
categorizado e as demais continuam.

| # | Fonte | Consulta | Endpoint |
|---|-------|----------|----------|
| 1 | CAv4 | Grupos de usuário | `GET /api/users/{userLogin}/user-groups` |
| 2 | CAv4 | Valores de informação | `GET /api/users/{userLogin}/information-values` |
| 3 | CAv4 | Detalhes do usuário (Admin) | `GET /api/admin/users/{userLogin}` |
| 4 | CAv4 | Enterprise groups (Admin) | `GET /api/admin/users/{userLogin}/enterprise-groups` |
| 5 | CAv4 | Papéis / roles (Admin) | `GET /api/admin/users/{userLogin}/roles` |
| 6 | Entra | Perfil completo | `GET /v1.0/users/{upn}` |
| 7 | Entra | Gerente/supervisor | `GET /v1.0/users/{upn}/manager` |
| 8 | Entra | Foto (data URI base64) | `GET /v1.0/users/{upn}/photo/$value` |
| 9 | Entra | Cadeia de gestão | `GET /v1.0/users/{upn}/manager?$expand=manager` |
| 10 | Entra | Subordinados diretos | `GET /v1.0/users/{upn}/directReports` |
| 11 | Entra | Grupos / equipes | `GET /v1.0/users/{upn}/memberOf` |

---

### Variáveis de ambiente do backend

O arquivo `backend/.env` (criado acima) contém as configurações. Pontos de atenção:

- **`OIDC_DISCOVERY_URL`** — endereço de autenticação do CA; confirme o caminho
  exato com o time do CA (pode haver um *realm*).
- **`CA_CLIENT_SECRET`** — segredo da aplicação no CA (em HOM/PROD use Secrets Manager).
- **`CA_REDIRECT_URI`** — URI de callback **registrada no CA**; precisa ser
  exatamente igual à cadastrada (ex.: `http://localhost:8000/auth/entra-callback`
  para teste local). É exigida pelo protocolo OIDC — sem ela o login não acontece.
- **`CA_SSL_VERIFY` / `CA_SSL_CERT_FILE`** — se o login falhar com erro de SSL,
  aponte `CA_SSL_CERT_FILE` para o bundle da CA interna da Petrobras (recomendado)
  ou, **somente em DSV**, defina `CA_SSL_VERIFY=false`.

#### Credenciais do Entra ID (Fase 2 — Microsoft Graph)

A consulta ao Graph usa o fluxo **app-only (client credentials)** com uma app
registration do Entra. O backend procura as credenciais nesta ordem (a primeira
preenchida vence): **`GRAPH_*` → `ENTRA_*` → `CA_*`**.

- **`ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET`** — opção
  recomendada. Se você já tem essas variáveis, **não precisa** preencher as
  `GRAPH_*`; o backend as usa automaticamente.
- A app registration precisa ter **permissões de APLICAÇÃO** no Microsoft Graph,
  com **admin consent**: `User.Read.All` (perfil, manager, foto, subordinados) e
  `GroupMember.Read.All` (grupos). Sem isso, o Graph responde **HTTP 403**.
- Sem nenhuma dessas credenciais, as consultas do Entra retornam erro controlado
  (`GRAPH_NOT_CONFIGURED`) **sem afetar** as consultas do CAv4.

---

### Problemas comuns

| Problema | Causa provável | Solução |
|----------|----------------|---------|
| `Internal Server Error` no login | Certificado SSL da CA interna não confiável no Python | Configure `CA_SSL_CERT_FILE` ou `CA_SSL_VERIFY=false` (só DSV) |
| `command not found: uv` | `uv` não instalado | `pip install uv` |
| Porta 8000 ocupada | Outro processo usando a porta | Encerre o processo ou troque a porta |
| O callback nunca chega (sem dados no terminal) | `CA_REDIRECT_URI` não bate com o registrado no CA | Cadastre/ajuste a URI de callback no CA e no `.env` |
| Consultas do Entra com `GRAPH_ACCESS_DENIED` (HTTP 403) | A app do Entra não tem permissão de **aplicação** no Graph | Conceda `User.Read.All` e `GroupMember.Read.All` (tipo Aplicação) com **admin consent** |
| Consultas do Entra com `GRAPH_NOT_CONFIGURED` | Faltam as credenciais do Entra | Preencha `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` no `.env` |

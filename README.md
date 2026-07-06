### Pock Python — POC Login CA Petrobras + Entra ID (FastAPI + Next.js)

Esta POC faz o login no **CA Petrobras (Entra ID)** e mostra, numa página bonita,
**todas as informações retornadas** por cada endpoint consultado. Após o login, o
backend executa um fluxo **encadeado em duas fases**:

1. **Fase 1 — CAv4:** consulta a User/Admin API do CAv4 (grupos, valores de
   informação, detalhes do usuário, enterprise groups e papéis).
2. **Fase 2 — Entra ID (Microsoft Graph):** usando o **e-mail que veio do CAv4**,
   consulta o Microsoft Graph para trazer perfil, gerente, foto, cadeia de
   gestão, subordinados diretos e grupos.

O projeto agora tem **dois serviços**:

- **`backend/`** — API **FastAPI** (Python) que faz o login e as consultas.
- **`frontend/`** — app **Next.js** (a página `/viewer`) que exibe os endpoints e
  o JSON de cada um. É **somente leitura** — não edita nem envia nada.

Localmente você roda os dois separados (uvicorn + Next.js) e acessa tudo por
**`http://localhost:3000/viewer`** — o frontend encaminha as chamadas do backend
automaticamente. O `vercel.json` só é usado caso um dia queira publicar na Vercel.

---

### Como funciona o fluxo (ponto de entrada = `/viewer`)

```
1. Você abre  /viewer
2. A página verifica se há sessão. Se NÃO houver, redireciona para /auth/login
3. /auth/login  -> manda para a tela de login do CA (Entra).
   (Se você já tem sessão SSO no Entra, ele volta sem pedir senha.)
4. /auth/entra-callback -> troca o code por tokens, roda as 11 consultas
   (CAv4 + Graph), imprime tudo no TERMINAL e guarda o resultado num token curto.
5. O callback redireciona para /viewer?r=TOKEN
6. /viewer busca o resultado em /auth/result/{TOKEN} e mostra tudo na tela:
   identidade, lista dos 11 endpoints e o JSON retornado por cada um.
```

> O resultado também continua sendo impresso no **terminal** do backend.

---

### Estrutura do projeto

```
.
├── backend/                # API FastAPI
│   ├── main.py             # entrypoint da API + /health
│   ├── auth.py             # /auth/login, /auth/entra-callback, /auth/result/{token}
│   ├── oidc.py             # fluxo OIDC (discovery, troca de code, validação)
│   ├── ca_client.py        # consultas ao CAv4 (Fase 1)
│   ├── graph_client.py     # consultas ao Microsoft Graph (Fase 2)
│   ├── config.py           # configurações via variáveis de ambiente
│   ├── session.py          # store em memória (logins pendentes + resultados)
│   ├── errors.py           # erros categorizados
│   └── .env.example        # modelo de variáveis de ambiente
├── frontend/               # app Next.js (página /viewer, somente leitura)
│   ├── app/                # page.tsx, layout.tsx, globals.css
│   ├── components/         # lista de endpoints, detalhe, visualizador de JSON
│   ├── lib/types.ts        # tipos + extração dos endpoints da resposta
│   └── next.config.ts      # basePath /viewer + proxy p/ o backend em dev
└── vercel.json             # roteamento dos 2 serviços (só p/ deploy na Vercel)
```

---

### Pré-requisitos

| Ferramenta | Versão | Para quê |
|------------|--------|----------|
| **Python** | 3.12+ | Backend (uvicorn) |
| **uv** | recente | Dependências do Python |
| **Node.js** | 20+ | Frontend (Next.js) |

```bash
python --version && uv --version && node --version
```

> Sem `uv`: `pip install uv` (ou https://docs.astral.sh/uv/)
>
> **Não é necessário Vercel nem `vercel dev`** — tudo roda localmente na sua máquina.

---

## Como rodar e testar (100% local, sem Vercel)

A ideia é simples: **dois terminais**, um para o backend (uvicorn) e outro para o
frontend (Next.js). O frontend já vem configurado para, em modo de
desenvolvimento, encaminhar as rotas do backend (`/auth/*` e `/health`) para o
uvicorn — então **você acessa tudo por uma única porta: `http://localhost:3000`**.

### Passo 1 — Preparar (apenas no primeiro uso)

```bash
# dependências do backend
cd backend
uv sync
cp .env.example .env          # preencha as variáveis (veja a seção abaixo)
cd ..

# dependências do frontend
cd frontend
npm install
cd ..
```

No `backend/.env`, deixe a `CA_REDIRECT_URI` apontando para a **porta 3000**
(porque é por ela que você vai acessar tudo) e registre essa mesma URI no CA:

```
CA_REDIRECT_URI=http://localhost:3000/auth/entra-callback
```

### Passo 2 — Subir o backend (Terminal 1)

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

O backend fica em `http://localhost:8000` (Swagger em `/docs`, health em `/health`).
Deixe este terminal aberto — é nele que o resultado do login também é impresso.

### Passo 3 — Subir o frontend (Terminal 2)

```bash
cd frontend
npm run dev
```

O frontend fica em `http://localhost:3000` e encaminha as chamadas de `/auth/*`
para o backend na 8000 automaticamente (via `rewrites` do `next.config.ts`).

> Se o seu backend rodar em outra porta, ajuste com a env
> `BACKEND_ORIGIN` ao iniciar o frontend, ex.:
> `BACKEND_ORIGIN=http://localhost:9000 npm run dev`.

### Passo 4 — Testar

1. Abra **http://localhost:3000/viewer** no navegador.
2. Você é redirecionado para o login do CA (Entra). Autentique.
3. Ao voltar, a página mostra sua identidade e **os 11 endpoints**.
4. **Clique em qualquer endpoint** para ver o JSON que ele retornou.
   - Aba **Endpoints** — lista + JSON de cada endpoint (CAv4 e Graph).
   - Aba **Claims do Entra** — as claims do `id_token`.
   - Aba **JSON completo** — a resposta inteira do callback.
5. O mesmo resultado também aparece no **Terminal 1** (backend).

> **Só o backend?** Se quiser apenas ver o JSON no terminal, sem a página, rode
> só o Passo 2, use `CA_REDIRECT_URI=http://localhost:8000/auth/entra-callback` e
> abra `http://localhost:8000/auth/login`. (Nesse modo o callback tenta ir para
> `/viewer`; para ver a página, use o fluxo completo dos dois terminais acima.)

---

### Rotas do backend

| Rota | O que faz |
|------|-----------|
| `GET /auth/login` | Redireciona para o login do CA (Entra). |
| `GET /auth/entra-callback` | Troca o code por tokens, roda as 11 consultas, imprime no terminal e redireciona para `/viewer?r=TOKEN`. |
| `GET /auth/result/{token}` | Devolve o JSON do login associado ao token (a página `/viewer` usa isto). Expira em ~10 min. |
| `GET /health` | Health check. |

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
  exatamente igual à cadastrada. Use `http://localhost:3000/auth/entra-callback`
  no fluxo completo (dois terminais), ou `http://localhost:8000/auth/entra-callback`
  no modo só-backend. É exigida pelo protocolo OIDC — sem ela o login não acontece.
- **`VIEWER_PATH`** *(opcional)* — caminho para onde o callback redireciona após o
  login. Padrão: `/viewer`. Só mude se hospedar a página em outro caminho.
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
| A página fica em "Verificando sua sessão…" e não sai | Backend (uvicorn) fora do ar | Confira o **Terminal 1** e suba o backend (Passo 2) |
| `502`/erro ao chamar `/auth/...` no front | Backend em outra porta | Suba na 8000 ou use `BACKEND_ORIGIN=http://localhost:PORTA npm run dev` |
| "Resultado do login não encontrado ou expirado" | Token expirou (10 min) ou o backend reiniciou | Clique em **Entrar novamente** para refazer o login |
| O callback nunca chega (sem dados) | `CA_REDIRECT_URI` não bate com o registrado no CA | Ajuste a URI no CA e no `.env` para `http://localhost:3000/auth/entra-callback` |
| `/viewer` retorna 404 (só na Vercel) | Framework Preset errado | Defina o preset como **Services** em Settings → Build and Deployment |
| `Internal Server Error` no login | Certificado SSL da CA interna não confiável no Python | Configure `CA_SSL_CERT_FILE` ou `CA_SSL_VERIFY=false` (só DSV) |
| `command not found: uv` | `uv` não instalado | `pip install uv` |
| Consultas do Entra com `GRAPH_ACCESS_DENIED` (HTTP 403) | A app do Entra não tem permissão de **aplicação** no Graph | Conceda `User.Read.All` e `GroupMember.Read.All` (tipo Aplicação) com **admin consent** |
| Consultas do Entra com `GRAPH_NOT_CONFIGURED` | Faltam as credenciais do Entra | Preencha `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` no `.env` |

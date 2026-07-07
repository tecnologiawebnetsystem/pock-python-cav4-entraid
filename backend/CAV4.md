# CAv4 — Controle de Acesso Petrobras (Passo 1)

Documentação dos endpoints do **CAv4** consultados por esta POC e do que cada um
retorna. É o **Passo 1** do fluxo de login, **independente** do Passo 2 (Entra ID,
documentado em [ENTRAID.md](./ENTRAID.md)).

> Implementação: `backend/ca_client.py` (classe `CAUserClient`).
> Catálogo/ordem das consultas: `CAV4_CONSULTAS` em `backend/auth.py`.

---

## Como funciona a autenticação (diferente do Entra)

Ao contrário do Passo 2 (Entra), que usa um token **da aplicação** (app-only), o
CAv4 é consultado com o **`access_token` do próprio usuário logado**, obtido no
fluxo OIDC durante o login.

- O token vem no cabeçalho `Authorization: Bearer <access_token>`.
- O token fica **no servidor** e **nunca** é exposto ao frontend.
- O identificador do usuário é o **`userLogin`** (a matrícula/chave extraída das
  claims do token), **não** o e-mail/UPN.

| Variável de ambiente | Para que serve |
|----------------------|----------------|
| `CA_API_BASE_URL` | Host base da API do CA (ex.: `https://ca-dsv.petrobras.com.br`). |

---

## Envelope de resposta (formato de cada consulta)

Cada consulta do CAv4 é devolvida no mesmo formato padronizado, para deixar
claro de onde veio o dado:

```json
{
  "endpoint": "GET /api/users/{userLogin}/user-groups",
  "titulo": "GRUPOS DE USUARIO (User Groups)",
  "descricao": "Grupos de usuário aos quais a pessoa está associada.",
  "ok": true,
  "data": <resposta crua do CA>
}
```

- **`endpoint`** — método + caminho real chamado (com o `userLogin` resolvido).
- **`titulo`** / **`descricao`** — rótulo legível da consulta.
- **`ok`** — `true` se a chamada teve sucesso; `false` se falhou.
- **`data`** — presente quando `ok: true`. Conteúdo exatamente como o CA devolve.
- **`error`** — presente quando `ok: false`. Erro categorizado (ver tabela no fim).

> As consultas são **resilientes**: se uma falha, ela registra o erro no próprio
> campo e as demais continuam normalmente.

---

## Endpoints

### 1. Grupos de usuário — `user_groups`
- **Endpoint:** `GET /api/users/{userLogin}/user-groups`
- **API:** User API
- **Para que serve:** listar os **grupos de usuário** aos quais a pessoa está
  associada no CA.
- **Retorna:** a lista de grupos de usuário do `userLogin`, no formato do CA.

### 2. Valores de informação — `information_values`
- **Endpoint:** `GET /api/users/{userLogin}/information-values`
- **API:** User API
- **Para que serve:** obter os **valores de informação** autorizados ao usuário
  (atributos/permissões de informação mantidos pelo CA).
- **Retorna:** a lista de valores de informação do usuário.

### 3. Detalhes do usuário — `admin_user_details`
- **Endpoint:** `GET /api/admin/users/{userLogin}`
- **API:** Admin API
- **Para que serve:** trazer os **dados cadastrais** do usuário — normalmente
  lotação, gerente/supervisor, empresa e demais atributos de cadastro.
- **Retorna:** o registro cadastral do usuário conforme o CA.

### 4. Enterprise groups — `admin_enterprise_groups`
- **Endpoint:** `GET /api/admin/users/{userLogin}/enterprise-groups`
- **API:** Admin API
- **Para que serve:** listar os **grupos corporativos (enterprise groups)** do
  usuário — os grupos ligados à estrutura de empresa.
- **Retorna:** a lista de enterprise groups do usuário.

### 5. Papéis / roles — `admin_roles`
- **Endpoint:** `GET /api/admin/users/{userLogin}/roles`
- **API:** Admin API
- **Para que serve:** listar os **papéis/perfis (roles)** atribuídos ao usuário.
- **Retorna:** a lista de papéis do usuário (GET, sem corpo de requisição).

---

## Observações importantes

- **User API vs Admin API:** as consultas #1 e #2 usam a *User API*
  (`/api/users/...`); as #3, #4 e #5 usam a *Admin API* (`/api/admin/users/...`).
  A Admin API pode exigir permissões adicionais da aplicação/usuário no CA.
- **`userLogin` (matrícula), não e-mail:** o CA identifica a pessoa pela
  matrícula/chave extraída do token — diferente do Entra, que usa o UPN/e-mail.
- **Formato de `data`:** o CA não usa uma lista fixa de campos (não há `$select`
  como no Graph). O conteúdo de `data` vem exatamente como a API do CA devolve e
  pode variar conforme o ambiente (DSV/HOM/PRD).

---

## Erros possíveis

| `code` | HTTP | O que significa | Como resolver |
|--------|------|-----------------|---------------|
| `CA_TOKEN_INVALID` | 401 | O CA recusou o token (inválido/expirado ou sem permissão). | Refaça o login; confirme os scopes da app no CA. |
| `CA_ACCESS_DENIED` | 403 | Usuário/aplicação sem autorização para o recurso. | Verifique as permissões do usuário e da app no CA. |
| `CA_NOT_FOUND` | 404 | `userLogin` ou recurso não existe no CA. | Confirme o `userLogin` e o endpoint chamado. |
| `CA_SERVER_ERROR` | 5xx | Falha interna no servidor do CA. | Tente mais tarde; se persistir, acione o time do CA. |
| `CA_REQUEST_ERROR` | 4xx | Requisição inválida para a User/Admin API. | Verifique os parâmetros enviados. |
| `MISSING_CA_API_BASE_URL` | 503 | `CA_API_BASE_URL` não configurado. | Defina `CA_API_BASE_URL` no `backend/.env`. |

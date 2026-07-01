# Entra ID (Microsoft Graph) — Documentação de Endpoints e Campos

Este documento descreve **o Passo 2 da POC**: o acesso ao **Entra ID** via
**Microsoft Graph**. Ele explica **cada endpoint** consultado (o que faz e o que
retorna) e **o significado de cada campo** trazido.

> **Independência:** o Passo 2 (Entra) é totalmente independente do Passo 1
> (CAv4). O Entra é consultado usando o **UPN/e-mail que vem nas claims do
> login**, sem usar nenhum dado do CAv4.

---

## Como funciona (visão geral)

- **Fluxo de autenticação:** `client credentials` (app-only). O backend obtém um
  **token próprio de aplicação** direto no Entra — não há usuário no token.
- **Como o usuário é localizado:** como é app-only, **não existe `/me`**. O
  usuário é buscado pelo **UPN** (e-mail), ex.: `GET /users/{upn}`.
- **Base da API:** `https://graph.microsoft.com/v1.0`
- **Permissões necessárias (tipo Aplicação, com admin consent):**
  - `User.Read.All` — perfil, manager, subordinados, foto, cadeia de gestão.
  - `GroupMember.Read.All` — grupos (`memberOf`).
- **Arquivo de implementação:** `backend/graph_client.py`

---

## Endpoints

### 1. Perfil do usuário
- **Endpoint:** `GET /v1.0/users/{upn}?$select=...`
- **Método no código:** `GraphClient.user()`
- **Para que serve:** retorna o **perfil completo** do usuário no Entra ID.
- **O que retorna:** um objeto com os campos descritos em
  [Campos do perfil](#campos-do-perfil-e-do-manager).

### 2. Gerente / supervisor
- **Endpoint:** `GET /v1.0/users/{upn}/manager?$select=...`
- **Método no código:** `GraphClient.user_manager()`
- **Para que serve:** retorna o **gerente/supervisor direto** do usuário.
- **O que retorna:** um objeto de usuário (mesmos campos do perfil, versão
  enriquecida). Se o usuário não tiver gerente definido, retorna **404**
  (tratado como situação normal).

### 3. Foto do usuário
- **Endpoint:** `GET /v1.0/users/{upn}/photo/$value`
- **Método no código:** `GraphClient.user_photo()`
- **Para que serve:** retorna a **foto de perfil** do usuário.
- **O que retorna:** um objeto com a imagem já convertida para **data URI
  base64**, pronto para uso em `<img src="...">`:
  - `contentType` — tipo da imagem (ex.: `image/jpeg`).
  - `sizeBytes` — tamanho da imagem em bytes.
  - `dataUri` — a imagem em base64 (`data:image/jpeg;base64,...`).
  - Se o usuário **não tiver foto**, retorna `null` (não é erro).

### 4. Cadeia de gestão
- **Endpoint:** `GET /v1.0/users/{upn}/manager?$expand=manager`
- **Método no código:** `GraphClient.user_management_chain()`
- **Para que serve:** retorna o **gerente e o gerente do gerente** (níveis acima
  na hierarquia).
- **O que retorna:** o objeto do gerente direto, com o gerente **dele** aninhado
  no campo `manager`.

### 5. Subordinados diretos
- **Endpoint:** `GET /v1.0/users/{upn}/directReports?$select=...`
- **Método no código:** `GraphClient.user_direct_reports()`
- **Para que serve:** retorna as pessoas que **reportam diretamente** ao usuário.
- **O que retorna:** uma lista (`value`) de objetos de pessoa (campos enxutos:
  `id`, `displayName`, `userPrincipalName`, `mail`, `jobTitle`, `department`).

### 6. Grupos / equipes
- **Endpoint:** `GET /v1.0/users/{upn}/memberOf?$select=...`
- **Método no código:** `GraphClient.user_member_of()`
- **Para que serve:** retorna os **grupos e equipes** aos quais o usuário
  pertence.
- **O que retorna:** uma lista (`value`) de grupos. Veja
  [Campos de grupo](#campos-de-grupo).

---

## Campos do perfil e do manager

Os campos abaixo vêm do endpoint de **perfil** (#1). O **manager** (#2) traz um
subconjunto enriquecido dos mesmos campos.

### Identificação
| Campo | Significado |
|-------|-------------|
| `id` | Identificador único (GUID) do usuário no Entra ID. |
| `displayName` | Nome de exibição completo. |
| `givenName` | Primeiro nome. |
| `surname` | Sobrenome. |
| `userPrincipalName` | UPN — o "login"/e-mail principal no Entra (ex.: `fulano@empresa.com`). |
| `mail` | Endereço de e-mail principal (SMTP). |
| `mailNickname` | Apelido de e-mail (parte antes do @, usado internamente). |

### Cargo e organização
| Campo | Significado |
|-------|-------------|
| `jobTitle` | **Cargo** do usuário (ex.: "Analista de Sistemas"). |
| `department` | Departamento/área. |
| `companyName` | Nome da empresa. |
| `employeeId` | Matrícula/ID do funcionário. |
| `employeeType` | Tipo de vínculo (ex.: `Employee`, `Contractor`). |
| `employeeOrgData` | Objeto com dados organizacionais: `division` (divisão) e `costCenter` (centro de custo). |
| `userType` | `Member` (membro da organização) ou `Guest` (convidado externo). |
| `officeLocation` | Localização do escritório/sala. |

### Contato
| Campo | Significado |
|-------|-------------|
| `mobilePhone` | Telefone celular. |
| `businessPhones` | Lista de telefones comerciais. |
| `faxNumber` | Número de fax. |
| `otherMails` | Lista de e-mails alternativos. |
| `proxyAddresses` | Endereços de e-mail associados (SMTP/legado). |
| `imAddresses` | Endereços de mensagens instantâneas (ex.: Teams/Skype). |

### Localização
| Campo | Significado |
|-------|-------------|
| `streetAddress` | Endereço (rua). |
| `city` | Cidade. |
| `state` | Estado/UF. |
| `country` | País. |
| `postalCode` | CEP. |
| `usageLocation` | País de uso (código ISO, ex.: `BR`) — usado para licenciamento. |
| `preferredLanguage` | Idioma preferido (ex.: `pt-BR`). |

### Datas e ciclo de vida
| Campo | Significado |
|-------|-------------|
| `createdDateTime` | Data de criação da conta no Entra. |
| `employeeHireDate` | Data de admissão do funcionário. |
| `lastPasswordChangeDateTime` | Data da última troca de senha. |
| `ageGroup` | Faixa etária (ex.: `Adult`) — usado por políticas de compliance. |

### Conta e segurança
| Campo | Significado |
|-------|-------------|
| `accountEnabled` | `true` se a conta está ativa; `false` se desativada. |
| `passwordPolicies` | Políticas de senha aplicadas (ex.: `DisablePasswordExpiration`). |
| `assignedLicenses` | Lista de licenças M365 atribuídas (por SKU). |
| `assignedPlans` | Lista de planos/serviços habilitados (ex.: Exchange, Teams). |

### Identificadores locais (Active Directory on-premises)
| Campo | Significado |
|-------|-------------|
| `onPremisesSamAccountName` | Nome de conta no AD local (ex.: matrícula/usuário de rede). |
| `onPremisesDistinguishedName` | DN (Distinguished Name) completo no AD local. |

---

## Campos de grupo

Vêm do endpoint **memberOf** (#6). Cada item da lista `value` representa um grupo.

| Campo | Significado |
|-------|-------------|
| `id` | Identificador único (GUID) do grupo. |
| `displayName` | Nome de exibição do grupo. |
| `description` | Descrição do grupo. |
| `mail` | E-mail do grupo (se for habilitado para e-mail). |
| `groupTypes` | Tipo do grupo (ex.: `Unified` para Microsoft 365; vazio para grupo de segurança). |
| `securityEnabled` | `true` se for um grupo de **segurança** (usado para permissões). |

---

## Observações importantes

- **403 (`GRAPH_ACCESS_DENIED`)**: a app do Entra não tem as permissões de
  **Aplicação** necessárias com **admin consent**. Solução: conceder
  `User.Read.All` e `GroupMember.Read.All` (tipo Aplicação) e clicar em
  "Grant admin consent".
- **404 no manager**: é **normal** quando o usuário não tem gerente definido no
  Entra — não é um erro de configuração.
- **Campos vazios/ausentes**: o Graph só retorna campos que **têm valor**. Se um
  campo não aparecer, significa que não está preenchido no Entra para aquele
  usuário.
- **Campos que exigem permissão extra** (NÃO incluídos nesta POC para evitar
  novos consentimentos): `signInActivity` (último login) exige
  `AuditLog.Read.All`; `aboutMe`, `skills`, `interests` só vêm no endpoint
  `/users/{upn}/profile` (beta).

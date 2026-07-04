import type { CallbackPayload } from './types'

// Payload de exemplo (mesma forma da resposta de /auth/entra-callback),
// para o usuário visualizar a interface sem precisar fazer login.
export const SAMPLE_PAYLOAD: CallbackPayload = {
  status: 'ok',
  entra: {
    userLogin: 'GFZ3',
    name: 'Maria Oliveira Santos',
    email: 'maria.santos@petrobras.com.br',
    claims: {
      sub: '9f2c1a7e-4b3d-4c2a-8e11-2b7a9d0c1e34',
      name: 'Maria Oliveira Santos',
      preferred_username: 'maria.santos@petrobras.com.br',
      upn: 'maria.santos@petrobras.com.br',
      user_login: 'GFZ3',
      email: 'maria.santos@petrobras.com.br',
      given_name: 'Maria',
      family_name: 'Santos',
      tid: 'a1b2c3d4-1111-2222-3333-abcdefabcdef',
      aud: 'f1f4d0d4-aaaa-bbbb-cccc-1234567890ab',
      iss: 'https://login.microsoftonline.com/a1b2c3d4/v2.0',
      iat: 1717600000,
      exp: 1717603600,
      nonce: 'v4Xk9...redacted',
    },
  },
  ca: {
    userLogin: 'GFZ3',
    userPrincipalName: 'maria.santos@petrobras.com.br',
    user_groups: {
      endpoint: 'GET /api/users/GFZ3/user-groups',
      titulo: 'GRUPOS DE USUARIO (User Groups)',
      descricao: 'Grupos de usuário aos quais a pessoa está associada.',
      ok: true,
      data: {
        userLogin: 'GFZ3',
        groups: [
          { id: 101, name: 'ENGENHARIA-SUBMARINA', type: 'FUNCIONAL' },
          { id: 205, name: 'PROJETOS-P77', type: 'PROJETO' },
          { id: 330, name: 'APROVADORES-NIVEL-2', type: 'WORKFLOW' },
        ],
      },
    },
    information_values: {
      endpoint: 'GET /api/users/GFZ3/information-values',
      titulo: 'VALORES DE INFORMACAO (Information Values)',
      descricao: 'Valores de informação autorizados ao usuário.',
      ok: true,
      data: {
        centroCusto: ['CC-4410', 'CC-4412'],
        unidadeOperacional: 'BACIA-DE-SANTOS',
        nivelAcesso: 'CONFIDENCIAL',
      },
    },
    admin_user_details: {
      endpoint: 'GET /api/admin/users/GFZ3',
      titulo: 'DETALHES DO USUARIO (Admin)',
      descricao:
        'Dados cadastrais do usuário (lotação, gerente/supervisor, empresa, etc.).',
      ok: true,
      data: {
        login: 'GFZ3',
        nome: 'Maria Oliveira Santos',
        empresa: 'PETROBRAS',
        lotacao: 'E&P/ENGENHARIA/SUBSEA',
        cargo: 'Engenheira de Equipamentos Sênior',
        gerente: { login: 'ABC1', nome: 'Carlos Pereira Lima' },
        ativo: true,
      },
    },
    admin_enterprise_groups: {
      endpoint: 'GET /api/admin/users/GFZ3/enterprise-groups',
      titulo: 'ENTERPRISE GROUPS (Admin)',
      descricao: 'Grupos corporativos (empresa) do usuário, via Admin API.',
      ok: true,
      data: {
        enterpriseGroups: [
          { id: 'EG-01', name: 'CORP-ENGENHARIA' },
          { id: 'EG-14', name: 'CORP-SEGURANCA-INFO' },
        ],
      },
    },
    admin_roles: {
      endpoint: 'GET /api/admin/users/GFZ3/roles',
      titulo: 'PAPEIS (Roles via Admin)',
      descricao: 'Lista os papéis/perfis do usuário (GET, sem corpo).',
      ok: false,
      error: {
        category: 'ca',
        category_label: 'CA (User API)',
        code: 'CA_HTTP_403',
        message: 'A User API do CA respondeu HTTP 403 (acesso negado) para /roles.',
        cause: 'O token não possui escopo de administração para consultar papéis.',
        resolution:
          'Solicite ao time do CA a permissão de leitura de roles para esta aplicação.',
        detail: 'HTTP 403: Forbidden',
      },
    },
    graph_me: {
      endpoint: 'GET https://graph.microsoft.com/v1.0/users/maria.santos@petrobras.com.br',
      titulo: 'PERFIL ENTRA ID (Graph — /users/{upn})',
      descricao:
        'Perfil completo no Entra ID (cargo, depto, empresa...). Chamado com o UPN das claims do login.',
      ok: true,
      data: {
        displayName: 'Maria Oliveira Santos',
        jobTitle: 'Engenheira de Equipamentos Sênior',
        department: 'Engenharia Submarina',
        officeLocation: 'EDISE - Rio de Janeiro',
        mail: 'maria.santos@petrobras.com.br',
        mobilePhone: '+55 21 99999-0000',
        accountEnabled: true,
      },
    },
    graph_manager: {
      endpoint:
        'GET https://graph.microsoft.com/v1.0/users/maria.santos@petrobras.com.br/manager',
      titulo: 'GERENTE/SUPERVISOR (Graph — /users/{upn}/manager)',
      descricao: 'Gerente/supervisor direto no Entra ID.',
      ok: true,
      data: {
        displayName: 'Carlos Pereira Lima',
        jobTitle: 'Gerente Setorial de Engenharia',
        mail: 'carlos.lima@petrobras.com.br',
      },
    },
    graph_photo: {
      endpoint:
        'GET https://graph.microsoft.com/v1.0/users/maria.santos@petrobras.com.br/photo/$value',
      titulo: 'FOTO DO USUARIO (Graph — /photo/$value)',
      descricao: 'Foto do usuário no Entra ID, devolvida como data URI base64.',
      ok: false,
      error: {
        category: 'entra',
        category_label: 'Entra ID (Graph)',
        code: 'GRAPH_HTTP_404',
        message: 'O usuário não possui foto cadastrada no Entra ID.',
        cause: 'O endpoint /photo/$value retornou 404 (sem foto).',
        resolution: 'Nenhuma ação necessária — a foto é opcional.',
        detail: 'HTTP 404: ImageNotFound',
      },
    },
    graph_management_chain: {
      endpoint:
        'GET https://graph.microsoft.com/v1.0/users/maria.santos@petrobras.com.br/manager?$expand=manager',
      titulo: 'CADEIA DE GESTAO (Graph — manager $expand)',
      descricao: 'Gerente e o gerente do gerente (níveis acima).',
      ok: true,
      data: {
        displayName: 'Carlos Pereira Lima',
        jobTitle: 'Gerente Setorial de Engenharia',
        manager: {
          displayName: 'Ana Beatriz Rocha',
          jobTitle: 'Gerente Geral de E&P',
          mail: 'ana.rocha@petrobras.com.br',
        },
      },
    },
    graph_direct_reports: {
      endpoint:
        'GET https://graph.microsoft.com/v1.0/users/maria.santos@petrobras.com.br/directReports',
      titulo: 'SUBORDINADOS DIRETOS (Graph — /directReports)',
      descricao: 'Pessoas que reportam diretamente ao usuário no Entra ID.',
      ok: true,
      data: {
        value: [
          { displayName: 'João Ferreira', jobTitle: 'Engenheiro Júnior' },
          { displayName: 'Beatriz Nunes', jobTitle: 'Analista de Projetos' },
        ],
      },
    },
    graph_member_of: {
      endpoint:
        'GET https://graph.microsoft.com/v1.0/users/maria.santos@petrobras.com.br/memberOf',
      titulo: 'GRUPOS / EQUIPES (Graph — /memberOf)',
      descricao: 'Grupos e equipes aos quais o usuário pertence no Entra ID.',
      ok: true,
      data: {
        value: [
          { displayName: 'Equipe Subsea P-77', '@odata.type': '#microsoft.graph.group' },
          { displayName: 'Aprovadores Nível 2', '@odata.type': '#microsoft.graph.group' },
        ],
      },
    },
  },
}

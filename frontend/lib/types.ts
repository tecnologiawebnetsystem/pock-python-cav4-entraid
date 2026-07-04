// Estrutura do JSON retornado por GET /auth/entra-callback no backend.

export type Fonte = 'cav4' | 'graph'

export interface EndpointEntry {
  endpoint: string
  titulo: string
  descricao: string
  ok: boolean
  data?: unknown
  error?: unknown
}

export interface EntraInfo {
  userLogin?: string | null
  name?: string | null
  email?: string | null
  claims?: Record<string, unknown>
}

export interface CallbackPayload {
  status?: string
  entra?: EntraInfo
  ca?: Record<string, unknown> & {
    userLogin?: string | null
    userPrincipalName?: string | null
  }
}

// Ordem e fonte canônicas das consultas (espelha CAV4_CONSULTAS no backend).
export const ENDPOINT_CATALOG: { label: string; fonte: Fonte }[] = [
  { label: 'user_groups', fonte: 'cav4' },
  { label: 'information_values', fonte: 'cav4' },
  { label: 'admin_user_details', fonte: 'cav4' },
  { label: 'admin_enterprise_groups', fonte: 'cav4' },
  { label: 'admin_roles', fonte: 'cav4' },
  { label: 'graph_me', fonte: 'graph' },
  { label: 'graph_manager', fonte: 'graph' },
  { label: 'graph_photo', fonte: 'graph' },
  { label: 'graph_management_chain', fonte: 'graph' },
  { label: 'graph_direct_reports', fonte: 'graph' },
  { label: 'graph_member_of', fonte: 'graph' },
]

export interface NormalizedEndpoint extends EndpointEntry {
  label: string
  fonte: Fonte
}

const FALLBACK_FONTE = (label: string): Fonte =>
  label.startsWith('graph') ? 'graph' : 'cav4'

/**
 * Extrai a lista ordenada de endpoints a partir do objeto `ca` do payload.
 * Considera qualquer entrada que seja um objeto com o campo `endpoint`.
 */
export function extractEndpoints(payload: CallbackPayload): NormalizedEndpoint[] {
  const ca = payload.ca ?? {}
  const catalogOrder = new Map(ENDPOINT_CATALOG.map((c, i) => [c.label, i]))
  const fonteByLabel = new Map(ENDPOINT_CATALOG.map((c) => [c.label, c.fonte]))

  const entries: NormalizedEndpoint[] = []
  for (const [label, value] of Object.entries(ca)) {
    if (!value || typeof value !== 'object') continue
    const entry = value as EndpointEntry
    if (typeof entry.endpoint !== 'string') continue
    entries.push({
      label,
      fonte: fonteByLabel.get(label) ?? FALLBACK_FONTE(label),
      endpoint: entry.endpoint,
      titulo: entry.titulo ?? label,
      descricao: entry.descricao ?? '',
      ok: Boolean(entry.ok),
      data: entry.data,
      error: entry.error,
    })
  }

  entries.sort((a, b) => {
    const ia = catalogOrder.has(a.label) ? catalogOrder.get(a.label)! : 999
    const ib = catalogOrder.has(b.label) ? catalogOrder.get(b.label)! : 999
    return ia - ib
  })
  return entries
}

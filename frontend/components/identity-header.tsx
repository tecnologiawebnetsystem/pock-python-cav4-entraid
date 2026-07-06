'use client'

import { User, Mail, IdCard } from 'lucide-react'
import type { CallbackPayload, NormalizedEndpoint } from '@/lib/types'

interface Props {
  payload: CallbackPayload
  endpoints: NormalizedEndpoint[]
}

function getPhoto(endpoints: NormalizedEndpoint[]): string | null {
  const photo = endpoints.find((e) => e.label === 'graph_photo' && e.ok)
  if (!photo) return null
  const data = photo.data as unknown
  // Formato do backend (graph_client): objeto { dataUri, contentType, sizeBytes }.
  if (data && typeof data === 'object' && 'dataUri' in data) {
    const uri = (data as { dataUri?: unknown }).dataUri
    if (typeof uri === 'string' && uri.startsWith('data:image/')) return uri
  }
  // Compatibilidade: caso algum dia a foto venha como string pura.
  if (typeof data === 'string' && data.startsWith('data:image/')) return data
  return null
}

export function IdentityHeader({ payload, endpoints }: Props) {
  const entra = payload.entra ?? {}
  const photo = getPhoto(endpoints)
  const okCount = endpoints.filter((e) => e.ok).length
  const failCount = endpoints.length - okCount

  const initials = (entra.name ?? entra.userLogin ?? '?')
    .split(' ')
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <header className="rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={photo || '/placeholder.svg'}
              alt={`Foto de ${entra.name ?? 'usuário'}`}
              crossOrigin="anonymous"
              className="size-16 rounded-full object-cover ring-2 ring-primary-soft"
            />
          ) : (
            <div className="flex size-16 items-center justify-center rounded-full bg-primary text-xl font-semibold text-primary-foreground">
              {initials}
            </div>
          )}
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold text-foreground">
              {entra.name ?? 'Usuário sem nome'}
            </h1>
            <div className="mt-1 flex flex-col gap-1 text-sm text-muted-foreground sm:flex-row sm:flex-wrap sm:gap-x-4">
              {entra.email && (
                <span className="inline-flex items-center gap-1.5">
                  <Mail size={14} /> {entra.email}
                </span>
              )}
              {entra.userLogin && (
                <span className="inline-flex items-center gap-1.5">
                  <IdCard size={14} /> matrícula: {entra.userLogin}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-lg bg-success-soft px-3 py-1.5 text-sm font-medium text-success">
            {okCount} OK
          </span>
          {failCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-danger-soft px-3 py-1.5 text-sm font-medium text-danger">
              {failCount} falha{failCount > 1 ? 's' : ''}
            </span>
          )}
        </div>
      </div>

      {!payload.entra && (
        <p className="mt-4 inline-flex items-center gap-2 text-sm text-muted-foreground">
          <User size={14} /> Nenhuma informação de identidade (bloco &quot;entra&quot;) encontrada
          no JSON.
        </p>
      )}
    </header>
  )
}

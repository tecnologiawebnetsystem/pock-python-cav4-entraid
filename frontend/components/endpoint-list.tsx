'use client'

import { CheckCircle2, XCircle, Server, Cloud } from 'lucide-react'
import type { Fonte, NormalizedEndpoint } from '@/lib/types'

interface Props {
  endpoints: NormalizedEndpoint[]
  selected: string
  onSelect: (label: string) => void
}

function FonteBadge({ fonte }: { fonte: Fonte }) {
  if (fonte === 'graph') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md bg-accent-soft px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent">
        <Cloud size={11} /> Graph
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-primary-soft px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
      <Server size={11} /> CAv4
    </span>
  )
}

export function EndpointList({ endpoints, selected, onSelect }: Props) {
  return (
    <nav aria-label="Lista de endpoints" className="flex flex-col gap-2">
      {endpoints.map((ep) => {
        const active = ep.label === selected
        return (
          <button
            key={ep.label}
            type="button"
            onClick={() => onSelect(ep.label)}
            aria-current={active}
            className={`group w-full rounded-xl border p-3 text-left transition-colors ${
              active
                ? 'border-primary bg-primary-soft/60'
                : 'border-border bg-surface hover:bg-surface-muted'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <FonteBadge fonte={ep.fonte} />
                {ep.ok ? (
                  <CheckCircle2 size={15} className="text-success" aria-label="Sucesso" />
                ) : (
                  <XCircle size={15} className="text-danger" aria-label="Falha" />
                )}
              </div>
            </div>
            <h3 className="mt-2 text-sm font-medium leading-snug text-foreground text-pretty">
              {ep.titulo}
            </h3>
            <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground" title={ep.endpoint}>
              {ep.endpoint}
            </p>
          </button>
        )
      })}
    </nav>
  )
}

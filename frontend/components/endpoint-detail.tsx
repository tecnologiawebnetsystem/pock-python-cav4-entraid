'use client'

import { useState } from 'react'
import { Check, Copy, CheckCircle2, XCircle, Server, Cloud } from 'lucide-react'
import type { NormalizedEndpoint } from '@/lib/types'
import { JsonView } from './json-view'

interface Props {
  endpoint: NormalizedEndpoint
}

export function EndpointDetail({ endpoint }: Props) {
  const [copied, setCopied] = useState(false)
  const payloadValue = endpoint.ok ? endpoint.data : endpoint.error

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(payloadValue, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // clipboard indisponível — silencioso
    }
  }

  return (
    <div className="flex h-full flex-col rounded-2xl border border-border bg-surface shadow-sm">
      {/* Cabeçalho do endpoint */}
      <div className="border-b border-border p-5">
        <div className="flex flex-wrap items-center gap-2">
          {endpoint.fonte === 'graph' ? (
            <span className="inline-flex items-center gap-1 rounded-md bg-accent-soft px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-accent">
              <Cloud size={12} /> Microsoft Graph
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-md bg-primary-soft px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-primary">
              <Server size={12} /> CAv4
            </span>
          )}
          {endpoint.ok ? (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-success-soft px-2 py-0.5 text-[11px] font-medium text-success">
              <CheckCircle2 size={12} /> Sucesso
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-danger-soft px-2 py-0.5 text-[11px] font-medium text-danger">
              <XCircle size={12} /> Falha
            </span>
          )}
        </div>

        <h2 className="mt-3 text-lg font-semibold text-foreground text-balance">
          {endpoint.titulo}
        </h2>
        {endpoint.descricao && (
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{endpoint.descricao}</p>
        )}

        <div className="mt-3 flex items-center gap-2 rounded-lg bg-surface-muted px-3 py-2">
          <span className="shrink-0 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Endpoint
          </span>
          <code className="scroll-thin overflow-x-auto whitespace-nowrap font-mono text-xs text-foreground">
            {endpoint.endpoint}
          </code>
        </div>
      </div>

      {/* Corpo: JSON retornado */}
      <div className="flex items-center justify-between px-5 pt-4">
        <span className="text-sm font-medium text-foreground">
          {endpoint.ok ? 'JSON retornado' : 'Detalhes do erro'}
        </span>
        <button
          type="button"
          onClick={copy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
        >
          {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
          {copied ? 'Copiado' : 'Copiar JSON'}
        </button>
      </div>

      <div className="scroll-thin min-h-0 flex-1 overflow-auto px-5 pb-5 pt-2">
        <div
          className={`rounded-xl border p-4 ${
            endpoint.ok ? 'border-border bg-surface-muted' : 'border-danger/30 bg-danger-soft/40'
          }`}
        >
          <JsonView value={payloadValue} />
        </div>
      </div>
    </div>
  )
}

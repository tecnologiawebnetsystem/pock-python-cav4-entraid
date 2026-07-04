'use client'

import { useState } from 'react'
import { ChevronRight } from 'lucide-react'

type Json = unknown

function typeOf(value: Json): 'object' | 'array' | 'string' | 'number' | 'boolean' | 'null' {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'array'
  const t = typeof value
  if (t === 'object') return 'object'
  if (t === 'number') return 'number'
  if (t === 'boolean') return 'boolean'
  return 'string'
}

function isImageDataUri(value: Json): value is string {
  return typeof value === 'string' && value.startsWith('data:image/')
}

function Primitive({ value }: { value: Json }) {
  const t = typeOf(value)
  if (t === 'string') {
    return <span className="text-primary break-all">{`"${value as string}"`}</span>
  }
  if (t === 'number') return <span className="text-accent">{String(value)}</span>
  if (t === 'boolean')
    return <span className="font-medium text-danger">{String(value)}</span>
  if (t === 'null') return <span className="italic text-muted-foreground">null</span>
  return <span>{String(value)}</span>
}

function Node({
  keyName,
  value,
  depth,
  defaultOpen,
}: {
  keyName?: string
  value: Json
  depth: number
  defaultOpen?: boolean
}) {
  const t = typeOf(value)
  const isContainer = t === 'object' || t === 'array'
  const [open, setOpen] = useState(defaultOpen ?? depth < 2)

  // Preview de imagem quando o valor é um data URI de imagem (ex.: foto do Graph).
  if (isImageDataUri(value)) {
    return (
      <div className="py-0.5">
        {keyName !== undefined && (
          <span className="text-foreground/80">{`"${keyName}": `}</span>
        )}
        <div className="mt-1 inline-flex flex-col gap-1 rounded-lg border border-border bg-surface-muted p-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={value || '/placeholder.svg'}
            alt="Imagem retornada pelo endpoint"
            className="h-24 w-24 rounded-md object-cover"
            crossOrigin="anonymous"
          />
          <span className="text-[11px] text-muted-foreground">data URI (imagem)</span>
        </div>
      </div>
    )
  }

  if (!isContainer) {
    return (
      <div className="py-0.5 leading-relaxed">
        {keyName !== undefined && (
          <span className="text-foreground/80">{`"${keyName}": `}</span>
        )}
        <Primitive value={value} />
      </div>
    )
  }

  const entries: [string, Json][] =
    t === 'array'
      ? (value as Json[]).map((v, i) => [String(i), v])
      : Object.entries(value as Record<string, Json>)

  const bracketOpen = t === 'array' ? '[' : '{'
  const bracketClose = t === 'array' ? ']' : '}'
  const count = entries.length

  return (
    <div className="leading-relaxed">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="group inline-flex items-center gap-1 rounded px-0.5 text-left hover:bg-surface-muted"
        aria-expanded={open}
      >
        <ChevronRight
          size={14}
          className={`shrink-0 text-muted-foreground transition-transform ${open ? 'rotate-90' : ''}`}
        />
        {keyName !== undefined && (
          <span className="text-foreground/80">{`"${keyName}": `}</span>
        )}
        <span className="text-muted-foreground">{bracketOpen}</span>
        {!open && (
          <span className="text-muted-foreground">
            {count} {count === 1 ? 'item' : 'itens'} {bracketClose}
          </span>
        )}
      </button>

      {open && (
        <div className="ml-[7px] border-l border-border pl-4">
          {entries.map(([k, v]) => (
            <Node key={k} keyName={t === 'array' ? undefined : k} value={v} depth={depth + 1} />
          ))}
          <div className="text-muted-foreground">{bracketClose}</div>
        </div>
      )}
    </div>
  )
}

export function JsonView({ value }: { value: Json }) {
  if (value === undefined) {
    return (
      <p className="text-sm italic text-muted-foreground">
        (nenhum dado retornado por este endpoint)
      </p>
    )
  }
  return (
    <div className="font-mono text-[13px]">
      <Node value={value} depth={0} defaultOpen />
    </div>
  )
}

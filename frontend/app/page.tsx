'use client'

import { useMemo, useState } from 'react'
import { Braces, KeyRound, FileCode2 } from 'lucide-react'
import type { CallbackPayload } from '@/lib/types'
import { extractEndpoints } from '@/lib/types'
import { JsonInput } from '@/components/json-input'
import { IdentityHeader } from '@/components/identity-header'
import { EndpointList } from '@/components/endpoint-list'
import { EndpointDetail } from '@/components/endpoint-detail'
import { JsonView } from '@/components/json-view'

type Aba = 'endpoints' | 'claims' | 'raw'

export default function Page() {
  const [payload, setPayload] = useState<CallbackPayload | null>(null)
  const [selected, setSelected] = useState<string>('')
  const [aba, setAba] = useState<Aba>('endpoints')

  const endpoints = useMemo(
    () => (payload ? extractEndpoints(payload) : []),
    [payload],
  )

  const handleLoad = (p: CallbackPayload) => {
    setPayload(p)
    const eps = extractEndpoints(p)
    setSelected(eps[0]?.label ?? '')
    setAba('endpoints')
  }

  const selectedEndpoint = endpoints.find((e) => e.label === selected) ?? endpoints[0]

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        {/* Título */}
        <div className="mb-6 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Braces size={20} />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">Visualizador de Endpoints</h1>
            <p className="text-sm text-muted-foreground">
              Login CA Petrobras · Entra ID · CAv4 · Microsoft Graph
            </p>
          </div>
        </div>

        {!payload ? (
          <JsonInput onLoad={handleLoad} />
        ) : (
          <div className="flex flex-col gap-5">
            <IdentityHeader
              payload={payload}
              endpoints={endpoints}
              onReset={() => {
                setPayload(null)
                setSelected('')
              }}
            />

            {/* Abas */}
            <div className="flex flex-wrap gap-1 rounded-xl border border-border bg-surface p-1">
              <TabButton
                active={aba === 'endpoints'}
                onClick={() => setAba('endpoints')}
                icon={<FileCode2 size={15} />}
                label={`Endpoints (${endpoints.length})`}
              />
              <TabButton
                active={aba === 'claims'}
                onClick={() => setAba('claims')}
                icon={<KeyRound size={15} />}
                label="Claims do Entra"
              />
              <TabButton
                active={aba === 'raw'}
                onClick={() => setAba('raw')}
                icon={<Braces size={15} />}
                label="JSON completo"
              />
            </div>

            {aba === 'endpoints' &&
              (endpoints.length === 0 ? (
                <EmptyEndpoints />
              ) : (
                <div className="grid gap-5 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
                  <div className="lg:max-h-[calc(100vh-15rem)] lg:overflow-auto lg:pr-1 scroll-thin">
                    <EndpointList
                      endpoints={endpoints}
                      selected={selectedEndpoint?.label ?? ''}
                      onSelect={setSelected}
                    />
                  </div>
                  <div className="lg:h-[calc(100vh-15rem)]">
                    {selectedEndpoint && <EndpointDetail endpoint={selectedEndpoint} />}
                  </div>
                </div>
              ))}

            {aba === 'claims' && (
              <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                <h2 className="mb-3 text-sm font-medium text-foreground">
                  Claims do id_token (Entra)
                </h2>
                <div className="scroll-thin max-h-[calc(100vh-18rem)] overflow-auto rounded-xl border border-border bg-surface-muted p-4">
                  <JsonView value={payload.entra?.claims ?? {}} />
                </div>
              </section>
            )}

            {aba === 'raw' && (
              <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
                <h2 className="mb-3 text-sm font-medium text-foreground">
                  Resposta completa de /auth/entra-callback
                </h2>
                <div className="scroll-thin max-h-[calc(100vh-18rem)] overflow-auto rounded-xl border border-border bg-surface-muted p-4">
                  <JsonView value={payload} />
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </main>
  )
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
        active
          ? 'bg-primary text-primary-foreground'
          : 'text-muted-foreground hover:bg-surface-muted hover:text-foreground'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

function EmptyEndpoints() {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-surface p-10 text-center">
      <FileCode2 size={28} className="mx-auto text-muted-foreground" />
      <p className="mt-3 text-sm text-muted-foreground">
        Nenhum endpoint encontrado no bloco &quot;ca&quot; do JSON. Verifique se colou a resposta
        completa do login.
      </p>
    </div>
  )
}

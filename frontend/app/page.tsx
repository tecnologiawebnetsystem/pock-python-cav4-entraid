'use client'

import { useEffect, useMemo, useState } from 'react'
import useSWR from 'swr'
import { Braces, KeyRound, FileCode2 } from 'lucide-react'
import type { CallbackPayload } from '@/lib/types'
import { extractEndpoints } from '@/lib/types'
import { IdentityHeader } from '@/components/identity-header'
import { EndpointList } from '@/components/endpoint-list'
import { EndpointDetail } from '@/components/endpoint-detail'
import { JsonView } from '@/components/json-view'
import { LoadingScreen, ErrorScreen } from '@/components/status-screen'

type Aba = 'endpoints' | 'claims' | 'raw'
type Fase = 'init' | 'redirecionando' | 'carregando' | 'pronto' | 'erro'

// Rota do backend que inicia o login no CA/Entra (fora do basePath /viewer).
const LOGIN_URL = '/auth/login'

const fetcher = async (url: string): Promise<CallbackPayload> => {
  const res = await fetch(url)
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.error?.message ?? `Falha ao carregar (HTTP ${res.status}).`)
  }
  return res.json()
}

export default function Page() {
  const [fase, setFase] = useState<Fase>('init')
  const [token, setToken] = useState<string | null>(null)
  const [payload, setPayload] = useState<CallbackPayload | null>(null)
  const [erro, setErro] = useState<string>('')

  const [selected, setSelected] = useState<string>('')
  const [aba, setAba] = useState<Aba>('endpoints')

  // Ao abrir a página: decide o que fazer com base na URL.
  //  - ?r=TOKEN -> voltou logado; busca o resultado no backend.
  //  - senão    -> não há sessão nesta página; vai para a tela de login do CA.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const r = params.get('r')

    if (r) {
      setToken(r)
      setFase('carregando')
    } else {
      setFase('redirecionando')
      window.location.href = LOGIN_URL
    }
  }, [])

  // Busca o payload do login quando temos um token (via SWR, sem retry infinito).
  const { data, error } = useSWR(token ? `/auth/result/${token}` : null, fetcher, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })

  useEffect(() => {
    if (!data) return
    setPayload(data)
    const eps = extractEndpoints(data)
    setSelected(eps[0]?.label ?? '')
    setAba('endpoints')
    setFase('pronto')
    // Remove o token da URL depois de carregar (evita recarregar/compartilhar).
    window.history.replaceState({}, '', window.location.pathname)
  }, [data])

  useEffect(() => {
    if (!error) return
    setErro((error as Error).message)
    setFase('erro')
  }, [error])

  const endpoints = useMemo(
    () => (payload ? extractEndpoints(payload) : []),
    [payload],
  )
  const selectedEndpoint = endpoints.find((e) => e.label === selected) ?? endpoints[0]

  const irParaLogin = () => {
    window.location.href = LOGIN_URL
  }

  // --- Telas de transição -------------------------------------------------
  if (fase === 'init' || fase === 'redirecionando') {
    return (
      <LoadingScreen
        title="Verificando sua sessão…"
        subtitle="Estamos confirmando seu login no CA Petrobras (Entra ID)."
      />
    )
  }

  if (fase === 'carregando') {
    return (
      <LoadingScreen
        title="Carregando dados do login…"
        subtitle="Buscando as respostas dos endpoints do CAv4 e do Microsoft Graph."
      />
    )
  }

  if (fase === 'erro' || !payload) {
    return <ErrorScreen message={erro} onLogin={irParaLogin} />
  }

  // --- Página principal ---------------------------------------------------
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

        <div className="flex flex-col gap-5">
          <IdentityHeader payload={payload} endpoints={endpoints} />

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
        Nenhum endpoint encontrado no bloco &quot;ca&quot; da resposta do login.
      </p>
    </div>
  )
}

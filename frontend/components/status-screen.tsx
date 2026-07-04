'use client'

import { Loader2, ShieldAlert, LogIn } from 'lucide-react'

/** Tela central de "verificando sessão" / "carregando dados". */
export function LoadingScreen({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <div className="flex w-full max-w-sm flex-col items-center gap-4 rounded-2xl border border-border bg-surface p-8 text-center shadow-sm">
        <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Loader2 size={24} className="animate-spin" />
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground text-balance">{title}</h2>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">{subtitle}</p>
        </div>
      </div>
    </div>
  )
}

/** Tela de erro com ações para entrar novamente ou colar o JSON manualmente. */
export function ErrorScreen({
  message,
  onLogin,
}: {
  message: string
  onLogin: () => void
}) {
  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <div className="flex w-full max-w-md flex-col items-center gap-5 rounded-2xl border border-border bg-surface p-8 text-center shadow-sm">
        <div className="flex size-12 items-center justify-center rounded-xl bg-danger/10 text-danger">
          <ShieldAlert size={24} />
        </div>
        <div>
          <h2 className="text-base font-semibold text-foreground text-balance">
            Não foi possível carregar os dados do login
          </h2>
          <p className="mt-1 text-sm text-muted-foreground text-pretty">{message}</p>
        </div>
        <button
          type="button"
          onClick={onLogin}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
        >
          <LogIn size={16} />
          Entrar novamente
        </button>
      </div>
    </div>
  )
}

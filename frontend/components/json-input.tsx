'use client'

import { useCallback, useRef, useState } from 'react'
import { ClipboardPaste, FileJson, Upload, Sparkles, AlertCircle } from 'lucide-react'
import type { CallbackPayload } from '@/lib/types'
import { SAMPLE_PAYLOAD } from '@/lib/sample'

interface Props {
  onLoad: (payload: CallbackPayload) => void
}

export function JsonInput({ onLoad }: Props) {
  const [text, setText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const parseAndLoad = useCallback(
    (raw: string) => {
      const trimmed = raw.trim()
      if (!trimmed) {
        setError('Cole o JSON retornado pelo login antes de visualizar.')
        return
      }
      try {
        const parsed = JSON.parse(trimmed) as CallbackPayload
        setError(null)
        onLoad(parsed)
      } catch {
        setError('JSON inválido. Verifique se copiou o conteúdo completo da resposta.')
      }
    },
    [onLoad],
  )

  const readFile = useCallback(
    (file: File) => {
      const reader = new FileReader()
      reader.onload = () => {
        const content = String(reader.result ?? '')
        setText(content)
        parseAndLoad(content)
      }
      reader.readAsText(file)
    },
    [parseAndLoad],
  )

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm sm:p-8">
        <div className="mb-5 flex items-start gap-3">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
            <FileJson size={22} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Carregar resposta do login</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Faça o login normalmente, copie o JSON exibido pelo navegador e cole abaixo (ou
              envie o arquivo <span className="font-mono text-xs">.json</span>).
            </p>
          </div>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            const file = e.dataTransfer.files?.[0]
            if (file) readFile(file)
          }}
          className={`rounded-xl border-2 border-dashed transition-colors ${
            dragging ? 'border-primary bg-primary-soft/50' : 'border-border bg-surface-muted'
          }`}
        >
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder='Cole aqui o JSON, algo como: { "status": "ok", "entra": { ... }, "ca": { ... } }'
            spellCheck={false}
            className="scroll-thin h-52 w-full resize-none rounded-xl bg-transparent p-4 font-mono text-[13px] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground/70"
          />
        </div>

        {error && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
            <AlertCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => parseAndLoad(text)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <ClipboardPaste size={16} />
            Visualizar endpoints
          </button>

          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-surface-muted"
          >
            <Upload size={16} />
            Enviar arquivo .json
          </button>

          <button
            type="button"
            onClick={() => {
              setText(JSON.stringify(SAMPLE_PAYLOAD, null, 2))
              onLoad(SAMPLE_PAYLOAD)
              setError(null)
            }}
            className="ml-auto inline-flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <Sparkles size={16} />
            Ver exemplo
          </button>

          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json,.txt"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) readFile(file)
            }}
          />
        </div>
      </div>
    </div>
  )
}

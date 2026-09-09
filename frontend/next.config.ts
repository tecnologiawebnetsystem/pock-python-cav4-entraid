import type { NextConfig } from 'next'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

// Origem do backend FastAPI quando rodando LOCALMENTE (uvicorn).
// Pode ser sobrescrita por env (BACKEND_ORIGIN), mas o padrão é a porta 8000.
// IMPORTANTE: usamos 127.0.0.1 (IPv4) e NÃO "localhost". No Windows/Node, o
// "localhost" costuma resolver primeiro para o IPv6 ::1, mas o uvicorn escuta
// só em IPv4 — isso causa "connect ECONNREFUSED ::1:8000" no proxy. Fixar o
// IPv4 evita esse erro.
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'
const isDev = process.env.NODE_ENV === 'development'

// Pasta deste próprio arquivo (a raiz real do frontend).
const projectRoot = dirname(fileURLToPath(import.meta.url))

const nextConfig: NextConfig = {
  // Fixa a raiz do workspace nesta pasta. Sem isso, se houver um lockfile
  // (package-lock.json) numa pasta PAI — comum ao baixar o projeto como ZIP ou
  // após um `npm install` acidental na raiz — o Turbopack escolhe a pasta errada
  // e exibe o warning "inferred your workspace root". Apontar para cá resolve.
  turbopack: {
    root: projectRoot,
  },
  // O serviço é montado sob /viewer no vercel.json. O basePath garante que
  // páginas, links e assets (/_next) sejam servidos sob esse prefixo.
  basePath: '/viewer',
  typescript: {
    ignoreBuildErrors: true,
  },
  // PROXY DE DESENVOLVIMENTO (rodar sem Vercel):
  // Em `next dev`, o front (porta 3000) encaminha as rotas do backend para o
  // uvicorn (porta 8000). Assim tudo fica na MESMA origem (localhost:3000),
  // que é o necessário para o fluxo de login OAuth funcionar. `basePath: false`
  // mantém essas rotas na raiz (fora do prefixo /viewer). Em produção (Vercel)
  // isto NÃO é usado — lá o roteamento vem do vercel.json / services.
  async rewrites() {
    if (!isDev) return []
    return [
      { source: '/auth/:path*', destination: `${BACKEND_ORIGIN}/auth/:path*`, basePath: false },
      { source: '/health', destination: `${BACKEND_ORIGIN}/health`, basePath: false },
    ]
  },
}

export default nextConfig

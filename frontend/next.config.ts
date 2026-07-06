import type { NextConfig } from 'next'

// Origem do backend FastAPI quando rodando LOCALMENTE (uvicorn).
// Pode ser sobrescrita por env (BACKEND_ORIGIN), mas o padrão é a porta 8000.
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? 'http://localhost:8000'
const isDev = process.env.NODE_ENV === 'development'

const nextConfig: NextConfig = {
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
  // isto NÃO é usado — lá o roteamento vem do vercel.json / experimentalServices.
  async rewrites() {
    if (!isDev) return []
    return [
      { source: '/auth/:path*', destination: `${BACKEND_ORIGIN}/auth/:path*`, basePath: false },
      { source: '/health', destination: `${BACKEND_ORIGIN}/health`, basePath: false },
    ]
  },
}

export default nextConfig

import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  async rewrites() {
    // Apenas em desenvolvimento local: encaminha as chamadas /api/* para o
    // backend FastAPI rodando na porta 8000, removendo o prefixo /api.
    // Em produção, o roteamento /api -> backend é feito pela plataforma,
    // então este rewrite não é aplicado.
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000'
    if (process.env.NODE_ENV !== 'production') {
      console.log(
        `[v0] rewrite ATIVO (dev): /api/* -> ${backendUrl}/*  (NODE_ENV=${process.env.NODE_ENV})`,
      )
      return [
        {
          source: '/api/:path*',
          destination: `${backendUrl}/:path*`,
        },
      ]
    }
    console.log(
      `[v0] rewrite NAO aplicado: NODE_ENV=${process.env.NODE_ENV} (producao). /api/* nao sera redirecionado para o backend.`,
    )
    return []
  },
}

export default nextConfig

import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  // O serviço é montado sob /viewer no vercel.json. O basePath garante que
  // páginas, links e assets (/_next) sejam servidos sob esse prefixo.
  basePath: '/viewer',
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
}

export default nextConfig

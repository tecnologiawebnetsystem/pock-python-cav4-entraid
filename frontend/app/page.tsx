'use client'

export default function Home() {
  const s = styles

  return (
    <main style={s.main}>
      <div style={s.card}>
        <h1 style={s.titulo}>Acesso CA Petrobras</h1>
        <p style={s.subtitulo}>
          Clique para entrar com suas credenciais corporativas. O CA vai
          autenticar você no Entra e devolver, em um único response, todas as
          informações do usuário.
        </p>

        {/* Navegação completa do browser para o backend.
            Ao voltar, o /api/auth/entra-callback exibe o JSON com tudo. */}
        <a href="/api/auth/login" style={s.botao}>
          Conectar com CA Petrobras
        </a>

        <p style={s.rodape}>
          Você será redirecionado para o login do CA e, ao concluir, verá o
          response com as informações do Entra e do CAv4.
        </p>
      </div>
    </main>
  )
}

const styles: Record<string, React.CSSProperties> = {
  main: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
  },
  card: {
    width: '100%',
    maxWidth: 460,
    background: '#fff',
    borderRadius: 16,
    padding: '40px 32px',
    boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
    textAlign: 'center',
  },
  titulo: {
    margin: '0 0 12px',
    fontSize: 24,
    fontWeight: 700,
    color: '#111',
  },
  subtitulo: {
    margin: '0 0 28px',
    fontSize: 15,
    lineHeight: 1.5,
    color: '#6b7280',
  },
  botao: {
    display: 'inline-block',
    padding: '14px 28px',
    background: '#059669',
    color: '#fff',
    border: 'none',
    borderRadius: 10,
    fontSize: 16,
    fontWeight: 600,
    cursor: 'pointer',
    textDecoration: 'none',
  },
  rodape: {
    margin: '24px 0 0',
    fontSize: 13,
    lineHeight: 1.5,
    color: '#9ca3af',
  },
}

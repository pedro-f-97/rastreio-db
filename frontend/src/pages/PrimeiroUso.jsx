import { useState } from 'react'
import { inicializar } from '../api/configuracao'

function PrimeiroUso({ onInicializado }) {
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState(null)

  async function handleInicializar() {
    setLoading(true)
    setErro(null)
    try {
      await inicializar()
      onInicializado()
    } catch (e) {
      setErro('Erro ao inicializar. Tenta novamente.')
      setLoading(false)
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      gap: 'var(--space-xl)',
      backgroundColor: 'var(--bg-primary)',
      color: 'var(--text-primary)',
    }}>
      <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--font-weight-medium)', margin: 0 }}>
        Bem-vindo ao Rastreio
      </h1>
      <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
        A base de dados está vazia. Criar as categorias predefinidas?
      </p>
      {erro && <p style={{ color: 'var(--danger)', margin: 0 }}>{erro}</p>}
      <button onClick={handleInicializar} disabled={loading}>
        {loading ? 'A inicializar...' : 'Carregar categorias predefinidas'}
      </button>
    </div>
  )
}

export default PrimeiroUso
import { useState } from 'react'
import { inicializar } from '../api/configuracao'
import logoRastreio from '../assets/nariz.svg'

function PrimeiroUso({ onInicializado }) {
  const [loading, setLoading] = useState(false)
  const [erro, setErro] = useState(null)
  const [passo, setPasso] = useState('inicial') // 'inicial' | 'perfil'

  async function handleInicializar(comCategorias, perfil = 'completo') {
    setLoading(true)
    setErro(null)
    try {
      await inicializar(comCategorias, perfil)
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
      height: '80vh',
      gap: 'var(--space-xl)',
      backgroundColor: 'var(--bg-primary)',
      color: 'var(--text-primary)',
    }}>
      <img src={logoRastreio} alt="Rastreio" style={{ width: '80px', height: '80px' }} />
      <h1 style={{ fontSize: 'var(--text-xl)', fontWeight: 'var(--font-weight-medium)', margin: 0 }}>
        Rastreio-DB
      </h1>

      {passo === 'inicial' && (
        <>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            A base de dados está vazia. Como queres começar?
          </p>
          {erro && <p style={{ color: 'var(--danger)', margin: 0 }}>{erro}</p>}
          <div style={{ display: 'flex', gap: 'var(--space-md)' }}>
            <button onClick={() => setPasso('perfil')} disabled={loading}>
              Carregar categorias predefinidas
            </button>
            <button onClick={() => handleInicializar(false)} disabled={loading}>
              {loading ? 'A inicializar...' : 'Começar sem categorias'}
            </button>
          </div>
        </>
      )}

      {passo === 'perfil' && (
        <>
          <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
            Que conjunto de categorias preferes?
          </p>
          {erro && <p style={{ color: 'var(--danger)', margin: 0 }}>{erro}</p>}
          <div style={{ display: 'flex', gap: 'var(--space-md)' }}>
            <button onClick={() => handleInicializar(true, 'minimalista')} disabled={loading}>
              {loading ? 'A inicializar...' : 'Minimalista'}
            </button>
            <button onClick={() => handleInicializar(true, 'completo')} disabled={loading}>
              {loading ? 'A inicializar...' : 'Completo'}
            </button>
          </div>
          <button
            onClick={() => setPasso('inicial')}
            disabled={loading}
            style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
          >
            Voltar
          </button>
        </>
      )}
    </div>
  )
}

export default PrimeiroUso
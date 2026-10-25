import { useState } from 'react'
import { inicializar } from '../api/configuracao'
import logoRastreio from '../assets/nariz.svg'
import '../componentes.css'
import '../App.css'

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
    } catch {
      setErro('Erro ao inicializar. Tenta novamente.')
      setLoading(false)
    }
  }

  return (
    <div className="primeiro-uso">
      <div className="primeiro-uso-cartao">
        <img src={logoRastreio} alt="" className="primeiro-uso-logo" />
        <h1 className="primeiro-uso-marca">rastreio<span className="sidebar-marca-db">.db</span></h1>
        <span className="sidebar-marca-lema">livro de contas</span>

        {passo === 'inicial' && (
          <>
            <p className="primeiro-uso-texto">
              A base de dados está vazia. Como queres começar?
            </p>
            {erro && <p className="erro">{erro}</p>}
            <div className="primeiro-uso-opcoes">
              <button className="primeiro-uso-opcao" onClick={() => setPasso('perfil')} disabled={loading}>
                <strong>Carregar categorias predefinidas</strong>
                <span>Um ponto de partida que podes ajustar depois.</span>
              </button>
              <button className="primeiro-uso-opcao" onClick={() => handleInicializar(false)} disabled={loading}>
                <strong>{loading ? 'A inicializar...' : 'Começar sem categorias'}</strong>
                <span>Crias as tuas de raiz.</span>
              </button>
            </div>
          </>
        )}

        {passo === 'perfil' && (
          <>
            <p className="primeiro-uso-texto">
              Que conjunto de categorias preferes?
            </p>
            {erro && <p className="erro">{erro}</p>}
            <div className="primeiro-uso-opcoes">
              <button className="primeiro-uso-opcao" onClick={() => handleInicializar(true, 'minimalista')} disabled={loading}>
                <strong>{loading ? 'A inicializar...' : 'Minimalista'}</strong>
                <span>Poucas categorias, as essenciais.</span>
              </button>
              <button className="primeiro-uso-opcao" onClick={() => handleInicializar(true, 'completo')} disabled={loading}>
                <strong>{loading ? 'A inicializar...' : 'Completo'}</strong>
                <span>Mais categorias e subcategorias.</span>
              </button>
            </div>
            <button
              className="btn-ghost"
              onClick={() => setPasso('inicial')}
              disabled={loading}
            >
              Voltar
            </button>
          </>
        )}
      </div>
    </div>
  )
}

export default PrimeiroUso
import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Transacoes from './pages/Transacoes'
import Historico from './pages/Historico'
import Categorias from './pages/Categorias'
import Regras from './pages/Regras'
import Estatisticas from './pages/Estatisticas'
import PrimeiroUso from './pages/PrimeiroUso'
import { getEstado } from './api/configuracao'
import './index.css'
import './App.css'
import { totalPorCategorizar } from './api/transacoes'
import Importacao from './pages/Importacao'
import Patrimonio from './pages/Patrimonio'
import Ativos from './pages/Ativos'
import { getPendentes } from './api/patrimonio'
import Contas from './pages/Contas'
import logoRastreio from './assets/nariz.svg'
import { GuiaProvider, useGuia } from './contexts/GuiaContext'
import GuiaDestaque from './components/GuiaDestaque'
import Sobre from './pages/Sobre'
import TiposAtivo from './pages/TiposAtivo'

const GRUPOS_NAV = [
  {
    label: 'Transações',
    items: [
      { to: '/', label: 'Transações', end: true },
      { to: '/historico', label: 'Histórico' },
      { to: '/importacao', label: 'Importação' },
    ],
  },
  {
      label: 'Configuração',
      items: [
          { to: '/categorias', label: 'Categorias' },
          { to: '/regras', label: 'Regras' },
          { to: '/contas', label: 'Contas' },
          { to: '/tipos-ativo', label: 'Tipos de Ativo' },
      ],
  },
  {
    label: 'Análise',
    items: [
      { to: '/estatisticas', label: 'Estatísticas' },
      { to: '/ativos', label: 'Ativos' },
      { to: '/patrimonio', label: 'Património' },
    ],
  },
]

function DisparoAutomaticoGuia({ inicializado, tourVisto }) {
  const { iniciar } = useGuia()

  useEffect(() => {
    if (inicializado && tourVisto === false) {
      iniciar()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inicializado])

  return null
}

function App() {
  const [inicializado, setInicializado] = useState(null)
  const [tourVisto, setTourVisto] = useState(true)
  const [porCategorizar, setPorCategorizar] = useState(0)
  const [pendentesAtivos, setPendentesAtivos] = useState(0)
  const [tema, setTema] = useState(() => document.documentElement.getAttribute('data-theme') || 'dark')

  function alternarTema() {
    const novoTema = tema === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', novoTema)
    try {
      localStorage.setItem('tema', novoTema)
    } catch (e) {
      // localStorage indisponível - o tema não persiste, mas continua a funcionar nesta sessão
    }
    setTema(novoTema)
  }

  function carregarTotaisBadges() {
    totalPorCategorizar().then(res => setPorCategorizar(res.data.total))
    getPendentes().then(res => setPendentesAtivos(res.data.length))
  }

  useEffect(() => {
    if (inicializado) {
      carregarTotaisBadges()
    }
  }, [inicializado])

  useEffect(() => {
    getEstado()
      .then(res => {
        setInicializado(res.data.inicializado)
        setTourVisto(res.data.tour_visto)
      })
      .catch(() => setInicializado(true))
  }, [])

  if (inicializado === null) return null

  return (
    <BrowserRouter>
      <GuiaProvider>
        <DisparoAutomaticoGuia inicializado={inicializado} tourVisto={tourVisto} />
        <GuiaDestaque />
        <div className="app-layout">
          {inicializado && (
            <nav className="sidebar">
              <div className="sidebar-logo">
                <img src={logoRastreio} alt="Rastreio" />
                <span>Rastreio-DB</span>
              </div>

              {GRUPOS_NAV.map(grupo => (
                <div key={grupo.label} className="sidebar-grupo">
                  <div className="sidebar-grupo-titulo">
                    {grupo.label}
                  </div>
                  {grupo.items.map(({ to, label, end }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={end}
                      className={({ isActive }) => `sidebar-link${isActive ? ' activo' : ''}`}
                    >
                      <span className="sidebar-link-conteudo">
                        {label}
                        {label === 'Transações' && porCategorizar > 0 && (
                          <span className="badge-contador">{porCategorizar}</span>
                        )}
                        {label === 'Ativos' && pendentesAtivos > 0 && (
                          <span className="badge-contador">{pendentesAtivos}</span>
                        )}
                      </span>
                    </NavLink>
                  ))}
                </div>
                 ))}

              <div className="sidebar-rodape">
                <NavLink
                  to="/sobre"
                  className={({ isActive }) => `sidebar-link${isActive ? ' activo' : ''}`}
                >
                  Conceitos
                </NavLink>
              </div>

              <button onClick={alternarTema} className="sidebar-toggle-tema">
                <span
                  className="sidebar-toggle-tema-metade-escura"
                  style={{ flex: tema === 'dark' ? 4 : 1 }}
                />
                <span
                  className="sidebar-toggle-tema-metade-clara"
                  style={{ flex: tema === 'dark' ? 1 : 4 }}
                />
              </button>
            </nav>
          )}
          <main className="app-main">
            <Routes>
              {!inicializado
                ? <Route path="*" element={<PrimeiroUso onInicializado={() => setInicializado(true)} />} />
                : <>
                  {/* ALTERAÇÃO #6: onDadosAlterados passado a Transações e Ativos */}
                  <Route path="/" element={<Transacoes onDadosAlterados={carregarTotaisBadges} />} />
                  <Route path="/historico" element={<Historico />} />
                  <Route path="/categorias" element={<Categorias />} />
                  <Route path="/regras" element={<Regras />} />
                  <Route path="/estatisticas" element={<Estatisticas />} />
                  <Route path="/importacao" element={<Importacao />} />
                  <Route path="*" element={<Navigate to="/" />} />
                  <Route path="/patrimonio" element={<Patrimonio />} />
                  <Route path="/contas" element={<Contas />} />
                  <Route path="/sobre" element={<Sobre />} />
                  <Route path="/tipos-ativo" element={<TiposAtivo />} />
                  <Route path="/ativos" element={<Ativos onDadosAlterados={carregarTotaisBadges} />} />
                </>
              }
            </Routes>
          </main>
        </div>
      </GuiaProvider>
    </BrowserRouter>
  )
}

export default App
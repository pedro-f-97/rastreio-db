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
import Icone from './components/Icone'

const GRUPOS_NAV = [
  {
    label: 'Transações',
    items: [
      { to: '/', label: 'Transações', icone: 'transacoes', end: true },
      { to: '/historico', label: 'Histórico', icone: 'historico' },
      { to: '/importacao', label: 'Importação', icone: 'importacao' },
    ],
  },
  {
      label: 'Configuração',
      items: [
          { to: '/categorias', label: 'Categorias', icone: 'categorias' },
          { to: '/regras', label: 'Regras', icone: 'regras' },
          { to: '/contas', label: 'Contas', icone: 'contas' },
          { to: '/tipos-ativo', label: 'Tipos de Ativo', icone: 'tipos' },
      ],
  },
  {
    label: 'Análise',
    items: [
      { to: '/estatisticas', label: 'Estatísticas', icone: 'estatisticas' },
      { to: '/ativos', label: 'Ativos', icone: 'ativos' },
      { to: '/patrimonio', label: 'Património', icone: 'patrimonio' },
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
    } catch {
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
                <img src={logoRastreio} alt="" />
                <div className="sidebar-marca">
                  <span className="sidebar-marca-nome">rastreio<span className="sidebar-marca-db">.db</span></span>
                  <span className="sidebar-marca-lema">livro de contas</span>
                </div>
              </div>

              <div className="sidebar-grupos">
                {GRUPOS_NAV.map((grupo, i) => (
                  <div key={grupo.label} className="sidebar-grupo">
                    <div className="sidebar-grupo-titulo">
                      <span className="sidebar-grupo-numero">{String(i + 1).padStart(2, '0')}</span>
                      {grupo.label}
                    </div>
                    {grupo.items.map(({ to, label, icone, end }) => (
                      <NavLink
                        key={to}
                        to={to}
                        end={end}
                        className={({ isActive }) => `sidebar-link${isActive ? ' activo' : ''}`}
                      >
                        <Icone nome={icone} tamanho={17} />
                        <span className="sidebar-link-conteudo">
                          {label}
                          {label === 'Transações' && porCategorizar > 0 && (
                            <span className="badge-contador" title="Transações por categorizar">{porCategorizar}</span>
                          )}
                          {label === 'Ativos' && pendentesAtivos > 0 && (
                            <span className="badge-contador" title="Movimentos pendentes">{pendentesAtivos}</span>
                          )}
                        </span>
                      </NavLink>
                    ))}
                  </div>
                ))}
              </div>

              <div className="sidebar-rodape">
                <NavLink
                  to="/sobre"
                  className={({ isActive }) => `sidebar-link${isActive ? ' activo' : ''}`}
                >
                  <Icone nome="conceitos" tamanho={17} />
                  <span className="sidebar-link-conteudo">Conceitos</span>
                </NavLink>

                <button
                  onClick={alternarTema}
                  className="sidebar-toggle-tema"
                  title={tema === 'dark' ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'}
                >
                  <span className={`sidebar-toggle-opcao${tema === 'dark' ? ' activa' : ''}`}>
                    <Icone nome="lua" tamanho={14} /> Escuro
                  </span>
                  <span className={`sidebar-toggle-opcao${tema === 'light' ? ' activa' : ''}`}>
                    <Icone nome="sol" tamanho={14} /> Claro
                  </span>
                </button>
              </div>
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
                  <Route path="/importacao" element={<Importacao onDadosAlterados={carregarTotaisBadges} />} />
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
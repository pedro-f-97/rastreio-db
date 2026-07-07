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
import { totalPorCategorizar } from './api/transacoes'
import Importacao from './pages/Importacao'
import Patrimonio from './pages/Patrimonio'
import { getPendentes } from './api/patrimonio'
import Contas from './pages/Contas'
import logoRastreio from './assets/nariz.svg'
import { GuiaProvider, useGuia } from './contexts/GuiaContext'
import GuiaDestaque from './components/GuiaDestaque'

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
      ],
  },
  {
    label: 'Análise',
    items: [
      { to: '/estatisticas', label: 'Estatísticas' },
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
  const [pendentesPatrimonio, setPendentesPatrimonio] = useState(0)
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

  useEffect(() => {
    if (inicializado) {
      totalPorCategorizar().then(res => setPorCategorizar(res.data.total))
      getPendentes().then(res => setPendentesPatrimonio(res.data.length))
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
        <div style={{ display: 'flex', height: '100vh' }}>
          {inicializado && (
            <nav style={{
              width: '200px',
              backgroundColor: 'var(--bg-secondary)',
              borderRight: '1px solid var(--border)',
              padding: '24px 0',
              display: 'flex',
              flexDirection: 'column',
              gap: '0',
            }}>
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '0 16px 24px',
                gap: '8px',
              }}>
                <img src={logoRastreio} alt="Rastreio" style={{ width: '40px', height: '40px' }} />
                <span style={{ color: 'var(--text-secondary)', fontSize: '14px', letterSpacing: '1px' }}>
                  Rastreio-DB
                </span>
              </div>

              {GRUPOS_NAV.map(grupo => (
                <div key={grupo.label} style={{ marginBottom: '16px' }}>
                  <div style={{
                    padding: '0 16px 6px',
                    fontSize: '10px',
                    fontWeight: 500,
                    letterSpacing: '0.08em',
                    color: 'var(--text-secondary)',
                    opacity: 0.6,
                    textTransform: 'uppercase',
                  }}>
                    {grupo.label}
                  </div>
                  {grupo.items.map(({ to, label, end }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={end}
                      style={({ isActive }) => ({
                        display: 'block',
                        padding: '8px 16px',
                        color: isActive ? 'var(--accent)' : 'var(--text-primary)',
                        textDecoration: 'none',
                        backgroundColor: isActive ? 'var(--bg-tertiary)' : 'transparent',
                        borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                      })}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        {label}
                        {label === 'Transações' && porCategorizar > 0 && (
                          <span style={{
                            background: 'var(--danger)',
                            color: '#fff',
                            borderRadius: '999px',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            padding: '0.1rem 0.45rem',
                            marginLeft: '0.5rem',
                          }}>
                            {porCategorizar}
                          </span>
                        )}
                        {label === 'Património' && pendentesPatrimonio > 0 && (
                          <span style={{
                            background: 'var(--danger)',
                            color: '#fff',
                            borderRadius: '999px',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            padding: '0.1rem 0.45rem',
                            marginLeft: '0.5rem',
                          }}>
                            {pendentesPatrimonio}
                          </span>
                        )}
                      </span>
                    </NavLink>
                  ))}
                </div>
              ))}

              <button
                onClick={alternarTema}
                style={{
                  marginTop: 'auto',
                  marginLeft: '16px',
                  marginRight: '16px',
                  width: 'calc(100% - 32px)',
                  height: '24px',
                  padding: 0,
                  display: 'flex',
                  overflow: 'hidden',
                  border: '1px solid var(--border)',
                }}
              >
                <span style={{ flex: tema === 'dark' ? 4 : 1, backgroundColor: '#000000' }} />
                <span style={{ flex: tema === 'dark' ? 1 : 4, backgroundColor: '#ffffff' }} />
              </button>
            </nav>
          )}
          <main style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
            <Routes>
              {!inicializado
                ? <Route path="*" element={<PrimeiroUso onInicializado={() => setInicializado(true)} />} />
                : <>
                  <Route path="/" element={<Transacoes />} />
                  <Route path="/historico" element={<Historico />} />
                  <Route path="/categorias" element={<Categorias />} />
                  <Route path="/regras" element={<Regras />} />
                  <Route path="/estatisticas" element={<Estatisticas />} />
                  <Route path="/importacao" element={<Importacao />} />
                  <Route path="*" element={<Navigate to="/" />} />
                  <Route path="/patrimonio" element={<Patrimonio />} />
                  <Route path="/contas" element={<Contas />} />
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
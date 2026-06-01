import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Transacoes from './pages/Transacoes'
import Categorias from './pages/Categorias'
import Regras from './pages/Regras'
import Estatisticas from './pages/Estatisticas'
import PrimeiroUso from './pages/PrimeiroUso'
import { getEstado } from './api/configuracao'
import './index.css'
import { totalPorCategorizar } from './api/transacoes'

function App() {
  const [inicializado, setInicializado] = useState(null)
  const [porCategorizar, setPorCategorizar] = useState(0)

  useEffect(() => {
    if (inicializado) {
        totalPorCategorizar().then(res => setPorCategorizar(res.data.total))
    }
  }, [inicializado])

  useEffect(() => {
    getEstado()
      .then(res => setInicializado(res.data.inicializado))
      .catch(() => setInicializado(true)) // em caso de erro, não bloqueia
  }, [])

  if (inicializado === null) return null // ainda a carregar

  return (
    <BrowserRouter>
      <div style={{ display: 'flex', height: '100vh' }}>
        {inicializado && (
          <nav style={{
            width: '200px',
            backgroundColor: 'var(--bg-secondary)',
            borderRight: '1px solid var(--border)',
            padding: '24px 0',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}>
            <div style={{ padding: '0 16px 24px', color: 'var(--text-secondary)', fontSize: '12px', letterSpacing: '1px' }}>
              RASTREIO
            </div>
            {[
              { to: '/', label: 'Transações', badge: porCategorizar },
              { to: '/categorias', label: 'Categorias' },
              { to: '/regras', label: 'Regras' },
              { to: '/estatisticas', label: 'Estatísticas' },
            ].map(({ to, label, badge }) => (
              <NavLink
                key={to}
                to={to}
                end
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
                    {badge > 0 && (
                        <span style={{
                            background: 'var(--danger)',
                            color: '#fff',
                            borderRadius: '999px',
                            fontSize: '0.7rem',
                            fontWeight: 700,
                            padding: '0.1rem 0.45rem',
                            marginLeft: '0.5rem',
                        }}>
                            {badge}
                        </span>
                    )}
                </span>
              </NavLink>
            ))}
          </nav>
        )}
        <main style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
          <Routes>
            {!inicializado
              ? <Route path="*" element={<PrimeiroUso onInicializado={() => setInicializado(true)} />} />
              : <>
                  <Route path="/" element={<Transacoes />} />
                  <Route path="/categorias" element={<Categorias />} />
                  <Route path="/regras" element={<Regras />} />
                  <Route path="/estatisticas" element={<Estatisticas />} />
                  <Route path="*" element={<Navigate to="/" />} />
                </>
            }
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
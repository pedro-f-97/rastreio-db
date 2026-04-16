import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Transacoes from './pages/Transacoes'
import Categorias from './pages/Categorias'
import Regras from './pages/Regras'
import './index.css'

function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', height: '100vh' }}>
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
            { to: '/', label: 'Transações' },
            { to: '/categorias', label: 'Categorias' },
            { to: '/regras', label: 'Regras' },
          ].map(({ to, label }) => (
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
              {label}
            </NavLink>
          ))}
        </nav>

        <main style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
          <Routes>
            <Route path="/" element={<Transacoes />} />
            <Route path="/categorias" element={<Categorias />} />
            <Route path="/regras" element={<Regras />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
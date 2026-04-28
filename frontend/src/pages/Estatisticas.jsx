import { useState, useEffect } from 'react';
import { obterResumoMensal, obterPorCategoria, obterPorSubcategoria } from '../api/estatisticas';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    LineChart, Line, Legend, CartesianGrid, PieChart, Pie, Cell
} from 'recharts';
import './Estatisticas.css';

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function labelMes(ano, mes) {
    return `${MESES[mes - 1]} ${ano}`;
}

export default function Estatisticas() {
    const [resumo, setResumo] = useState(null);
    const [porCategoria, setPorCategoria] = useState([]);
    const [porSubcategoria, setPorSubcategoria] = useState([]);
    const [categoriaSeleccionada, setCategoriaSeleccionada] = useState(null);

    useEffect(() => {
        obterResumoMensal().then(res => setResumo(res.data));
        obterPorCategoria().then(res => setPorCategoria(res.data));
        obterPorSubcategoria().then(res => setPorSubcategoria(res.data));
    }, []);

    if (!resumo) return <p className="carregando">A carregar...</p>;

    const dadosGrafico = resumo.meses.map(m => ({
        label: labelMes(m.ano, m.mes),
        Receitas: m.receitas,
        Despesas: m.despesas,
        Investimento: m.investimento,
        Saldo: m.saldo,
    }));

    const CORES = [
        '#6366f1', '#22c55e', '#ef4444', '#f59e0b', '#3b82f6',
        '#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4'
    ];

    return (
        <div className="estatisticas-page">
            <h1>Estatísticas</h1>

            {/* RESUMO GLOBAL */}
            <section className="secao">
                <h2>Resumo global</h2>
                <div className="cartoes">
                    <div className="cartao">
                        <span className="cartao-label">Média mensal de despesas</span>
                        <span className="cartao-valor">{resumo.media_mensal.toFixed(2)} €</span>
                    </div>
                    <div className="cartao">
                        <span className="cartao-label">Mediana mensal de despesas</span>
                        <span className="cartao-valor">{resumo.mediana_mensal.toFixed(2)} €</span>
                    </div>
                </div>
            </section>

            {/* GRÁFICO EVOLUÇÃO */}
            <section className="secao">
                <h2>Evolução mensal</h2>
                <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={dadosGrafico} margin={{ top: 10, right: 20, left: 20, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" />
                        <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                        <Tooltip
                            contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                            labelStyle={{ color: 'var(--text-primary)' }}
                            formatter={(v) => `${v.toFixed(2)} €`}
                        />
                        <Legend wrapperStyle={{ color: 'var(--text-secondary)', paddingTop: '2rem' }} />
                        <Bar dataKey="Receitas" fill="var(--success)" />
                        <Bar dataKey="Despesas" fill="var(--danger)" />
                        <Bar dataKey="Investimento" fill="var(--accent)" />
                    </BarChart>
                </ResponsiveContainer>
            </section>

                        {/* TABELA MENSAL */}
            <section className="secao">
                <h2>Detalhe por mês</h2>
                <table className="tabela-stats">
                    <thead>
                        <tr>
                            <th>Mês</th>
                            <th>Receitas</th>
                            <th>Despesas</th>
                            <th>Investimento</th>
                            <th>Saldo</th>
                        </tr>
                    </thead>
                    <tbody>
                        {resumo.meses.map(m => (
                            <tr key={`${m.ano}-${m.mes}`}>
                                <td>{labelMes(m.ano, m.mes)}</td>
                                <td className="valor-positivo">{m.receitas.toFixed(2)} €</td>
                                <td className="valor-negativo">{m.despesas.toFixed(2)} €</td>
                                <td>{m.investimento.toFixed(2)} €</td>
                                <td className={m.saldo >= 0 ? 'valor-positivo' : 'valor-negativo'}>
                                    {m.saldo.toFixed(2)} €
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </section>

            {/* POR CATEGORIA */}
            <section className="secao">
                <h2>Por categoria</h2>
                <table className="tabela-stats">
                    <thead>
                        <tr>
                            <th>Categoria</th>
                            <th>Média mensal</th>
                            <th>Mediana mensal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {porCategoria.map(c => (
                            <tr key={c.categoria_id}>
                                <td>{c.categoria_nome}</td>
                                <td>{c.media.toFixed(2)} €</td>
                                <td>{c.mediana.toFixed(2)} €</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </section>
            {/* PIE CHART */}
            <section className="secao">
                <h2>Distribuição por categoria</h2>
                <div className="pie-container">
                    <div className="pie-wrapper">
                        <p className="pie-titulo">Categorias</p>
                        <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                                <Pie
                                    data={porSubcategoria}
                                    dataKey="total"
                                    nameKey="categoria_nome"
                                    cx="50%"
                                    cy="50%"
                                    outerRadius={100}
                                    onClick={d => setCategoriaSeleccionada(
                                        categoriaSeleccionada?.categoria_id === d.categoria_id ? null : d
                                    )}
                                    cursor="pointer"
                                >
                                    {porSubcategoria.map((_, i) => (
                                        <Cell
                                            key={i}
                                            fill={CORES[i % CORES.length]}
                                            opacity={
                                                categoriaSeleccionada === null ||
                                                categoriaSeleccionada.categoria_id === porSubcategoria[i].categoria_id
                                                    ? 1 : 0.3
                                            }
                                        />
                                    ))}
                                </Pie>
                                <Tooltip
                                    contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                                    formatter={(v, _, props) => [`${v.toFixed(2)} €`, props.payload.categoria_nome]}
                                />
                                <Legend />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>

                    {categoriaSeleccionada && (
                        <div className="pie-wrapper">
                            <p className="pie-titulo">{categoriaSeleccionada.categoria_nome}</p>
                            <ResponsiveContainer width="100%" height={300}>
                                <PieChart>
                                    <Pie
                                        data={categoriaSeleccionada.subcategorias}
                                        dataKey="total"
                                        nameKey="subcategoria_nome"
                                        cx="50%"
                                        cy="50%"
                                        outerRadius={100}
                                    >
                                        {categoriaSeleccionada.subcategorias.map((_, i) => (
                                            <Cell key={i} fill={CORES[i % CORES.length]} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                                        formatter={(v, _, props) => [`${v.toFixed(2)} €`, props.payload.subcategoria_nome]}
                                    />
                                    <Legend />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
}
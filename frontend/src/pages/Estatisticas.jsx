import { useState, useEffect } from 'react';
import { obterResumoMensal, obterPorCategoria, obterPorSubcategoria, obterDetalheMensal } from '../api/estatisticas';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    LineChart, Line, Legend, CartesianGrid, Cell
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
    const [mesSeleccionado, setMesSeleccionado] = useState(null);
    const [detalheMes, setDetalheMes] = useState([]);

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

    function toggleMes(ano, mes) {
        if (mesSeleccionado?.ano === ano && mesSeleccionado?.mes === mes) {
            setMesSeleccionado(null);
            setDetalheMes([]);
        } else {
            setMesSeleccionado({ ano, mes });
            obterDetalheMensal(ano, mes).then(res => setDetalheMes(res.data));
        }
    }

    const totalGeral = porSubcategoria.reduce((soma, c) => soma + c.total, 0);

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
                        {resumo.meses.map(m => {
                            const seleccionado = mesSeleccionado?.ano === m.ano && mesSeleccionado?.mes === m.mes;
                            return (
                                <>
                                    <tr
                                        key={`${m.ano}-${m.mes}`}
                                        onClick={() => toggleMes(m.ano, m.mes)}
                                        className={`linha-mes ${seleccionado ? 'linha-mes-activa' : ''}`}
                                    >
                                        <td>{labelMes(m.ano, m.mes)}</td>
                                        <td className="valor-positivo">{m.receitas.toFixed(2)} €</td>
                                        <td className="valor-negativo">{m.despesas.toFixed(2)} €</td>
                                        <td>{m.investimento.toFixed(2)} €</td>
                                        <td className={m.saldo >= 0 ? 'valor-positivo' : 'valor-negativo'}>
                                            {m.saldo.toFixed(2)} €
                                        </td>
                                    </tr>
                                    {seleccionado && detalheMes.map(cat => {
                                        const classe =
                                            cat.tipo === 'receita' ? 'valor-positivo' :
                                            cat.tipo === 'investimento' ? '' :
                                            cat.total >= 0 ? 'valor-positivo' : 'valor-negativo';

                                        return (
                                            <>
                                                <tr key={`cat-${cat.categoria_id}`} className="linha-categoria-detalhe">
                                                    <td className="celula-categoria-nome">↳ {cat.categoria_nome}</td>
                                                    <td className={classe} colSpan={4}>{cat.total.toFixed(2)} €</td>
                                                </tr>
                                                {cat.subcategorias.map(sub => (
                                                    <tr key={`sub-${sub.subcategoria_nome}`} className="linha-subcategoria-detalhe">
                                                        <td className="celula-subcategoria-nome">　　{sub.subcategoria_nome}</td>
                                                        <td className={classe} colSpan={4}>{sub.total.toFixed(2)} €</td>
                                                    </tr>
                                                ))}
                                            </>
                                        );
                                    })}
                                </>
                            );
                        })}
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
            {/* DISTRIBUIÇÃO POR CATEGORIA */}
                <section className="secao">
                    <h2>Distribuição por categoria</h2>
                    <ResponsiveContainer width="100%" height={porSubcategoria.length * 48 + 40}>
                        <BarChart
                            data={porSubcategoria}
                            layout="vertical"
                            margin={{ top: 0, right: 60, left: 120, bottom: 0 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                            <XAxis
                                type="number"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                                tickFormatter={v => `${v.toFixed(0)} €`}
                            />
                            <YAxis
                                type="category"
                                dataKey="categoria_nome"
                                tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                                width={115}
                            />
                            <Tooltip
                                contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                                formatter={(v, _, props) => {
                                    const pct = totalGeral > 0 ? (v / totalGeral * 100).toFixed(1) : 0;
                                    return [`${v.toFixed(2)} € (${pct}%)`, 'Total'];
                                }}
                            />
                            <Bar dataKey="total" radius={[0, 4, 4, 0]} onClick={item => setCategoriaSeleccionada(
                                categoriaSeleccionada?.categoria_id === item.categoria_id ? null : item
                            )} style={{ cursor: 'pointer' }}>
                                {porSubcategoria.map((_, i) => (
                                    <Cell key={i} fill={CORES[i % CORES.length]} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>

                    {categoriaSeleccionada && (
                        <div className="subcategoria-detalhe">
                            <h3>{categoriaSeleccionada.categoria_nome}</h3>
                            <ResponsiveContainer width="100%" height={categoriaSeleccionada.subcategorias.length * 48 + 40}>
                                <BarChart
                                    data={categoriaSeleccionada.subcategorias}
                                    layout="vertical"
                                    margin={{ top: 0, right: 60, left: 140, bottom: 0 }}
                                >
                                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                                    <XAxis
                                        type="number"
                                        tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                                        tickFormatter={v => `${v.toFixed(0)} €`}
                                    />
                                    <YAxis
                                        type="category"
                                        dataKey="subcategoria_nome"
                                        tick={{ fill: 'var(--text-secondary)', fontSize: 12 }}
                                        width={135}
                                    />
                                    <Tooltip
                                        contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                                        formatter={(v, _, props) => {
                                            const pct = categoriaSeleccionada.total > 0 ? (v / categoriaSeleccionada.total * 100).toFixed(1) : 0;
                                            return [`${v.toFixed(2)} € (${pct}%)`, 'Total'];
                                        }}
                                    />
                                    <Bar dataKey="total" radius={[0, 4, 4, 0]}>
                                        {categoriaSeleccionada.subcategorias.map((_, i) => (
                                            <Cell key={i} fill={CORES[i % CORES.length]} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    )}
                </section>
        </div>
    );
}
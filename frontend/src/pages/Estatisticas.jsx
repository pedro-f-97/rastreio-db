import { useState, useEffect, useMemo, Fragment } from 'react';
import { obterResumoMensal, obterPorCategoria, obterPorSubcategoria } from '../api/estatisticas';
import {
    ComposedChart, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    Line, Legend, CartesianGrid, Cell
} from 'recharts';
import './Estatisticas.css';

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function labelMes(ano, mes) {
    return `${MESES[mes - 1]} ${ano}`;
}

function calcularLimiteSerie(valores, multiplicador = 4) {
    const absolutos = valores.map(Math.abs).filter(v => v > 0);
    if (absolutos.length < 3) {
        return { limite: Infinity, valoresNormais: absolutos, extremos: [] };
    }
    const ordenados = [...absolutos].sort((a, b) => a - b);
    const meio = Math.floor(ordenados.length / 2);
    const mediana = ordenados.length % 2 === 0
        ? (ordenados[meio - 1] + ordenados[meio]) / 2
        : ordenados[meio];
    const limite = mediana * multiplicador;
    return {
        limite,
        valoresNormais: absolutos.filter(v => v <= limite),
        extremos: absolutos.filter(v => v > limite),
    };
}

function maiorValor(lista) {
    return lista.length > 0 ? Math.max(...lista) : 0;
}

function calcularMediana(valores) {
    if (valores.length === 0) return 0;
    const ordenados = [...valores].sort((a, b) => a - b);
    const meio = Math.floor(ordenados.length / 2);
    return ordenados.length % 2 === 0
        ? (ordenados[meio - 1] + ordenados[meio]) / 2
        : ordenados[meio];
}

function calcularMedia(valores) {
    if (valores.length === 0) return 0;
    return valores.reduce((s, v) => s + v, 0) / valores.length;
}

const CORES = [
    '#6366f1', '#22c55e', '#ef4444', '#f59e0b', '#3b82f6',
    '#ec4899', '#14b8a6', '#f97316', '#8b5cf6', '#06b6d4'
];

export default function Estatisticas() {
    const [resumo, setResumo] = useState(null);
    const [porCategoria, setPorCategoria] = useState([]);
    const [porSubcategoria, setPorSubcategoria] = useState([]);
    const [categoriaSeleccionada, setCategoriaSeleccionada] = useState(null);
    const [categoriaExpandida, setCategoriaExpandida] = useState(null);
    const [anoSeleccionado, setAnoSeleccionado] = useState('todos');
    const [incluirOutliers, setIncluirOutliers] = useState(false);

    useEffect(() => {
        obterResumoMensal().then(res => setResumo(res.data));
    }, []);

    useEffect(() => {
        setCategoriaSeleccionada(null);
        setCategoriaExpandida(null);
        obterPorCategoria(anoSeleccionado).then(res => setPorCategoria(res.data));
        obterPorSubcategoria(anoSeleccionado).then(res => setPorSubcategoria(res.data));
    }, [anoSeleccionado]);

    const MULTIPLICADOR_EXTREMO = 4;

    const { dadosGrafico, dadosGraficoFiltrados, dominioValores, totalExtremos } = useMemo(() => {
        if (!resumo) {
            return { dadosGrafico: [], dadosGraficoFiltrados: [], dominioValores: ['auto', 'auto'], totalExtremos: 0 };
        }

        const dadosGrafico = resumo.meses.map(m => ({
            ano: m.ano,
            label: labelMes(m.ano, m.mes),
            Receitas: m.receitas,
            Despesas: m.despesas,
            Investimento: m.investimento,
            Poupança: m.poupanca,
            'Taxa de Poupança': m.receitas > 0 ? parseFloat(((m.poupanca / m.receitas) * 100).toFixed(1)) : null,
        }));

        const filtrados = anoSeleccionado === 'todos'
            ? dadosGrafico
            : dadosGrafico.filter(m => m.ano === parseInt(anoSeleccionado));

        const analiseReceitas = calcularLimiteSerie(filtrados.map(m => m.Receitas), MULTIPLICADOR_EXTREMO);
        const analiseDespesas = calcularLimiteSerie(filtrados.map(m => m.Despesas), MULTIPLICADOR_EXTREMO);
        const analiseInvestimento = calcularLimiteSerie(filtrados.map(m => m.Investimento), MULTIPLICADOR_EXTREMO);

        const extremos = analiseReceitas.extremos.length + analiseDespesas.extremos.length + analiseInvestimento.extremos.length;

        const maxNormal = Math.max(
            maiorValor(analiseReceitas.valoresNormais),
            maiorValor(analiseDespesas.valoresNormais),
            maiorValor(analiseInvestimento.valoresNormais),
        );

        const dominio = (!incluirOutliers && extremos > 0)
            ? [-Math.ceil(maxNormal * 1.15), Math.ceil(maxNormal * 1.15)]
            : ['auto', 'auto'];

        return {
            dadosGrafico,
            dadosGraficoFiltrados: filtrados,
            dominioValores: dominio,
            totalExtremos: extremos,
        };
    }, [resumo, anoSeleccionado, incluirOutliers]);

    const { cardDespesas, cardPoupanca, cardTaxa } = useMemo(() => {
        const despesas = dadosGraficoFiltrados.map(m => m.Despesas);
        const poupancas = dadosGraficoFiltrados.map(m => m.Poupança);
        const taxas = dadosGraficoFiltrados
            .filter(m => m['Taxa de Poupança'] !== null)
            .map(m => m['Taxa de Poupança']);

        return {
            cardDespesas: {
                mediana: calcularMediana(despesas),
                media: calcularMedia(despesas),
            },
            cardPoupanca: {
                mediana: calcularMediana(poupancas),
                media: calcularMedia(poupancas),
            },
            cardTaxa: {
                mediana: calcularMediana(taxas),
                media: calcularMedia(taxas),
            },
        };
    }, [dadosGraficoFiltrados]);

    if (!resumo) return <p className="carregando">A carregar...</p>;

    const anosDisponiveis = [...new Set(resumo.meses.map(m => m.ano))].sort();
    const totalGeral = porSubcategoria.reduce((soma, c) => soma + Math.abs(c.total), 0);

    function classeValor(v) {
        return v >= 0 ? 'valor-positivo' : 'valor-negativo';
    }

    return (
        <div className="estatisticas-page">
            <div className="secao-cabecalho" style={{ borderBottom: 'none', paddingBottom: 0 }}>
                <h1>Estatísticas</h1>
                <select
                    value={anoSeleccionado}
                    onChange={e => setAnoSeleccionado(e.target.value)}
                    className="filtro-ano"
                >
                    <option value="todos">Todos</option>
                    {anosDisponiveis.map(ano => (
                        <option key={ano} value={ano}>{ano}</option>
                    ))}
                </select>
            </div>

            {/* RESUMO GLOBAL */}
            <section className="secao">
                <h2>Resumo global</h2>
                <div className="cartoes">
                    <div className="cartao">
                        <span className="cartao-titulo">Despesas mensais</span>
                        <div className="cartao-corpo">
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Mediana</span>
                                <span className={`cartao-metade-valor ${classeValor(cardDespesas.mediana)}`}>
                                    {cardDespesas.mediana.toFixed(2)} €
                                </span>
                            </div>
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Média</span>
                                <span className={`cartao-metade-valor ${classeValor(cardDespesas.media)}`}>
                                    {cardDespesas.media.toFixed(2)} €
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="cartao">
                        <span className="cartao-titulo">Poupança mensal</span>
                        <div className="cartao-corpo">
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Mediana</span>
                                <span className={`cartao-metade-valor ${classeValor(cardPoupanca.mediana)}`}>
                                    {cardPoupanca.mediana.toFixed(2)} €
                                </span>
                            </div>
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Média</span>
                                <span className={`cartao-metade-valor ${classeValor(cardPoupanca.media)}`}>
                                    {cardPoupanca.media.toFixed(2)} €
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="cartao">
                        <span className="cartao-titulo">Taxa de poupança mensal</span>
                        <div className="cartao-corpo">
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Mediana</span>
                                <span className={`cartao-metade-valor ${classeValor(cardTaxa.mediana)}`}>
                                    {cardTaxa.mediana.toFixed(1)}%
                                </span>
                            </div>
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Média</span>
                                <span className={`cartao-metade-valor ${classeValor(cardTaxa.media)}`}>
                                    {cardTaxa.media.toFixed(1)}%
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* GRÁFICO EVOLUÇÃO — VALORES */}
            <section className="secao">
                <h2>Evolução mensal</h2>

                {totalExtremos > 0 && (
                    <div className="aviso-outlier">
                        <span>
                            {incluirOutliers
                                ? `Escala a incluir ${totalExtremos === 1 ? '1 valor extremo' : `${totalExtremos} valores extremos`}`
                                : `Escala ajustada para ignorar ${totalExtremos === 1 ? '1 valor extremo' : `${totalExtremos} valores extremos`}`}
                        </span>
                        <button onClick={() => setIncluirOutliers(!incluirOutliers)}>
                            {incluirOutliers ? 'Ignorar valores extremos' : 'Incluir valores extremos na escala'}
                        </button>
                    </div>
                )}

                <ResponsiveContainer width="100%" height={400}>
                    <ComposedChart data={dadosGraficoFiltrados} margin={{ top: 10, right: 40, left: 20, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" />
                        <YAxis
                            tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                            tickFormatter={v => `${v} €`}
                            domain={dominioValores}
                            allowDataOverflow={true}
                        />
                        <Tooltip
                            contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                            labelStyle={{ color: 'var(--text-primary)' }}
                            formatter={(v) => `${v.toFixed(2)} €`}
                        />
                        <Legend wrapperStyle={{ color: 'var(--text-secondary)', paddingTop: '2rem' }} />
                        <Bar dataKey="Receitas" fill="var(--success)" />
                        <Bar dataKey="Despesas" fill="var(--danger)" />
                        <Bar dataKey="Investimento" fill="var(--type-investimento-text)" />
                    </ComposedChart>
                </ResponsiveContainer>
            </section>

            {/* GRÁFICO TAXA DE POUPANÇA */}
            <section className="secao">
                <h2>Taxa de poupança mensal</h2>
                <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={dadosGraficoFiltrados} margin={{ top: 10, right: 40, left: 20, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" />
                        <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
                        <Tooltip
                            contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                            labelStyle={{ color: 'var(--text-primary)' }}
                            formatter={(v) => v !== null ? `${v.toFixed(1)}%` : '—'}
                        />
                        <Legend wrapperStyle={{ color: 'var(--text-secondary)', paddingTop: '2rem' }} />
                        <Line dataKey="Taxa de Poupança" type="monotone" stroke="#a78bfa" strokeWidth={2} dot={false} connectNulls={false} />
                    </ComposedChart>
                </ResponsiveContainer>
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
                        {[...porCategoria]
                            .sort((a, b) => Math.abs(b.media) - Math.abs(a.media))
                            .map(c => (
                                <Fragment key={c.categoria_id}>
                                    <tr
                                        className="linha-ano"
                                        onClick={() => setCategoriaExpandida(
                                            categoriaExpandida === c.categoria_id ? null : c.categoria_id
                                        )}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        <td>
                                            <span className="seta-expansao">
                                                {categoriaExpandida === c.categoria_id ? '▼' : '▶'}
                                            </span>
                                            {c.categoria_nome}
                                        </td>
                                        <td className={classeValor(c.media)}>{c.media.toFixed(2)} €</td>
                                        <td className={classeValor(c.mediana)}>{c.mediana.toFixed(2)} €</td>
                                    </tr>
                                    {categoriaExpandida === c.categoria_id &&
                                        [...c.subcategorias]
                                            .sort((a, b) => Math.abs(b.media) - Math.abs(a.media))
                                            .map(sub => (
                                                <tr key={sub.subcategoria_nome} className="linha-mes">
                                                    <td className="celula-subcategoria-nome">{sub.subcategoria_nome}</td>
                                                    <td className={classeValor(sub.media)}>{sub.media.toFixed(2)} €</td>
                                                    <td className={classeValor(sub.mediana)}>{sub.mediana.toFixed(2)} €</td>
                                                </tr>
                                            ))
                                    }
                                </Fragment>
                            ))}
                    </tbody>
                </table>
            </section>

            {/* DISTRIBUIÇÃO POR CATEGORIA */}
            <section className="secao">
                <h2>Distribuição por categoria</h2>
                <ResponsiveContainer width="100%" height={porSubcategoria.length * 32 + 40}>
                    <BarChart
                        data={[...porSubcategoria].sort((a, b) => Math.abs(b.total) - Math.abs(a.total))}
                        layout="vertical"
                        background={false}
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
                            labelStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
                            itemStyle={{ color: 'var(--text-primary)' }}
                            formatter={(v) => {
                                const pct = totalGeral > 0 ? (Math.abs(v) / totalGeral * 100).toFixed(1) : 0;
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
                        <ResponsiveContainer width="100%" height={categoriaSeleccionada.subcategorias.length * 32 + 40}>
                            <BarChart
                                data={[...categoriaSeleccionada.subcategorias].sort((a, b) => Math.abs(b.total) - Math.abs(a.total))}
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
                                    labelStyle={{ color: 'var(--text-primary)', fontWeight: 600 }}
                                    itemStyle={{ color: 'var(--text-primary)' }}
                                    formatter={(v) => {
                                        const pct = totalGeral > 0 ? (Math.abs(v) / totalGeral * 100).toFixed(1) : 0;
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

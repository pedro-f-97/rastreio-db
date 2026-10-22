import { useState, useEffect, useMemo, Fragment } from 'react';
import { obterResumoMensal, obterPorCategoria, obterPorSubcategoria } from '../api/estatisticas';
import {
    ComposedChart, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    Line, Legend, CartesianGrid, Cell, LabelList
} from 'recharts';
import './Estatisticas.css';
import '../componentes.css';
import { formatarEuros, formatarEurosEixo, formatarPercentagem, labelMes } from '../utils/formatacao';

function calcularLimiteSerie(valores, multiplicador = 4) {
    const absolutos = valores.map(Math.abs).filter(v => v > 0);
    if (absolutos.length < 3) {
        return { limite: Infinity, valoresNormais: absolutos, extremos: [] };
    }
    const limite = calcularMediana(absolutos) * multiplicador;
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

// Barras horizontais da distribuição da despesa, para as categorias e para as
// subcategorias da categoria escolhida
function GraficoDistribuicao({ dados, chaveSeleccionada = null, onSeleccionar }) {
    return (
        <ResponsiveContainer width="100%" height={dados.length * 32 + 40}>
            <BarChart data={dados} layout="vertical" margin={{ top: 0, right: 160, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={formatarEurosEixo} />
                <YAxis type="category" dataKey="nome" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} width={140} />
                <Tooltip
                    contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                    labelStyle={{ color: 'var(--text-primary)' }}
                    cursor={{ fill: 'var(--bg-tertiary)' }}
                    formatter={(_v, _nome, item) => [item.payload.rotulo, 'Despesa']}
                />
                <Bar
                    dataKey="valor"
                    fill="var(--danger)"
                    radius={[0, 4, 4, 0]}
                    onClick={onSeleccionar ? item => onSeleccionar(item.payload) : undefined}
                    style={onSeleccionar ? { cursor: 'pointer' } : undefined}
                >
                    {dados.map(d => (
                        <Cell key={d.chave} fillOpacity={chaveSeleccionada === null || chaveSeleccionada === d.chave ? 1 : 0.4} />
                    ))}
                    <LabelList dataKey="rotulo" position="right" fill="var(--text-secondary)" fontSize={11} />
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    );
}

export default function Estatisticas() {
    const [resumo, setResumo] = useState(null);
    const [erro, setErro] = useState(null);
    const [porCategoria, setPorCategoria] = useState([]);
    const [porSubcategoria, setPorSubcategoria] = useState([]);
    const [categoriaExpandida, setCategoriaExpandida] = useState(null);
    const [categoriaDistribuicao, setCategoriaDistribuicao] = useState(null);
    const [anoSeleccionado, setAnoSeleccionado] = useState('todos');
    const [incluirOutliers, setIncluirOutliers] = useState(false);

    useEffect(() => {
        obterResumoMensal()
            .then(res => setResumo(res.data))
            .catch(() => setErro('Não foi possível carregar as estatísticas.'));
    }, []);

    useEffect(() => {
        // Ao trocar de ano depressa, a resposta de um ano anterior pode chegar
        // depois da do ano escolhido: é ignorada
        let cancelado = false;
        obterPorCategoria(anoSeleccionado).then(res => {
            if (!cancelado) setPorCategoria(res.data);
        });
        obterPorSubcategoria(anoSeleccionado).then(res => {
            if (!cancelado) setPorSubcategoria(res.data);
        });
        return () => {
            cancelado = true;
        };
    }, [anoSeleccionado]);

    // Só a despesa: as percentagens são sobre o total gasto no período. Uma
    // categoria ou subcategoria em que os reembolsos cobrem a despesa fica de fora
    const distribuicao = useMemo(() => {
        const despesas = porSubcategoria.filter(c => c.tipo === 'despesa' && c.total < 0);
        const totalDespesa = despesas.reduce((s, c) => s - c.total, 0);
        const item = (chave, nome, total) => ({
            chave,
            nome,
            valor: -total,
            rotulo: `${formatarEuros(-total)} · ${formatarPercentagem(-total / totalDespesa * 100)}`,
        });
        return despesas
            .map(c => ({
                ...item(c.categoria_id, c.categoria_nome, c.total),
                subcategorias: c.subcategorias
                    .filter(sub => sub.total < 0)
                    .map(sub => item(sub.subcategoria_nome, sub.subcategoria_nome, sub.total))
                    .sort((a, b) => b.valor - a.valor),
            }))
            .sort((a, b) => b.valor - a.valor);
    }, [porSubcategoria]);

    const categoriaDistribuicaoDados = distribuicao.find(c => c.chave === categoriaDistribuicao);

    const MULTIPLICADOR_EXTREMO = 4;

    const { dadosGraficoFiltrados, dominioValores, totalExtremos } = useMemo(() => {
        if (!resumo) {
            return { dadosGraficoFiltrados: [], dominioValores: ['auto', 'auto'], totalExtremos: 0 };
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
        // Taxa do período: soma da poupança / soma das receitas, como no Histórico
        const receitas = dadosGraficoFiltrados.reduce((s, m) => s + m.Receitas, 0);
        const poupanca = poupancas.reduce((s, v) => s + v, 0);

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
                periodo: receitas > 0 ? (poupanca / receitas) * 100 : null,
                mediana: taxas.length > 0 ? calcularMediana(taxas) : null,
            },
        };
    }, [dadosGraficoFiltrados]);

    if (erro) return <p className="erro">{erro}</p>;
    if (!resumo) return <p className="carregando">A carregar...</p>;

    const anosDisponiveis = [...new Set(resumo.meses.map(m => m.ano))].sort();

    function classeValor(v) {
        return v >= 0 ? 'valor-positivo' : 'valor-negativo';
    }

    return (
        <div className="estatisticas-page">
            <div className="secao-cabecalho" style={{ borderBottom: 'none', paddingBottom: 0 }}>
                <h1 className="titulo-pagina">Estatísticas</h1>
                <select
                    value={anoSeleccionado}
                    onChange={e => {
                        setAnoSeleccionado(e.target.value);
                        setCategoriaExpandida(null);
                        setCategoriaDistribuicao(null);
                    }}
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
                <h2 className="titulo-secao">Resumo global</h2>
                <div className="cartoes">
                    <div className="cartao">
                        <span className="cartao-titulo">Despesas mensais</span>
                        <div className="cartao-corpo">
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Mediana</span>
                                <span className={`cartao-metade-valor ${classeValor(cardDespesas.mediana)}`}>
                                    {formatarEuros(cardDespesas.mediana)}
                                </span>
                            </div>
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Média</span>
                                <span className={`cartao-metade-valor ${classeValor(cardDespesas.media)}`}>
                                    {formatarEuros(cardDespesas.media)}
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
                                    {formatarEuros(cardPoupanca.mediana)}
                                </span>
                            </div>
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Média</span>
                                <span className={`cartao-metade-valor ${classeValor(cardPoupanca.media)}`}>
                                    {formatarEuros(cardPoupanca.media)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="cartao">
                        <span className="cartao-titulo">Taxa de poupança</span>
                        <div className="cartao-corpo">
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Do período</span>
                                <span className={`cartao-metade-valor ${cardTaxa.periodo !== null ? classeValor(cardTaxa.periodo) : ''}`}>
                                    {formatarPercentagem(cardTaxa.periodo)}
                                </span>
                            </div>
                            <div className="cartao-metade">
                                <span className="cartao-metade-label">Mediana mensal</span>
                                <span className={`cartao-metade-valor ${cardTaxa.mediana !== null ? classeValor(cardTaxa.mediana) : ''}`}>
                                    {formatarPercentagem(cardTaxa.mediana)}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* GRÁFICO EVOLUÇÃO — VALORES */}
            <section className="secao">
                <h2 className="titulo-secao">Evolução mensal</h2>

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
                            tickFormatter={formatarEurosEixo}
                            domain={dominioValores}
                            allowDataOverflow={true}
                        />
                        <Tooltip
                            contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                            labelStyle={{ color: 'var(--text-primary)' }}
                            formatter={(v) => formatarEuros(v)}
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
                <h2 className="titulo-secao">Taxa de poupança mensal</h2>
                <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={dadosGraficoFiltrados} margin={{ top: 10, right: 40, left: 20, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" />
                        <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
                        <Tooltip
                            contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                            labelStyle={{ color: 'var(--text-primary)' }}
                            formatter={(v) => formatarPercentagem(v)}
                        />
                        <Legend wrapperStyle={{ color: 'var(--text-secondary)', paddingTop: '2rem' }} />
                        <Line dataKey="Taxa de Poupança" type="monotone" stroke="#a78bfa" strokeWidth={2} dot={false} connectNulls={false} />
                    </ComposedChart>
                </ResponsiveContainer>
            </section>

            {/* DISTRIBUIÇÃO DA DESPESA */}
            <section className="secao">
                <h2 className="titulo-secao">Distribuição da despesa</h2>
                {distribuicao.length === 0 ? (
                    <p className="estado-vazio">Sem despesas no período.</p>
                ) : (
                    <GraficoDistribuicao
                        dados={distribuicao}
                        chaveSeleccionada={categoriaDistribuicao}
                        onSeleccionar={c => setCategoriaDistribuicao(categoriaDistribuicao === c.chave ? null : c.chave)}
                    />
                )}

                {categoriaDistribuicaoDados && (
                    <div className="subcategoria-detalhe">
                        <h3>{categoriaDistribuicaoDados.nome}</h3>
                        <GraficoDistribuicao dados={categoriaDistribuicaoDados.subcategorias} />
                    </div>
                )}
            </section>

            {/* POR CATEGORIA */}
            <section className="secao">
                <h2 className="titulo-secao">Por categoria</h2>
                <table className="tabela-base tabela-stats">
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
                                        <td className={classeValor(c.media)}>{formatarEuros(c.media)}</td>
                                        <td className={classeValor(c.mediana)}>{formatarEuros(c.mediana)}</td>
                                    </tr>
                                    {categoriaExpandida === c.categoria_id &&
                                        [...c.subcategorias]
                                            .sort((a, b) => Math.abs(b.media) - Math.abs(a.media))
                                            .map(sub => (
                                                <tr key={sub.subcategoria_nome} className="linha-mes">
                                                    <td className="celula-subcategoria-nome">{sub.subcategoria_nome}</td>
                                                    <td className={classeValor(sub.media)}>{formatarEuros(sub.media)}</td>
                                                    <td className={classeValor(sub.mediana)}>{formatarEuros(sub.mediana)}</td>
                                                </tr>
                                            ))
                                    }
                                </Fragment>
                            ))}
                    </tbody>
                </table>
            </section>
        </div>
    );
}
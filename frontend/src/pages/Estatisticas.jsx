import { useState, useEffect, useMemo, Fragment } from 'react';
import { obterResumoMensal, obterPorCategoria, obterPorSubcategoria, obterExtraordinarias } from '../api/estatisticas';
import {
    ComposedChart, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    Line, Legend, CartesianGrid, Cell, LabelList, ReferenceLine
} from 'recharts';
import './Estatisticas.css';
import '../componentes.css';
import {
    classeValor, formatarEuros, formatarEurosEixo, formatarPercentagem, labelMes, NOMES_CLASSE_DESPESA
} from '../utils/formatacao';

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

// Sem meses (só o mês em curso no período), não há média: mostra-se «—»
function calcularMedia(valores) {
    if (valores.length === 0) return null;
    return valores.reduce((s, v) => s + v, 0) / valores.length;
}

// Taxa de poupança dos `n` meses que acabam em cada mês. Soma a poupança e as
// receitas da janela antes de dividir, para que um salário que caia no fim do
// mês anterior não crie picos. Sem `n` meses de histórico, não há valor, nem
// no mês em curso, que está incompleto. Os meses vêm ordenados, como os
// devolve o resumo mensal
function taxaMovel(meses, n) {
    const indice = m => m.ano * 12 + m.mes;
    const primeiro = meses.length > 0 ? indice(meses[0]) : 0;
    return meses.map(m => {
        if (m.em_curso) return null;
        const fim = indice(m);
        if (fim - n + 1 < primeiro) return null;
        const janela = meses.filter(x => indice(x) > fim - n && indice(x) <= fim);
        const receitas = janela.reduce((s, x) => s + x.receitas, 0);
        const poupanca = janela.reduce((s, x) => s + x.poupanca, 0);
        return receitas > 0 ? parseFloat(((poupanca / receitas) * 100).toFixed(1)) : null;
    });
}

// Um cartão do resumo global com dois valores lado a lado. Em percentagem, um
// valor null (sem receitas no período) mostra-se sem cor
function CartaoMetades({ titulo, metades, percentagem = false }) {
    return (
        <div className="cartao">
            <span className="cartao-titulo">{titulo}</span>
            <div className="cartao-corpo">
                {metades.map(([label, valor]) => (
                    <div className="cartao-metade" key={label}>
                        <span className="cartao-metade-label">{label}</span>
                        {percentagem ? (
                            <span className={`cartao-metade-valor ${valor !== null ? classeValor(valor, 1) : ''}`}>
                                {formatarPercentagem(valor)}
                            </span>
                        ) : (
                            <span className={`cartao-metade-valor ${classeValor(valor)}`}>{formatarEuros(valor)}</span>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
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

// Grupos da tabela «Por categoria», pela ordem em que aparecem. O `campo` é o
// total do tipo em cada mês do resumo mensal, de onde vêm a média e a mediana
// do grupo, e o `campoTipico` o mesmo total sem as extraordinárias
const GRUPOS_CATEGORIA = [
    { tipo: 'despesa', titulo: 'Despesas', campo: 'Despesas', campoTipico: 'DespesaTipica' },
    { tipo: 'receita', titulo: 'Receitas', campo: 'Receitas', campoTipico: 'Receitas' },
    { tipo: 'investimento', titulo: 'Investimento', campo: 'Investimento', campoTipico: 'Investimento' },
];

// As partes da despesa do mês típico, pela ordem da barra da composição
const PARTES_TIPICO = [
    { campo: 'Essencial', nome: NOMES_CLASSE_DESPESA.essencial, cor: 'var(--chart-7)' },
    { campo: 'Evitavel', nome: NOMES_CLASSE_DESPESA.evitavel, cor: 'var(--chart-3)' },
    { campo: 'SemClasse', nome: 'Sem classificação', cor: 'var(--text-secondary)' },
];

// A despesa do mês típico (a média sem as extraordinárias) separada pela
// classificação, numa barra com o valor médio e a percentagem de cada parte
function ComposicaoTipico({ partes }) {
    const total = partes.reduce((s, p) => s + p.valor, 0);
    if (total <= 0) return null;
    return (
        <div className="cartao">
            <span className="cartao-titulo">Composição do mês típico</span>
            <div className="composicao-barra">
                {partes.filter(p => p.valor > 0).map(p => (
                    <div key={p.campo} style={{ width: `${(p.valor / total) * 100}%`, background: p.cor }} title={p.nome} />
                ))}
            </div>
            <div className="composicao-legenda">
                {partes.map(p => (
                    <span key={p.campo}>
                        <span className="composicao-cor" style={{ background: p.cor }} />
                        {p.nome}: <strong>{formatarEuros(-p.valor)}</strong>{' '}
                        <span className="composicao-percentagem">({formatarPercentagem((p.valor / total) * 100, 0)})</span>
                    </span>
                ))}
            </div>
        </div>
    );
}

export default function Estatisticas() {
    const [resumo, setResumo] = useState(null);
    const [erro, setErro] = useState(null);
    const [porCategoria, setPorCategoria] = useState([]);
    const [porSubcategoria, setPorSubcategoria] = useState([]);
    const [extraordinarias, setExtraordinarias] = useState(null);
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
        obterExtraordinarias(anoSeleccionado).then(res => {
            if (!cancelado) setExtraordinarias(res.data);
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

        // As médias móveis calculam-se sobre todos os meses, antes do filtro de
        // ano: assim, janeiro de um ano usa os meses do ano anterior
        const movel3 = taxaMovel(resumo.meses, 3);
        const movel12 = taxaMovel(resumo.meses, 12);

        const dadosGrafico = resumo.meses.map((m, i) => ({
            ano: m.ano,
            label: labelMes(m.ano, m.mes),
            Receitas: m.receitas,
            Despesas: m.despesas,
            Investimento: m.investimento,
            Poupança: m.poupanca,
            // A despesa por classe, para o mês típico e a sua composição; o
            // gráfico não as mostra
            Essencial: m.despesa_essencial,
            Evitavel: m.despesa_evitavel,
            Extraordinaria: m.despesa_extraordinaria,
            SemClasse: m.despesa_sem_classe,
            DespesaTipica: m.despesas - m.despesa_extraordinaria,
            emCurso: m.em_curso,
            'Média de 3 meses': movel3[i],
            'Média de 12 meses': movel12[i],
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

    const { cardTipico, cardPoupanca, cardTaxa, partesTipico } = useMemo(() => {
        // As médias e as taxas contam só os meses completos; as somas do
        // período contam todos
        const meses = dadosGraficoFiltrados.filter(m => !m.emCurso);
        const soma = (campo, lista = meses) => lista.reduce((s, m) => s + m[campo], 0);
        // Sem as extraordinárias, a poupança do mês sobe o que elas custaram
        const poupancasTipicas = meses.map(m => m.Poupança - m.Extraordinaria);
        // Taxa do período: soma da poupança / soma das receitas, como no Histórico
        const receitas = soma('Receitas');
        const taxa = poupanca => (receitas > 0 ? (poupanca / receitas) * 100 : null);

        return {
            cardTipico: {
                media: calcularMedia(meses.map(m => m.DespesaTipica)),
                extraordinarias: soma('Extraordinaria', dadosGraficoFiltrados),
            },
            cardPoupanca: {
                media: calcularMedia(meses.map(m => m.Poupança)),
                semExtraordinarias: calcularMedia(poupancasTipicas),
            },
            cardTaxa: {
                periodo: taxa(soma('Poupança')),
                semExtraordinarias: taxa(poupancasTipicas.reduce((s, v) => s + v, 0)),
            },
            // Média mensal de cada parte, em positivo para a barra
            partesTipico: PARTES_TIPICO.map(p => ({ ...p, valor: -calcularMedia(meses.map(m => m[p.campo])) })),
        };
    }, [dadosGraficoFiltrados]);

    if (erro) return <p className="erro">{erro}</p>;
    if (!resumo) return <p className="carregando">A carregar...</p>;

    const anosDisponiveis = [...new Set(resumo.meses.map(m => m.ano))].sort();

    return (
        <div className="estatisticas-page">
            <div className="secao-cabecalho secao-cabecalho-limpo">
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
                    <CartaoMetades
                        titulo="Mês típico (sem extraordinárias)"
                        metades={[
                            ['Despesa média', cardTipico.media],
                            ['Extraordinárias no período', cardTipico.extraordinarias],
                        ]}
                    />
                    <CartaoMetades
                        titulo="Poupança mensal"
                        metades={[
                            ['Média', cardPoupanca.media],
                            ['Sem extraordinárias', cardPoupanca.semExtraordinarias],
                        ]}
                    />
                    <CartaoMetades
                        titulo="Taxa de poupança"
                        percentagem
                        metades={[
                            ['Do período', cardTaxa.periodo],
                            ['Sem extraordinárias', cardTaxa.semExtraordinarias],
                        ]}
                    />
                </div>
                <ComposicaoTipico partes={partesTipico} />
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
                <h2 className="titulo-secao">Taxa de poupança</h2>
                <ResponsiveContainer width="100%" height={300}>
                    <ComposedChart data={dadosGraficoFiltrados} margin={{ top: 10, right: 100, left: 20, bottom: 60 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" />
                        <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
                        <Tooltip
                            contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
                            labelStyle={{ color: 'var(--text-primary)' }}
                            formatter={(v) => formatarPercentagem(v)}
                        />
                        <Legend wrapperStyle={{ color: 'var(--text-secondary)', paddingTop: '2rem' }} />
                        {cardTaxa.periodo !== null && (
                            <ReferenceLine
                                y={cardTaxa.periodo}
                                stroke="var(--text-secondary)"
                                strokeDasharray="6 4"
                                ifOverflow="extendDomain"
                                label={{
                                    value: `Período: ${formatarPercentagem(cardTaxa.periodo)}`,
                                    position: 'right',
                                    fill: 'var(--text-secondary)',
                                    fontSize: 11,
                                }}
                            />
                        )}
                        <Line dataKey="Média de 3 meses" type="monotone" stroke="var(--accent)" strokeWidth={2} dot={false} connectNulls={false} />
                        <Line dataKey="Média de 12 meses" type="monotone" stroke="var(--chart-2)" strokeWidth={2} dot={false} connectNulls={false} />
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

            {/* DESPESAS EXTRAORDINÁRIAS */}
            <section className="secao">
                <h2 className="titulo-secao">Despesas extraordinárias</h2>
                {extraordinarias === null ? null : extraordinarias.transacoes.length === 0 ? (
                    <p className="estado-vazio">Sem despesas extraordinárias no período.</p>
                ) : (
                    <table className="tabela-base tabela-stats">
                        <thead>
                            <tr>
                                <th>Data</th>
                                <th>Descrição</th>
                                <th>Subcategoria</th>
                                <th>Valor</th>
                            </tr>
                        </thead>
                        <tbody>
                            {extraordinarias.transacoes.map(t => (
                                <tr key={t.id}>
                                    <td>{t.data}</td>
                                    <td>{t.descricao}</td>
                                    <td>{t.categoria_nome} / {t.subcategoria_nome}</td>
                                    <td className={classeValor(t.valor)}>{formatarEuros(t.valor)}</td>
                                </tr>
                            ))}
                            <tr className="linha-ano linha-grupo">
                                <td>Total</td>
                                <td />
                                <td />
                                <td className={classeValor(extraordinarias.total)}>{formatarEuros(extraordinarias.total)}</td>
                            </tr>
                        </tbody>
                    </table>
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
                            <th>Mês típico</th>
                        </tr>
                    </thead>
                    <tbody>
                        {GRUPOS_CATEGORIA.map(grupo => {
                            const categorias = porCategoria
                                .filter(c => c.tipo === grupo.tipo)
                                .sort((a, b) => Math.abs(b.media) - Math.abs(a.media));
                            if (categorias.length === 0) return null;
                            // Os mesmos meses das categorias: a linha das despesas
                            // bate certo com o cartão «Mês típico» na última coluna
                            // (sem o mês em curso, como as categorias)
                            const completos = dadosGraficoFiltrados.filter(m => !m.emCurso);
                            const totais = completos.map(m => m[grupo.campo]);
                            const media = calcularMedia(totais);
                            const mediana = calcularMediana(totais);
                            const tipico = calcularMedia(completos.map(m => m[grupo.campoTipico]));
                            return (
                                <Fragment key={grupo.tipo}>
                                    <tr className="linha-ano linha-grupo">
                                        <td>{grupo.titulo}</td>
                                        <td className={classeValor(media)}>{formatarEuros(media)}</td>
                                        <td className={classeValor(mediana)}>{formatarEuros(mediana)}</td>
                                        <td className={classeValor(tipico)}>{formatarEuros(tipico)}</td>
                                    </tr>
                                    {categorias.map(c => {
                                        const expandida = categoriaExpandida === c.categoria_id;
                                        return (
                                            <Fragment key={c.categoria_id}>
                                                <tr
                                                    className={`linha-mes ${expandida ? 'linha-mes-activa' : ''}`}
                                                    onClick={() => setCategoriaExpandida(expandida ? null : c.categoria_id)}
                                                >
                                                    <td>
                                                        <span className="seta-expansao">{expandida ? '▼' : '▶'}</span>
                                                        {c.categoria_nome}
                                                    </td>
                                                    <td className={classeValor(c.media)}>{formatarEuros(c.media)}</td>
                                                    <td className={classeValor(c.mediana)}>{formatarEuros(c.mediana)}</td>
                                                    <td className={classeValor(c.mes_tipico)}>{formatarEuros(c.mes_tipico)}</td>
                                                </tr>
                                                {expandida &&
                                                    [...c.subcategorias]
                                                        .sort((a, b) => Math.abs(b.media) - Math.abs(a.media))
                                                        .map(sub => (
                                                            <tr key={sub.subcategoria_nome} className="linha-subcategoria-detalhe">
                                                                <td className="celula-subcategoria-nome">{sub.subcategoria_nome}</td>
                                                                <td className={classeValor(sub.media)}>{formatarEuros(sub.media)}</td>
                                                                <td className={classeValor(sub.mediana)}>{formatarEuros(sub.mediana)}</td>
                                                                <td className={classeValor(sub.mes_tipico)}>{formatarEuros(sub.mes_tipico)}</td>
                                                            </tr>
                                                        ))
                                                }
                                            </Fragment>
                                        );
                                    })}
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </section>
        </div>
    );
}
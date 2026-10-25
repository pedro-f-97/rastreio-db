import { useState, useEffect, useMemo, Fragment } from 'react';
import { obterResumoMensal, obterPorCategoria, obterPorSubcategoria, obterExtraordinarias } from '../api/estatisticas';
import {
    ComposedChart, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    Line, Area, CartesianGrid, Cell, LabelList, ReferenceLine
} from 'recharts';
import './Estatisticas.css';
import '../componentes.css';
import {
    classeValor, formatarEuros, formatarEurosEixo, formatarPercentagem, labelMes, NOMES_CLASSE_DESPESA
} from '../utils/formatacao';
import CabecalhoPagina from '../components/CabecalhoPagina';
import SeletorAno from '../components/SeletorAno';
import Montante from '../components/Montante';
import Icone from '../components/Icone';
import { TooltipGrafico, TickMes } from '../components/Graficos';
import { EIXO, GRELHA, PALETA } from '../utils/graficos';

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

// O limite da escala arredondado para cima a 1, 2, 2,5 ou 5 vezes uma potência de
// 10, para os traços do eixo caírem em números redondos
function limiteRedondo(valor) {
    if (valor <= 0) return 1;
    const potencia = 10 ** Math.floor(Math.log10(valor));
    const passo = [1, 2, 2.5, 5, 10].find(m => valor <= m * potencia);
    return passo * potencia;
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
function CartaoMetades({ titulo, metades, percentagem = false, cor }) {
    return (
        <div className="cartao" style={{ '--cartao-cor': cor }}>
            <span className="cartao-titulo">{titulo}</span>
            <div className="cartao-corpo">
                {metades.map(([label, valor]) => (
                    <div className="cartao-metade" key={label}>
                        <span className="cartao-metade-label">{label}</span>
                        {percentagem ? (
                            <span className={`cartao-metade-valor montante ${valor !== null ? classeValor(valor, 1) : ''}`}>
                                {valor === null ? '—' : (
                                    <>
                                        {formatarPercentagem(valor).slice(0, -1)}
                                        <span className="montante-moeda">%</span>
                                    </>
                                )}
                            </span>
                        ) : (
                            <Montante valor={valor} cor className="cartao-metade-valor" />
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}

// Barras horizontais da distribuição da despesa, para as categorias e para as
// subcategorias da categoria escolhida. Cada barra tem a sua cor, ou a `cor`
// de todas quando vem dada (as subcategorias herdam a da categoria)
function GraficoDistribuicao({ dados, chaveSeleccionada = null, onSeleccionar, cor = null }) {
    return (
        <ResponsiveContainer width="100%" height={dados.length * 34 + 30}>
            <BarChart data={dados} layout="vertical" margin={{ top: 0, right: 170, left: 8, bottom: 0 }} barCategoryGap={7}>
                <CartesianGrid {...GRELHA} vertical horizontal={false} />
                <XAxis type="number" {...EIXO} tickFormatter={formatarEurosEixo} />
                <YAxis type="category" dataKey="nome" {...EIXO} tick={{ ...EIXO.tick, fill: 'var(--text-primary)', fontFamily: 'var(--font-sans)', fontSize: 12 }} width={150} />
                <Tooltip
                    content={<TooltipGrafico formatar={(_v, item) => item.payload.rotulo} />}
                    cursor={{ fill: 'var(--accent-suave)' }}
                />
                <Bar
                    dataKey="valor"
                    name="Despesa"
                    radius={[0, 4, 4, 0]}
                    onClick={onSeleccionar ? item => onSeleccionar(item.payload) : undefined}
                    style={onSeleccionar ? { cursor: 'pointer' } : undefined}
                >
                    {dados.map((d, i) => (
                        <Cell
                            key={d.chave}
                            fill={cor ?? d.cor ?? PALETA[i % PALETA.length]}
                            fillOpacity={chaveSeleccionada === null || chaveSeleccionada === d.chave ? 0.9 : 0.25}
                        />
                    ))}
                    <LabelList dataKey="rotulo" position="right" fill="var(--text-secondary)" fontSize={11} fontFamily="var(--font-mono)" />
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    );
}

// As séries do gráfico da evolução mensal: três barras e a poupança em linha
const SERIES_EVOLUCAO = [
    { chave: 'Receitas', cor: 'var(--type-receita-text)' },
    { chave: 'Despesas', cor: 'var(--type-despesa-text)' },
    { chave: 'Investimento', cor: 'var(--type-investimento-text)' },
    { chave: 'Poupança', cor: 'var(--accent)', linha: true },
];

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
        <div className="painel painel-corpo composicao">
            <div className="composicao-cabecalho">
                <span className="cartao-titulo">Composição do mês típico</span>
                <span className="composicao-total">{formatarEuros(-total)}</span>
            </div>
            <div className="composicao-barra composicao-barra-grossa">
                {partes.filter(p => p.valor > 0).map(p => (
                    <div key={p.campo} style={{ width: `${(p.valor / total) * 100}%`, background: p.cor }} title={p.nome} />
                ))}
            </div>
            <div className="composicao-legenda">
                {partes.map(p => (
                    <div key={p.campo} className="composicao-parte">
                        <span className="composicao-nome">
                            <span className="legenda-cor" style={{ background: p.cor }} />
                            {p.nome}
                        </span>
                        <span className="composicao-valor">{formatarEuros(-p.valor)}</span>
                        <span className="composicao-percentagem">{formatarPercentagem((p.valor / total) * 100, 0)}</span>
                    </div>
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
            .sort((a, b) => b.valor - a.valor)
            // A cor fica presa à categoria, para as subcategorias a herdarem
            .map((c, i) => ({ ...c, cor: PALETA[i % PALETA.length] }));
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

        const limite = limiteRedondo(maxNormal * 1.15);
        const dominio = (!incluirOutliers && extremos > 0)
            ? [-limite, limite]
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

    if (erro) return <p className="erro carregando">{erro}</p>;
    if (!resumo) return <p className="carregando">A carregar...</p>;

    const anosDisponiveis = [...new Set(resumo.meses.map(m => m.ano))].sort();

    // As colunas da tabela «Por categoria»: o nome e três valores
    const celulasValor = (media, mediana, tipico) => (
        <>
            <td className={`col-num ${classeValor(media)}`}>{formatarEuros(media)}</td>
            <td className={`col-num ${classeValor(mediana)}`}>{formatarEuros(mediana)}</td>
            <td className={`col-num ${classeValor(tipico)}`}>{formatarEuros(tipico)}</td>
        </>
    );

    return (
        <div className="pagina-container estatisticas-page">
            <CabecalhoPagina
                secao="03 · Análise"
                titulo="Estatísticas"
                descricao="Médias, taxas e para onde vai o dinheiro. As médias contam só os meses completos."
            >
                <SeletorAno
                    anos={anosDisponiveis}
                    valor={anoSeleccionado}
                    onChange={ano => {
                        setAnoSeleccionado(ano);
                        setCategoriaExpandida(null);
                        setCategoriaDistribuicao(null);
                    }}
                />
            </CabecalhoPagina>

            {/* RESUMO GLOBAL */}
            <section className="secao">
                <h2 className="titulo-secao"><span className="titulo-secao-numero">01</span>Resumo global</h2>
                <div className="cartoes">
                    <CartaoMetades
                        titulo="Mês típico (sem extraordinárias)"
                        cor="var(--type-despesa-text)"
                        metades={[
                            ['Despesa média', cardTipico.media],
                            ['Extraordinárias no período', cardTipico.extraordinarias],
                        ]}
                    />
                    <CartaoMetades
                        titulo="Poupança mensal"
                        cor="var(--type-receita-text)"
                        metades={[
                            ['Média', cardPoupanca.media],
                            ['Sem extraordinárias', cardPoupanca.semExtraordinarias],
                        ]}
                    />
                    <CartaoMetades
                        titulo="Taxa de poupança"
                        cor="var(--accent)"
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
                <div className="secao-cabecalho">
                    <h2 className="titulo-secao"><span className="titulo-secao-numero">02</span>Evolução mensal</h2>
                    <div className="legenda">
                        {SERIES_EVOLUCAO.map(s => (
                            <span key={s.chave} className="legenda-item">
                                <span className={`legenda-cor ${s.linha ? 'linha' : ''}`} style={{ background: s.cor }} />{s.chave}
                            </span>
                        ))}
                    </div>
                </div>

                {totalExtremos > 0 && (
                    <div className="aviso">
                        <Icone nome="aviso" />
                        <span className="aviso-texto">
                            {incluirOutliers
                                ? `Escala a incluir ${totalExtremos === 1 ? '1 valor extremo' : `${totalExtremos} valores extremos`}`
                                : `Escala ajustada para ignorar ${totalExtremos === 1 ? '1 valor extremo' : `${totalExtremos} valores extremos`}`}
                        </span>
                        <button className="btn-ghost" onClick={() => setIncluirOutliers(!incluirOutliers)}>
                            {incluirOutliers ? 'Ignorar valores extremos' : 'Incluir valores extremos na escala'}
                        </button>
                    </div>
                )}

                <div className="grafico-moldura">
                    <ResponsiveContainer width="100%" height={380}>
                        <ComposedChart data={dadosGraficoFiltrados} margin={{ top: 10, right: 16, left: 8, bottom: 10 }} barGap={2} barCategoryGap="22%">
                            <CartesianGrid {...GRELHA} />
                            <XAxis dataKey="label" {...EIXO} tick={<TickMes />} interval={0} height={40} />
                            <YAxis
                                {...EIXO}
                                tickFormatter={formatarEurosEixo}
                                domain={dominioValores}
                                allowDataOverflow={true}
                                width={84}
                            />
                            <Tooltip content={<TooltipGrafico />} cursor={{ fill: 'var(--accent-suave)' }} />
                            <ReferenceLine y={0} stroke="var(--text-secondary)" strokeOpacity={0.5} />
                            {SERIES_EVOLUCAO.filter(s => !s.linha).map(s => (
                                <Bar key={s.chave} dataKey={s.chave} fill={s.cor} radius={2} maxBarSize={18} />
                            ))}
                            <Line
                                dataKey="Poupança"
                                type="monotone"
                                stroke="var(--accent)"
                                strokeWidth={2}
                                dot={{ r: 2.5, fill: 'var(--accent)', strokeWidth: 0 }}
                                activeDot={{ r: 4 }}
                            />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </section>

            {/* GRÁFICO TAXA DE POUPANÇA */}
            <section className="secao">
                <div className="secao-cabecalho">
                    <h2 className="titulo-secao"><span className="titulo-secao-numero">03</span>Taxa de poupança</h2>
                    <div className="legenda">
                        <span className="legenda-item"><span className="legenda-cor" style={{ background: 'var(--accent)' }} />Média de 3 meses</span>
                        <span className="legenda-item"><span className="legenda-cor linha" style={{ background: 'var(--chart-2)' }} />Média de 12 meses</span>
                        {cardTaxa.periodo !== null && (
                            <span className="legenda-item"><span className="legenda-cor linha tracejada" />Período</span>
                        )}
                    </div>
                </div>
                <div className="grafico-moldura">
                    <ResponsiveContainer width="100%" height={280}>
                        <ComposedChart data={dadosGraficoFiltrados} margin={{ top: 10, right: 110, left: 8, bottom: 10 }}>
                            <defs>
                                <linearGradient id="grad-taxa" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                                    <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid {...GRELHA} />
                            <XAxis dataKey="label" {...EIXO} tick={<TickMes />} interval={0} height={40} />
                            <YAxis {...EIXO} tickFormatter={v => `${v}%`} width={56} />
                            <Tooltip
                                content={<TooltipGrafico formatar={v => formatarPercentagem(v)} />}
                                cursor={{ stroke: 'var(--accent-linha)', strokeDasharray: '3 3' }}
                            />
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
                                        fontFamily: 'var(--font-mono)',
                                    }}
                                />
                            )}
                            <Area
                                dataKey="Média de 3 meses"
                                type="monotone"
                                stroke="var(--accent)"
                                strokeWidth={2}
                                fill="url(#grad-taxa)"
                                dot={false}
                                activeDot={{ r: 4 }}
                                connectNulls={false}
                            />
                            <Line dataKey="Média de 12 meses" type="monotone" stroke="var(--chart-2)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} connectNulls={false} />
                        </ComposedChart>
                    </ResponsiveContainer>
                </div>
            </section>

            {/* POR CATEGORIA */}
            <section className="secao">
                <h2 className="titulo-secao"><span className="titulo-secao-numero">04</span>Por categoria</h2>
                <div className="tabela-wrapper">
                    <table className="tabela-base tabela-stats">
                        <thead>
                            <tr>
                                <th>Categoria</th>
                                <th className="col-num">Média mensal</th>
                                <th className="col-num">Mediana mensal</th>
                                <th className="col-num">Mês típico</th>
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
                                        <tr className="linha-grupo">
                                            <td>
                                                <span className={`badge-tipo badge-tipo-${grupo.tipo}`}>{grupo.titulo}</span>
                                            </td>
                                            {celulasValor(media, mediana, tipico)}
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
                                                            <span className={`seta-expansao ${expandida ? 'aberta' : ''}`}><Icone nome="direita" tamanho={13} /></span>
                                                            {c.categoria_nome}
                                                        </td>
                                                        {celulasValor(c.media, c.mediana, c.mes_tipico)}
                                                    </tr>
                                                    {expandida &&
                                                        [...c.subcategorias]
                                                            .sort((a, b) => Math.abs(b.media) - Math.abs(a.media))
                                                            .map(sub => (
                                                                <tr key={sub.subcategoria_nome} className="linha-subcategoria-detalhe">
                                                                    <td className="celula-subcategoria-nome">{sub.subcategoria_nome}</td>
                                                                    {celulasValor(sub.media, sub.mediana, sub.mes_tipico)}
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
                </div>
            </section>

            {/* DESPESAS EXTRAORDINÁRIAS */}
            <section className="secao">
                <h2 className="titulo-secao"><span className="titulo-secao-numero">05</span>Despesas extraordinárias</h2>
                {extraordinarias === null ? null : extraordinarias.transacoes.length === 0 ? (
                    <p className="estado-vazio">Sem despesas extraordinárias no período.</p>
                ) : (
                    <div className="tabela-wrapper">
                        <table className="tabela-base tabela-stats">
                            <thead>
                                <tr>
                                    <th>Data</th>
                                    <th>Descrição</th>
                                    <th>Subcategoria</th>
                                    <th className="col-num">Valor</th>
                                </tr>
                            </thead>
                            <tbody>
                                {extraordinarias.transacoes.map(t => (
                                    <tr key={t.id}>
                                        <td className="col-data">{t.data}</td>
                                        <td>{t.descricao}</td>
                                        <td className="celula-secundaria">{t.categoria_nome} / {t.subcategoria_nome}</td>
                                        <td className={`col-num ${classeValor(t.valor)}`}>{formatarEuros(t.valor)}</td>
                                    </tr>
                                ))}
                                <tr className="linha-total">
                                    <td colSpan={3}>Total</td>
                                    <td className={`col-num ${classeValor(extraordinarias.total)}`}>{formatarEuros(extraordinarias.total)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            {/* DISTRIBUIÇÃO DA DESPESA */}
            <section className="secao">
                <div className="secao-cabecalho">
                    <h2 className="titulo-secao">
                        <span className="titulo-secao-numero">06</span>Distribuição da despesa
                        {distribuicao.length > 0 && (
                            <span className="titulo-secao-nota">Clica numa categoria para ver as subcategorias</span>
                        )}
                    </h2>
                </div>
                {distribuicao.length === 0 ? (
                    <p className="estado-vazio">Sem despesas no período.</p>
                ) : (
                    <div className={`distribuicao ${categoriaDistribuicaoDados ? 'com-detalhe' : ''}`}>
                        <div className="grafico-moldura">
                            <GraficoDistribuicao
                                dados={distribuicao}
                                chaveSeleccionada={categoriaDistribuicao}
                                onSeleccionar={c => setCategoriaDistribuicao(categoriaDistribuicao === c.chave ? null : c.chave)}
                            />
                        </div>

                        {categoriaDistribuicaoDados && (
                            <div className="grafico-moldura subcategoria-detalhe" style={{ '--detalhe-cor': categoriaDistribuicaoDados.cor }}>
                                <div className="subcategoria-detalhe-cabecalho">
                                    <h3>{categoriaDistribuicaoDados.nome}</h3>
                                    <button
                                        className="btn-icone"
                                        title="Fechar"
                                        onClick={() => setCategoriaDistribuicao(null)}
                                    >
                                        <Icone nome="fechar" />
                                    </button>
                                </div>
                                <GraficoDistribuicao dados={categoriaDistribuicaoDados.subcategorias} cor={categoriaDistribuicaoDados.cor} />
                            </div>
                        )}
                    </div>
                )}
            </section>
        </div>
    );
}

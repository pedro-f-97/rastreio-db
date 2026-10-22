import { useState, useEffect, Fragment } from 'react';
import { obterResumoMensal, obterDetalheMensal } from '../api/estatisticas';
import './Estatisticas.css';
import '../componentes.css';
import { classeValor, formatarEuros, formatarPercentagem, labelMes } from '../utils/formatacao';

export default function Historico() {
    const [resumo, setResumo] = useState(null);
    const [erro, setErro] = useState(null);
    const [mesSeleccionado, setMesSeleccionado] = useState(null);
    const [detalheMes, setDetalheMes] = useState([]);

    useEffect(() => {
        obterResumoMensal()
            .then(res => setResumo(res.data))
            .catch(() => setErro('Não foi possível carregar o histórico.'));
    }, []);

    if (erro) return <p className="erro">{erro}</p>;
    if (!resumo) return <p className="carregando">A carregar...</p>;

    const mesesPorAno = resumo.meses.reduce((acc, m) => {
        if (!acc[m.ano]) acc[m.ano] = [];
        acc[m.ano].push(m);
        return acc;
    }, {});

    const totaisPorAno = Object.entries(mesesPorAno).map(([ano, meses]) => {
        const receitas = meses.reduce((s, m) => s + m.receitas, 0);
        const despesas = meses.reduce((s, m) => s + m.despesas, 0);
        const investimento = meses.reduce((s, m) => s + m.investimento, 0);
        const poupanca = receitas + despesas;
        const taxa = receitas > 0 ? poupanca / receitas * 100 : null;
        return { ano: parseInt(ano), receitas, despesas, investimento, poupanca, taxa };
    });

    function toggleMes(ano, mes) {
        if (mesSeleccionado?.ano === ano && mesSeleccionado?.mes === mes) {
            setMesSeleccionado(null);
            setDetalheMes([]);
        } else {
            setMesSeleccionado({ ano, mes });
            obterDetalheMensal(ano, mes).then(res => setDetalheMes(res.data));
        }
    }

    return (
        <div className="estatisticas-page">
            <h1>Histórico</h1>

            <section className="secao">
                <table className="tabela-base tabela-stats">
                    <thead>
                        <tr>
                            <th>Mês</th>
                            <th>Receitas</th>
                            <th>Despesas</th>
                            <th>Investimento</th>
                            <th>Poupança</th>
                            <th>Taxa</th>
                        </tr>
                    </thead>
                    <tbody>
                        {Object.keys(mesesPorAno).sort().reverse().map(ano => {
                            const totalAno = totaisPorAno.find(t => t.ano === parseInt(ano));
                            return (
                                <Fragment key={`ano-${ano}`}>
                                    <tr className="linha-ano">
                                        <td>{ano}</td>
                                        <td className={classeValor(totalAno.receitas)}>{formatarEuros(totalAno.receitas)}</td>
                                        <td className={classeValor(totalAno.despesas)}>{formatarEuros(totalAno.despesas)}</td>
                                        <td className={classeValor(totalAno.investimento)}>{formatarEuros(totalAno.investimento)}</td>
                                        <td className={classeValor(totalAno.poupanca)}>{formatarEuros(totalAno.poupanca)}</td>
                                        <td className={totalAno.taxa === null ? '' : classeValor(totalAno.taxa, 1)}>{formatarPercentagem(totalAno.taxa)}</td>
                                    </tr>
                                    {mesesPorAno[ano].map(m => {
                                        const seleccionado = mesSeleccionado?.ano === m.ano && mesSeleccionado?.mes === m.mes;
                                        return (
                                            <Fragment key={`${m.ano}-${m.mes}`}>
                                                <tr
                                                    onClick={() => toggleMes(m.ano, m.mes)}
                                                    className={`linha-mes ${seleccionado ? 'linha-mes-activa' : ''}`}
                                                >
                                                    <td>
                                                        <span className="seta-expansao">{seleccionado ? '▼' : '▶'}</span>
                                                        {labelMes(m.ano, m.mes)}
                                                    </td>
                                                    <td className={classeValor(m.receitas)}>{formatarEuros(m.receitas)}</td>
                                                    <td className={classeValor(m.despesas)}>{formatarEuros(m.despesas)}</td>
                                                    <td className={classeValor(m.investimento)}>{formatarEuros(m.investimento)}</td>
                                                    <td className={classeValor(m.poupanca)}>{formatarEuros(m.poupanca)}</td>
                                                    <td className={m.receitas <= 0 ? '' : classeValor(m.poupanca / m.receitas * 100, 1)}>{m.receitas > 0 ? formatarPercentagem(m.poupanca / m.receitas * 100) : '—'}</td>
                                                </tr>
                                                {seleccionado && detalheMes.map(cat => (
                                                    <Fragment key={`cat-${cat.categoria_id}`}>
                                                        <tr className="linha-categoria-detalhe">
                                                            <td className="celula-categoria-nome">↳ {cat.categoria_nome}</td>
                                                            <td className={cat.tipo === 'receita' ? classeValor(cat.total) : ''}>{cat.tipo === 'receita' ? formatarEuros(cat.total) : ''}</td>
                                                            <td className={cat.tipo === 'despesa' ? classeValor(cat.total) : ''}>{cat.tipo === 'despesa' ? formatarEuros(cat.total) : ''}</td>
                                                            <td className={cat.tipo === 'investimento' ? classeValor(cat.total) : ''}>{cat.tipo === 'investimento' ? formatarEuros(cat.total) : ''}</td>
                                                            <td></td>
                                                            <td></td>
                                                        </tr>
                                                        {cat.subcategorias.map(sub => (
                                                            <tr key={`sub-${sub.subcategoria_nome}`} className="linha-subcategoria-detalhe">
                                                                <td className="celula-subcategoria-nome">{sub.subcategoria_nome}</td>
                                                                <td className={cat.tipo === 'receita' ? classeValor(sub.total) : ''}>{cat.tipo === 'receita' ? formatarEuros(sub.total) : ''}</td>
                                                                <td className={cat.tipo === 'despesa' ? classeValor(sub.total) : ''}>{cat.tipo === 'despesa' ? formatarEuros(sub.total) : ''}</td>
                                                                <td className={cat.tipo === 'investimento' ? classeValor(sub.total) : ''}>{cat.tipo === 'investimento' ? formatarEuros(sub.total) : ''}</td>
                                                                <td></td>
                                                                <td></td>
                                                            </tr>
                                                        ))}
                                                    </Fragment>
                                                ))}
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

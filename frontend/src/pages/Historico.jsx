import { useState, useEffect, Fragment } from 'react';
import { obterResumoMensal, obterDetalheMensal } from '../api/estatisticas';
import './Estatisticas.css';
import '../componentes.css';
import { classeValor, classeValorInvestimento, formatarEuros, formatarPercentagem, labelMes } from '../utils/formatacao';
import CabecalhoPagina from '../components/CabecalhoPagina';
import Icone from '../components/Icone';

// A taxa de poupança de um mês ou de um ano, com uma barra pequena: cheia aos
// 100%, para a esquerda quando é negativa
function CelulaTaxa({ taxa }) {
    if (taxa === null) return <td className="col-num celula-taxa">—</td>;
    const largura = Math.min(Math.abs(taxa), 100);
    return (
        <td className={`col-num celula-taxa ${classeValor(taxa, 1)}`}>
            <span className={`barra-taxa ${taxa < 0 ? 'negativa' : ''}`}><span style={{ width: `${largura}%` }} /></span>
            {formatarPercentagem(taxa)}
        </td>
    );
}

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

    if (erro) return <p className="erro carregando">{erro}</p>;
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
        <div className="pagina-container estatisticas-page">
            <CabecalhoPagina
                secao="01 · Transações"
                titulo="Histórico"
                descricao="Os totais de cada mês e de cada ano. Clica num mês para o ver por categoria."
            />

            <section className="secao">
                <div className="tabela-wrapper">
                    <table className="tabela-base tabela-stats tabela-historico">
                        <thead>
                            <tr>
                                <th>Mês</th>
                                <th className="col-num">Receitas</th>
                                <th className="col-num">Despesas</th>
                                <th className="col-num">Investimento</th>
                                <th className="col-num">Poupança</th>
                                <th className="col-num">Taxa</th>
                            </tr>
                        </thead>
                        <tbody>
                            {Object.keys(mesesPorAno).sort().reverse().map(ano => {
                                const totalAno = totaisPorAno.find(t => t.ano === parseInt(ano));
                                return (
                                    <Fragment key={`ano-${ano}`}>
                                        <tr className="linha-ano">
                                            <td>{ano}</td>
                                            <td className={`col-num ${classeValor(totalAno.receitas)}`}>{formatarEuros(totalAno.receitas)}</td>
                                            <td className={`col-num ${classeValor(totalAno.despesas)}`}>{formatarEuros(totalAno.despesas)}</td>
                                            <td className={`col-num ${classeValorInvestimento(totalAno.investimento)}`}>{formatarEuros(totalAno.investimento)}</td>
                                            <td className={`col-num ${classeValor(totalAno.poupanca)}`}>{formatarEuros(totalAno.poupanca)}</td>
                                            <CelulaTaxa taxa={totalAno.taxa} />
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
                                                            <span className={`seta-expansao ${seleccionado ? 'aberta' : ''}`}><Icone nome="direita" tamanho={13} /></span>
                                                            {labelMes(m.ano, m.mes)}
                                                            {m.em_curso && <span className="chip chip-accent chip-em-curso">em curso</span>}
                                                        </td>
                                                        <td className={`col-num ${classeValor(m.receitas)}`}>{formatarEuros(m.receitas)}</td>
                                                        <td className={`col-num ${classeValor(m.despesas)}`}>{formatarEuros(m.despesas)}</td>
                                                        <td className={`col-num ${classeValorInvestimento(m.investimento)}`}>{formatarEuros(m.investimento)}</td>
                                                        <td className={`col-num ${classeValor(m.poupanca)}`}>{formatarEuros(m.poupanca)}</td>
                                                        <CelulaTaxa taxa={m.receitas > 0 ? m.poupanca / m.receitas * 100 : null} />
                                                    </tr>
                                                    {seleccionado && detalheMes.map(cat => (
                                                        <Fragment key={`cat-${cat.categoria_id}`}>
                                                            <tr className="linha-categoria-detalhe">
                                                                <td className="celula-categoria-nome">{cat.categoria_nome}</td>
                                                                <td className={`col-num ${cat.tipo === 'receita' ? classeValor(cat.total) : ''}`}>{cat.tipo === 'receita' ? formatarEuros(cat.total) : ''}</td>
                                                                <td className={`col-num ${cat.tipo === 'despesa' ? classeValor(cat.total) : ''}`}>{cat.tipo === 'despesa' ? formatarEuros(cat.total) : ''}</td>
                                                                <td className={`col-num ${cat.tipo === 'investimento' ? classeValorInvestimento(cat.total) : ''}`}>{cat.tipo === 'investimento' ? formatarEuros(cat.total) : ''}</td>
                                                                <td></td>
                                                                <td></td>
                                                            </tr>
                                                            {cat.subcategorias.map(sub => (
                                                                <tr key={`sub-${sub.subcategoria_nome}`} className="linha-subcategoria-detalhe">
                                                                    <td className="celula-subcategoria-nome">{sub.subcategoria_nome}</td>
                                                                    <td className={`col-num ${cat.tipo === 'receita' ? classeValor(sub.total) : ''}`}>{cat.tipo === 'receita' ? formatarEuros(sub.total) : ''}</td>
                                                                    <td className={`col-num ${cat.tipo === 'despesa' ? classeValor(sub.total) : ''}`}>{cat.tipo === 'despesa' ? formatarEuros(sub.total) : ''}</td>
                                                                    <td className={`col-num ${cat.tipo === 'investimento' ? classeValorInvestimento(sub.total) : ''}`}>{cat.tipo === 'investimento' ? formatarEuros(sub.total) : ''}</td>
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
                </div>
            </section>
        </div>
    );
}

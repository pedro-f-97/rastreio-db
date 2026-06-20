import { useState, useEffect, Fragment } from 'react';
import { obterResumoMensal, obterDetalheMensal } from '../api/estatisticas';
import './Estatisticas.css';

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

function labelMes(ano, mes) {
    return `${MESES[mes - 1]} ${ano}`;
}

export default function Historico() {
    const [resumo, setResumo] = useState(null);
    const [mesSeleccionado, setMesSeleccionado] = useState(null);
    const [detalheMes, setDetalheMes] = useState([]);

    useEffect(() => {
        obterResumoMensal().then(res => setResumo(res.data));
    }, []);

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
        const taxa = receitas > 0 ? parseFloat((poupanca / receitas * 100).toFixed(1)) : 0;
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
                <table className="tabela-stats">
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
                                        <td className="valor-positivo">{totalAno.receitas.toFixed(2)} €</td>
                                        <td className="valor-negativo">{totalAno.despesas.toFixed(2)} €</td>
                                        <td className={totalAno.investimento <= 0 ? 'valor-negativo' : 'valor-positivo'}>{totalAno.investimento.toFixed(2)} €</td>
                                        <td className={totalAno.poupanca >= 0 ? 'valor-positivo' : 'valor-negativo'}>{totalAno.poupanca.toFixed(2)} €</td>
                                        <td>{totalAno.taxa}%</td>
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
                                                    <td className="valor-positivo">{m.receitas.toFixed(2)} €</td>
                                                    <td className="valor-negativo">{m.despesas.toFixed(2)} €</td>
                                                    <td className={m.investimento <= 0 ? 'valor-negativo' : 'valor-positivo'}>{m.investimento.toFixed(2)} €</td>
                                                    <td className={m.poupanca >= 0 ? 'valor-positivo' : 'valor-negativo'}>{m.poupanca.toFixed(2)} €</td>
                                                    <td>{m.receitas > 0 ? (m.poupanca / m.receitas * 100).toFixed(1) : '—'}%</td>
                                                </tr>
                                                {seleccionado && detalheMes.map(cat => (
                                                    <Fragment key={`cat-${cat.categoria_id}`}>
                                                        <tr className="linha-categoria-detalhe">
                                                            <td className="celula-categoria-nome">↳ {cat.categoria_nome}</td>
                                                            <td className={cat.tipo === 'receita' ? 'valor-positivo' : ''}>{cat.tipo === 'receita' ? `${cat.total.toFixed(2)} €` : ''}</td>
                                                            <td className={cat.tipo === 'despesa' ? 'valor-negativo' : ''}>{cat.tipo === 'despesa' ? `${cat.total.toFixed(2)} €` : ''}</td>
                                                            <td className={cat.tipo === 'investimento' ? (cat.total >= 0 ? 'valor-positivo' : 'valor-negativo') : ''}>{cat.tipo === 'investimento' ? `${cat.total.toFixed(2)} €` : ''}</td>
                                                            <td></td>
                                                            <td></td>
                                                        </tr>
                                                        {cat.subcategorias.map(sub => (
                                                            <tr key={`sub-${sub.subcategoria_nome}`} className="linha-subcategoria-detalhe">
                                                                <td className="celula-subcategoria-nome">{sub.subcategoria_nome}</td>
                                                                <td className={cat.tipo === 'receita' ? 'valor-positivo' : ''}>{cat.tipo === 'receita' ? `${sub.total.toFixed(2)} €` : ''}</td>
                                                                <td className={cat.tipo === 'despesa' ? 'valor-negativo' : ''}>{cat.tipo === 'despesa' ? `${sub.total.toFixed(2)} €` : ''}</td>
                                                                <td className={cat.tipo === 'investimento' ? (sub.total >= 0 ? 'valor-positivo' : 'valor-negativo') : ''}>{cat.tipo === 'investimento' ? `${sub.total.toFixed(2)} €` : ''}</td>
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

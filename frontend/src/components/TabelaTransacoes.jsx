import { useState, useEffect } from 'react';

export default function TabelaTransacoes({ transacoes, categorias, onGuardar, listarSubcategorias }) {
    const [subcategorias, setSubcategorias] = useState({});
    const [notasEditando, setNotasEditando] = useState({});

    // Carrega subcategorias para cada categoria única presente nas transações
    useEffect(() => {
        const categoriasUnicas = [...new Set(
            transacoes.map(t => t.categoria_id).filter(Boolean)
        )];

        categoriasUnicas.forEach(async (catId) => {
            if (!subcategorias[catId]) {
                const res = await listarSubcategorias(catId);
                setSubcategorias(prev => ({ ...prev, [catId]: res.data }));
            }
        });
    }, [transacoes]);

    async function aoMudarCategoria(t, novaCatId) {
        const id = novaCatId ? Number(novaCatId) : null;
        // Ao mudar categoria, limpa subcategoria
        await onGuardar(t.id, 'categoria_id', id);
        await onGuardar(t.id, 'subcategoria_id', null);

        if (id && !subcategorias[id]) {
            const res = await listarSubcategorias(id);
            setSubcategorias(prev => ({ ...prev, [id]: res.data }));
        }
    }

    function aoEditarNotas(id, valor) {
        setNotasEditando(prev => ({ ...prev, [id]: valor }));
    }

    function aoGuardarNotas(t) {
        const novas = notasEditando[t.id];
        if (novas !== undefined && novas !== t.notas) {
            onGuardar(t.id, 'notas', novas);
        }
    }

    return (
        <div className="tabela-wrapper">
            <table className="tabela-transacoes">
                <thead>
                    <tr>
                        <th>Data</th>
                        <th>Descrição</th>
                        <th>Valor</th>
                        <th>Saldo</th>
                        <th>Categoria</th>
                        <th>Subcategoria</th>
                        <th>Reembolso</th>
                        <th>Notas</th>
                    </tr>
                </thead>
                <tbody>
                    {transacoes.map(t => (
                        <tr key={t.id} className={t.valor < 0 ? 'despesa' : 'receita'}>
                            <td>{t.data}</td>
                            <td>{t.descricao}</td>
                            <td className="valor">{t.valor.toFixed(2)} €</td>
                            <td className="valor">{t.saldo?.toFixed(2)} €</td>

                            <td>
                                <select
                                    value={t.categoria_id ?? ''}
                                    onChange={e => aoMudarCategoria(t, e.target.value || null)}
                                >
                                    <option value="">—</option>
                                    {categorias.map(c => (
                                        <option key={c.id} value={c.id}>{c.nome}</option>
                                    ))}
                                </select>
                            </td>

                            <td>
                                <select
                                    value={t.subcategoria_id ?? ''}
                                    onChange={e => onGuardar(t.id, 'subcategoria_id', e.target.value ? Number(e.target.value) : null)}
                                    disabled={!t.categoria_id}
                                >
                                    <option value="">—</option>
                                    {(subcategorias[t.categoria_id] ?? []).map(s => (
                                        <option key={s.id} value={s.id}>{s.nome}</option>
                                    ))}
                                </select>
                            </td>

                            <td>
                                <input
                                    type="checkbox"
                                    checked={t.reembolso}
                                    onChange={e => onGuardar(t.id, 'reembolso', e.target.checked)}
                                />
                            </td>

                            <td>
                                <input
                                    type="text"
                                    value={notasEditando[t.id] ?? t.notas ?? ''}
                                    onChange={e => aoEditarNotas(t.id, e.target.value)}
                                    onBlur={() => aoGuardarNotas(t)}
                                    placeholder="—"
                                />
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
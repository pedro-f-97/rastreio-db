import { useState, useEffect } from 'react';

export default function TabelaTransacoes({ transacoes, categorias, regras, onGuardar, onCriarRegra, listarSubcategorias }) {
    const [subcategorias, setSubcategorias] = useState({});
    const [notasEditando, setNotasEditando] = useState({});
    const [modalRegra, setModalRegra] = useState(null);
// { transacaoId, descricao, categoria_id, subcategoria_id, palavraChave }

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
        await onGuardar(t.id, 'categoria_id', id);
        await onGuardar(t.id, 'subcategoria_id', null);

        if (id && !subcategorias[id]) {
            const res = await listarSubcategorias(id);
            setSubcategorias(prev => ({ ...prev, [id]: res.data }));
        }

        verificarRegra(t, id, null);
    }

    async function aoMudarSubcategoria(t, novaSubId) {
        console.log('aoMudarSubcategoria', t.id, novaSubId);
        const id = novaSubId ? Number(novaSubId) : null;
        await onGuardar(t.id, 'subcategoria_id', id);
        verificarRegra(t, t.categoria_id, id);
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

    function verificarRegra(t, categoriaId, subcategoriaId) {
        if (!categoriaId) return;
        if (t.descricao.toUpperCase().startsWith("TRF")) return;

        // Verifica se já existe alguma regra cuja palavra-chave está contida na descrição
        const regraExistente = regras.some(r =>
            t.descricao.toLowerCase().includes(r.palavra_chave.toLowerCase())
        );
        if (regraExistente) return;

        // Sugere como palavra-chave a palavra mais longa da descrição com mais de 3 caracteres
        const palavras = t.descricao.split(/\s+/).filter(p => p.length > 3);
        const sugestao = palavras.reduce((a, b) => a.length >= b.length ? a : b, '');

        setModalRegra({
            transacaoId: t.id,
            descricao: t.descricao,
            categoria_id: categoriaId,
            subcategoria_id: subcategoriaId,
            palavraChave: sugestao,
        });
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
                                    onChange={e => aoMudarSubcategoria(t, e.target.value || null)}
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
        {modalRegra && (
            <div className="modal-overlay">
                <div className="modal">
                    <h3>Criar regra de categorização?</h3>
                    <p className="modal-descricao">{modalRegra.descricao}</p>
                    <input
                        type="text"
                        value={modalRegra.palavraChave}
                        onChange={e => setModalRegra(prev => ({ ...prev, palavraChave: e.target.value }))}
                    />
                    <div className="modal-accoes">
                        <button onClick={() => setModalRegra(null)}>Ignorar</button>
                        <button
                            className="btn-confirmar"
                            onClick={async () => {
                                if (!modalRegra.palavraChave.trim()) return;
                                await onCriarRegra({
                                    palavra_chave: modalRegra.palavraChave.trim(),
                                    categoria_id: modalRegra.categoria_id,
                                    subcategoria_id: modalRegra.subcategoria_id,
                                });
                                setModalRegra(null);
                            }}
                        >
                            Criar regra
                        </button>
                    </div>
                </div>
            </div>
        )}
        
        </div>
    );
}
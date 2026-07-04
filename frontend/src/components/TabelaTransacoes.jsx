import { useState, useEffect } from 'react';
import { formatarEuros } from '../utils/formatacao';

export default function TabelaTransacoes({
    transacoes,
    categorias,
    regras,
    onGuardar,
    onCriarRegra,
    listarSubcategorias
}) {
    const [subcategorias, setSubcategorias] = useState({});
    const [notasEditando, setNotasEditando] = useState({});
    const [modalRegra, setModalRegra] = useState(null);

    // =========================
    // HELPERS
    // =========================
    const normalizar = (s) =>
        (s ?? "")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();

    // =========================
    // EFFECT - SUBCATEGORIAS
    // =========================
    useEffect(() => {
        const categoriasUnicas = [...new Set(
            transacoes.map(t => t.categoria_id).filter(Boolean)
        )];

        async function carregarSubcategorias() {
            const novas = {};

            await Promise.all(
                categoriasUnicas.map(async (catId) => {
                    if (!subcategorias[catId]) {
                        const res = await listarSubcategorias(catId);
                        novas[catId] = res.data;
                    }
                })
            );

            if (Object.keys(novas).length > 0) {
                setSubcategorias(prev => ({ ...prev, ...novas }));
            }
        }

        carregarSubcategorias();
    }, [transacoes, listarSubcategorias]);

    // =========================
    // HANDLERS
    // =========================
    async function aoMudarCategoria(t, novaCatId) {
        const updated = {
            ...t,
            categoria_id: novaCatId,
            subcategoria_id: null
        };

        await onGuardar(t.id, 'categoria_id', novaCatId);
        await onGuardar(t.id, 'subcategoria_id', null);
    }

    async function aoMudarSubcategoria(t, novaSubId) {
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

    // =========================
    // LÓGICA DE REGRAS
    // =========================
    function verificarRegra(t, categoriaId, subcategoriaId) {
        if (!categoriaId) return;
        if (!t?.descricao) return;
        if (t.descricao.toUpperCase().startsWith("TRF")) return;

        const descricao = normalizar(t.descricao);

        const regraExistente = regras.some(r => {
            const chave = normalizar(r.palavra_chave);

            // regra de palavra única
            if (!chave.includes(" ")) {
                return descricao.split(" ").includes(chave);
            }

            // regra de frase
            return descricao.includes(chave);
        });

        if (regraExistente) return;

        const palavras = t.descricao.split(" ").filter(p => p.length > 3);

        if (palavras.length === 0) return;

        const sugestao = palavras.reduce((a, b) =>
            a.length >= b.length ? a : b
        );

        const inicio = t.descricao.indexOf(sugestao);
        const fim = inicio + sugestao.length;

        setModalRegra({
            transacaoId: t.id,
            descricao: t.descricao,
            categoria_id: categoriaId,
            subcategoria_id: subcategoriaId,
            inicio,
            fim,
        });
        console.log('modal', { descricao: t.descricao, sugestao, inicio, fim });
    }

    // =========================
    // RENDER
    // =========================
    return (
        <>
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
                            <th>Conta</th>
                            <th>Notas</th>
                        </tr>
                    </thead>

                    <tbody>
                        {transacoes.map(t => (
                            <tr key={t.id} className={t.valor < 0 ? 'despesa' : 'receita'}>
                                <td>{t.data}</td>
                                <td>{t.descricao}</td>
                                <td className="valor">{formatarEuros(t.valor)}</td>
                                <td className="valor">{formatarEuros(t.saldo)}</td>
                                <td>
                                    <select
                                        value={t.categoria_id ?? ''}
                                        onChange={e => aoMudarCategoria(t, e.target.value || null)}
                                    >
                                        <option value="">—</option>
                                        {categorias.map(c => (
                                            <option key={c.id} value={c.id}>
                                                {c.nome}
                                            </option>
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
                                            <option key={s.id} value={s.id}>
                                                {s.nome}
                                            </option>
                                        ))}
                                    </select>
                                </td>

                                <td>
                                    <input
                                        type="checkbox"
                                        checked={t.reembolso}
                                        onChange={e =>
                                            onGuardar(t.id, 'reembolso', e.target.checked)
                                        }
                                    />
                                </td>

                                <td>{t.conta_nome ?? '—'}</td>

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

            {/* MODAL */}
            {modalRegra && (
                <div className="modal-overlay">
                    <div className="modal">
                        <h3>Criar regra de categorização?</h3>

                        <p className="modal-descricao">
                            <span>
                                {modalRegra.descricao.slice(0, modalRegra.inicio)}
                            </span>
                            <span className="desc-seleccionado">
                                {modalRegra.descricao.slice(
                                    modalRegra.inicio,
                                    modalRegra.fim
                                )}
                            </span>
                            <span>
                                {modalRegra.descricao.slice(modalRegra.fim)}
                            </span>
                        </p>

                        <div className="sliders">
                            <input
                                type="range"
                                min={0}
                                max={modalRegra.fim - 1}
                                value={modalRegra.inicio}
                                onChange={e => {
                                    const inicio = Number(e.target.value);
                                    setModalRegra(prev => ({ ...prev, inicio }));
                                }}
                            />

                            <input
                                type="range"
                                min={modalRegra.inicio + 1}
                                max={modalRegra.descricao.length}
                                value={modalRegra.fim}
                                onChange={e => {
                                    const fim = Number(e.target.value);
                                    setModalRegra(prev => ({ ...prev, fim }));
                                }}
                            />
                        </div>

                        <p>
                            Palavra-chave:{' '}
                            <strong>
                                {modalRegra.descricao
                                    .slice(modalRegra.inicio, modalRegra.fim)
                                    .trim()}
                            </strong>
                        </p>

                        <div className="modal-accoes">
                            <button onClick={() => setModalRegra(null)}>
                                Ignorar
                            </button>

                            <button
                                className="btn-confirmar"
                                onClick={async () => {
                                    const palavraChave = modalRegra.descricao
                                        .slice(modalRegra.inicio, modalRegra.fim)
                                        .trim();

                                    if (!palavraChave) return;

                                    await onCriarRegra({
                                        palavra_chave: palavraChave,
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
        </>
    );
}

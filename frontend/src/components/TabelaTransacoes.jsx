import { useState, useEffect, Fragment } from 'react';
import { formatarEuros } from '../utils/formatacao';
import Icone from './Icone';

const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
    'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
const MESES_CURTOS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

// "2026-10-20" → o dia e o mês curto, para a coluna da data
function DataCurta({ iso }) {
    const [, mes, dia] = iso.split('-');
    return (
        <>
            <span className="data-dia">{dia}</span>
            <span className="data-mes">{MESES_CURTOS[Number(mes) - 1]}</span>
        </>
    );
}

export default function TabelaTransacoes({
    transacoes,
    categorias,
    regras,
    onGuardar,
    onCriarRegra,
    listarSubcategorias,
    onGuardarSaldo,
    onApagar
}) {
    const [subcategorias, setSubcategorias] = useState({});
    const [notasEditando, setNotasEditando] = useState({});
    const [saldosEditando, setSaldosEditando] = useState({});
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
    }, [transacoes, subcategorias, listarSubcategorias]);

    // =========================
    // HANDLERS
    // =========================
    async function aoMudarCategoria(t, novaCatId) {
        await onGuardar(t.id, { categoria_id: novaCatId, subcategoria_id: null });
    }

    async function aoMudarSubcategoria(t, novaSubId) {
        const id = novaSubId ? Number(novaSubId) : null;

        if (await onGuardar(t.id, { subcategoria_id: id })) {
            verificarRegra(t, t.categoria_id, id);
        }
    }

    function aoEditarNotas(id, valor) {
        setNotasEditando(prev => ({ ...prev, [id]: valor }));
    }

    function aoGuardarNotas(t) {
        const novas = notasEditando[t.id];

        if (novas !== undefined && novas !== t.notas) {
            onGuardar(t.id, { notas: novas });
        }
    }

    // O saldo escrito à mão: vazio apaga-o
    async function aoGuardarSaldo(t) {
        const texto = saldosEditando[t.id];
        if (texto === undefined) return;
        const novo = texto === '' ? null : parseFloat(texto);
        if (novo !== t.saldo) await onGuardarSaldo(t, novo);
        setSaldosEditando(prev => {
            const resto = { ...prev };
            delete resto[t.id];
            return resto;
        });
    }

    // =========================
    // LÓGICA DE REGRAS
    // =========================
    function verificarRegra(t, categoriaId, subcategoriaId) {
        if (!categoriaId) return;
        if (!t?.descricao) return;

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
                <table className="tabela-base tabela-transacoes">
                    <thead>
                        <tr>
                            <th>Data</th>
                            <th>Descrição</th>
                            <th className="col-num">Valor</th>
                            <th className="col-num">Saldo</th>
                            <th>Categoria</th>
                            <th>Subcategoria</th>
                            <th>Conta</th>
                            <th>Notas</th>
                            <th></th>
                        </tr>
                    </thead>

                    <tbody>
                        {transacoes.length === 0 && (
                            <tr>
                                <td colSpan={9} className="tabela-vazia">Nenhuma transação com estes filtros.</td>
                            </tr>
                        )}
                        {transacoes.map((t, i) => {
                            // Um separador sempre que o mês muda, como num extracto
                            const mes = t.data.slice(0, 7);
                            const novoMes = i === 0 || transacoes[i - 1].data.slice(0, 7) !== mes;
                            const [ano, numMes] = mes.split('-');
                            return (
                                <Fragment key={t.id}>
                                    {novoMes && (
                                        <tr className="linha-separador-mes">
                                            <td colSpan={9}>
                                                <span className="separador-mes-nome">{MESES[Number(numMes) - 1]}</span>
                                                <span className="separador-mes-ano">{ano}</span>
                                            </td>
                                        </tr>
                                    )}
                                    <tr className={`${t.valor < 0 ? 'despesa' : 'receita'} ${t.categoria_id ? '' : 'por-categorizar'} revelar-accoes`}>
                                        <td className="col-data"><DataCurta iso={t.data} /></td>
                                        <td className="col-descricao">
                                            {t.descricao}
                                            {t.manual && <span className="etiqueta-manual">manual</span>}
                                        </td>
                                        <td className="valor col-num">{formatarEuros(t.valor)}</td>
                                        <td className="col-num col-saldo">
                                            {t.saldo_editavel ? (
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    className="input-saldo"
                                                    value={saldosEditando[t.id] ?? t.saldo ?? ''}
                                                    onChange={e => setSaldosEditando(prev => ({ ...prev, [t.id]: e.target.value }))}
                                                    onBlur={() => aoGuardarSaldo(t)}
                                                    placeholder="—"
                                                    title="Saldo da conta no fim deste dia, como o banco o mostra"
                                                />
                                            ) : formatarEuros(t.saldo)}
                                        </td>
                                        <td>
                                            <select
                                                className="select-celula"
                                                value={t.categoria_id ?? ''}
                                                onChange={e => aoMudarCategoria(t, e.target.value ? Number(e.target.value) : null)}
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
                                                className="select-celula"
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
        
                                        <td><span className="chip">{t.conta_nome ?? '—'}</span></td>
        
                                        <td>
                                            <input
                                                type="text"
                                                className="input-nota"
                                                value={notasEditando[t.id] ?? t.notas ?? ''}
                                                onChange={e => aoEditarNotas(t.id, e.target.value)}
                                                onBlur={() => aoGuardarNotas(t)}
                                                placeholder="—"
                                            />
                                        </td>
        
                                        <td className="col-accoes">
                                            {t.manual && (
                                                <div className="accoes">
                                                    <button
                                                        className="perigo"
                                                        title="Apagar a transação manual"
                                                        onClick={() => onApagar(t)}
                                                    >
                                                        <Icone nome="apagar" />
                                                    </button>
                                                </div>
                                            )}
                                        </td>
                                    </tr>
                                </Fragment>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* MODAL */}
            {modalRegra && (
                <div className="modal-overlay">
                    <div className="modal">
                        <h3>Criar regra de categorização?</h3>
                        <p className="modal-descricao">
                            Ajusta o início e o fim do texto a procurar: as transações com estas palavras
                            passam a ficar nesta categoria.
                        </p>

                        <p className="modal-descricao-expandida">
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

                        <p className="palavra-chave-preview">
                            Palavra-chave:{' '}
                            <strong>
                                {modalRegra.descricao
                                    .slice(modalRegra.inicio, modalRegra.fim)
                                    .trim()}
                            </strong>
                        </p>

                        <div className="modal-acoes">
                            <button className="btn-ghost" onClick={() => setModalRegra(null)}>
                                Ignorar
                            </button>

                            <button
                                className="btn-primario"
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

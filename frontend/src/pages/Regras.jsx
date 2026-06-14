import { useState, useEffect } from 'react';
import { listarRegras, criarRegra, apagarRegra, preVisualizarRegras, aplicarEmMassa } from '../api/regras';
import { listarCategorias, listarSubcategorias } from '../api/categorias';
import './Regras.css';

export default function Regras() {
    const [regras, setRegras] = useState([]);
    const [categorias, setCategorias] = useState([]);
    const [subcategorias, setSubcategorias] = useState([]);
    const [form, setForm] = useState({
        palavra_chave: '',
        categoria_id: '',
        subcategoria_id: '',
    });
    const [feedback, setFeedback] = useState(null);

    // Estado do modal de aplicação em massa
    const [modalAberto, setModalAberto] = useState(false);
    const [semConflito, setSemConflito] = useState([]);
    const [comConflito, setComConflito] = useState([]);
    const [conflitosAprovados, setConflitosAprovados] = useState([]);
    const [indiceConflito, setIndiceConflito] = useState(0);
    const [fase, setFase] = useState('resumo'); // 'resumo' | 'conflitos' | 'concluido'
    const [resultado, setResultado] = useState(null);

    useEffect(() => {
        carregar();
        listarCategorias().then(res => setCategorias(res.data));
    }, []);

    async function carregar() {
        const res = await listarRegras();
        setRegras(res.data);
    }

    async function aoMudarCategoria(categoriaId) {
        setForm(prev => ({ ...prev, categoria_id: categoriaId, subcategoria_id: '' }));
        if (categoriaId) {
            const res = await listarSubcategorias(categoriaId);
            setSubcategorias(res.data);
        } else {
            setSubcategorias([]);
        }
    }

    async function aoSubmeter() {
        if (!form.palavra_chave.trim() || !form.categoria_id) return;
        try {
            const res = await criarRegra({
                palavra_chave: form.palavra_chave.trim(),
                categoria_id: Number(form.categoria_id),
                subcategoria_id: form.subcategoria_id ? Number(form.subcategoria_id) : null,
            });
            setFeedback({ texto: `Regra criada. ${res.data.transacoes_atualizadas} transações actualizadas.`, erro: false });
            setForm({ palavra_chave: '', categoria_id: '', subcategoria_id: '' });
            setSubcategorias([]);
            carregar();
        } catch (e) {
            setFeedback({ texto: e.response?.data?.detail ?? 'Erro ao criar regra.', erro: true });
        }
    }

    async function aoApagar(id) {
        if (!confirm('Apagar regra?')) return;
        await apagarRegra(id);
        carregar();
    }

    async function aoAbrirModal() {
        const res = await preVisualizarRegras();
        setSemConflito(res.data.sem_conflito);
        setComConflito(res.data.com_conflito);
        setConflitosAprovados([]);
        setIndiceConflito(0);
        setFase(res.data.com_conflito.length > 0 ? 'resumo' : 'resumo');
        setModalAberto(true);
    }

    function aoAprovarConflito(t) {
        const aprovado = {
            id: t.id,
            categoria_id: t.categoria_sugerida_id,
            subcategoria_id: t.subcategoria_sugerida_id,
        };
        const novosAprovados = [...conflitosAprovados, aprovado];
        setConflitosAprovados(novosAprovados);

        if (indiceConflito + 1 >= comConflito.length) {
            aplicarComAprovados(novosAprovados);
        } else {
            setIndiceConflito(prev => prev + 1);
        }
    }

    function avancarConflito() {
        if (indiceConflito + 1 >= comConflito.length) {
            aplicarComAprovados(conflitosAprovados);
        } else {
            setIndiceConflito(prev => prev + 1);
        }
    }

    async function aplicarComAprovados(aprovados) {
        const ids = [
            ...semConflito.map(t => ({
                id: t.id,
                categoria_id: t.categoria_id,
                subcategoria_id: t.subcategoria_sugerida_id,
            })),
            ...aprovados,
        ];

        if (ids.length === 0) {
            setResultado({ aplicadas: 0 });
            setFase('concluido');
            return;
        }

        const res = await aplicarEmMassa(ids);
        setResultado(res.data);
        setFase('concluido');
    }

    function fecharModal() {
        setModalAberto(false);
        setFase('resumo');
        setResultado(null);
    }

    const conflitoActual = comConflito[indiceConflito];

    return (
        <div className="regras-page">
            <div className="regras-header">
                <h1>Regras de categorização</h1>
                <button className="btn-aplicar" onClick={aoAbrirModal}>
                    Aplicar regras às transações
                </button>
            </div>

            <div className="regras-form">
                <input
                    type="text"
                    placeholder="Palavra-chave..."
                    value={form.palavra_chave}
                    onChange={e => setForm(prev => ({ ...prev, palavra_chave: e.target.value }))}
                />
                <select
                    value={form.categoria_id}
                    onChange={e => aoMudarCategoria(e.target.value)}
                >
                    <option value="">Categoria...</option>
                    {categorias.map(c => (
                        <option key={c.id} value={c.id}>{c.nome}</option>
                    ))}
                </select>
                <select
                    value={form.subcategoria_id}
                    onChange={e => setForm(prev => ({ ...prev, subcategoria_id: e.target.value }))}
                    disabled={!form.categoria_id}
                >
                    <option value="">Subcategoria (opcional)...</option>
                    {subcategorias.map(s => (
                        <option key={s.id} value={s.id}>{s.nome}</option>
                    ))}
                </select>
                <button onClick={aoSubmeter}>Adicionar</button>
            </div>

            {feedback && (
                <p className={`feedback ${feedback.erro ? 'feedback-erro' : ''}`}>
                    {feedback.texto}
                </p>
            )}

            <table className="tabela-regras">
                <thead>
                    <tr>
                        <th>Palavra-chave</th>
                        <th>Categoria</th>
                        <th>Subcategoria</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    {regras.map(r => (
                        <tr key={r.id}>
                            <td>{r.palavra_chave}</td>
                            <td>{r.categoria_nome}</td>
                            <td>{r.subcategoria_nome ?? '—'}</td>
                            <td>
                                <button className="btn-apagar" onClick={() => aoApagar(r.id)}>🗑</button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {modalAberto && (
                <div className="modal-overlay">
                    <div className="modal">

                        {fase === 'resumo' && (
                            <>
                                <h3>Aplicar regras às transações</h3>
                                <p>{semConflito.length} transações serão actualizadas automaticamente.</p>
                                {comConflito.length > 0 && (
                                    <p>{comConflito.length} transações têm conflito de categoria — serão analisadas uma a uma.</p>
                                )}
                                <div className="modal-accoes">
                                    <button onClick={fecharModal}>Cancelar</button>
                                    {comConflito.length > 0 ? (
                                        <button className="btn-confirmar" onClick={() => setFase('conflitos')}>
                                            Analisar conflitos →
                                        </button>
                                    ) : (
                                        <button className="btn-confirmar" onClick={() => aplicarComAprovados([])}>
                                            Aplicar
                                        </button>
                                    )}
                                </div>
                            </>
                        )}

                        {fase === 'conflitos' && conflitoActual && (
                            <>
                                <h3>Conflito {indiceConflito + 1} de {comConflito.length}</h3>
                                <p className="modal-descricao">{conflitoActual.descricao}</p>
                                <div className="conflito-detalhe">
                                    <div>
                                        <span className="label">Categoria actual</span>
                                        <span>{conflitoActual.categoria_atual_nome}</span>
                                    </div>
                                    <div>
                                        <span className="label">Sugerida pela regra</span>
                                        <span>{conflitoActual.categoria_sugerida_nome} → {conflitoActual.subcategoria_sugerida_nome}</span>
                                    </div>
                                </div>
                                <div className="modal-accoes">
                                    <button onClick={avancarConflito}>Ignorar</button>
                                    <button className="btn-confirmar" onClick={() => aoAprovarConflito(conflitoActual)}>
                                        Aplicar regra
                                    </button>
                                </div>
                            </>
                        )}

                        {fase === 'concluido' && (
                            <>
                                <h3>Concluído</h3>
                                <p>{resultado?.aplicadas} transações actualizadas.</p>
                                <div className="modal-accoes">
                                    <button className="btn-confirmar" onClick={fecharModal}>Fechar</button>
                                </div>
                            </>
                        )}

                    </div>
                </div>
            )}
        </div>
    );
}
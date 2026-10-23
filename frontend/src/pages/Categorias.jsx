import { useState, useEffect } from 'react';
import {
    listarCategorias, criarCategoria, renomearCategoria, apagarCategoria,
    criarSubcategoria, renomearSubcategoria, apagarSubcategoria
} from '../api/categorias';
import { NOMES_CLASSE_DESPESA } from '../utils/formatacao';
import '../componentes.css';
import './Categorias.css';

const ESTILO_CLASSE = {
    background: 'var(--bg-tertiary)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border)',
    padding: 'var(--space-xs) var(--space-sm)',
    fontSize: 'var(--text-sm)',
    borderRadius: 'var(--radius-sm)',
};

// A classificação só existe nas subcategorias de categorias de despesa; o valor
// vazio é «sem classificação» (null na API)
function SelectClasse({ valor, onChange }) {
    return (
        <select
            value={valor ?? ''}
            onChange={e => onChange(e.target.value || null)}
            style={ESTILO_CLASSE}
            title="Classificação da despesa, para o mês típico das Estatísticas"
        >
            <option value="">Sem classificação</option>
            {Object.entries(NOMES_CLASSE_DESPESA).map(([chave, nome]) => (
                <option key={chave} value={chave}>{nome}</option>
            ))}
        </select>
    );
}

export default function Categorias() {
    const [categorias, setCategorias] = useState([]);
    const [novaCategoria, setNovaCategoria] = useState({ nome: '', tipo: 'despesa' });
    const [editando, setEditando] = useState({}); // { tipo: 'categoria'|'subcategoria', id, categoriaId, valor }
    const [erro, setErro] = useState('');

    async function carregar() {
        const res = await listarCategorias();
        setCategorias(res.data);
    }

    useEffect(() => {
        // Falso positivo: o setState de carregar() corre depois do await
        // eslint-disable-next-line react-hooks/set-state-in-effect
        carregar();
    }, []);

    async function aoAdicionarCategoria() {
        if (!novaCategoria.nome.trim()) return;
        setErro('');
        try {
            await criarCategoria(novaCategoria.nome.trim(), novaCategoria.tipo);
            setNovaCategoria({ nome: '', tipo: 'despesa' });
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao criar categoria.');
        }
    }

    async function aoRenomearCategoria(id, nome, tipo) {
        setErro('');
        try {
            await renomearCategoria(id, nome, tipo);
            setEditando({});
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao renomear categoria.');
        }
    }

    async function aoApagarCategoria(id) {
        if (!confirm('Apagar categoria e todas as suas subcategorias?')) return;
        try {
            await apagarCategoria(id);
        } catch (e) {
            alert(e.response?.data?.detail || 'Erro ao apagar categoria.');
            return;
        }
        carregar();
    }

    async function aoAdicionarSubcategoria(categoriaId, nome, trataPatrimonio = false, classeDespesa = undefined) {
        if (!nome.trim()) return;
        setErro('');
        try {
            await criarSubcategoria(categoriaId, nome.trim(), trataPatrimonio, classeDespesa);
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao criar subcategoria.');
        }
    }

    async function aoRenomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio, classeDespesa) {
        setErro('');
        try {
            await renomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio, classeDespesa);
            setEditando({});
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao renomear subcategoria.');
        }
    }

    async function aoApagarSubcategoria(categoriaId, subcategoriaId) {
        if (!confirm('Apagar subcategoria?')) return;
        try {
            await apagarSubcategoria(categoriaId, subcategoriaId);
        } catch (e) {
            alert(e.response?.data?.detail || 'Erro ao apagar subcategoria.');
            return;
        }
        carregar();
    }

    return (
        <div className="pagina-container">
            <h1 className="titulo-pagina">Categorias</h1>

            <div className="form-linha nova-categoria" data-tour="categorias-nova-categoria">
                <input
                    type="text"
                    placeholder="Nova categoria..."
                    value={novaCategoria.nome}
                    onChange={e => setNovaCategoria(prev => ({ ...prev, nome: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && aoAdicionarCategoria()}
                />
                <select
                    value={novaCategoria.tipo}
                    onChange={e => setNovaCategoria(prev => ({ ...prev, tipo: e.target.value }))}
                >
                    <option value="despesa">Despesa</option>
                    <option value="receita">Receita</option>
                    <option value="investimento">Investimento</option>
                    <option value="transferencia">Transferência</option>
                </select>
                <button onClick={aoAdicionarCategoria}>Adicionar</button>
            </div>

            {erro && <p className="erro">{erro}</p>}

            <div className="lista-itens">
                {categorias.map(cat => (
                    <CategoriaItem
                        key={cat.id}
                        cat={cat}
                        editando={editando}
                        setEditando={setEditando}
                        onRenomear={aoRenomearCategoria}
                        onApagar={aoApagarCategoria}
                        onAdicionarSub={aoAdicionarSubcategoria}
                        onRenomearSub={aoRenomearSubcategoria}
                        onApagarSub={aoApagarSubcategoria}
                    />
                ))}
            </div>
        </div>
    );
}

function CategoriaItem({ cat, editando, setEditando, onRenomear, onApagar, onAdicionarSub, onRenomearSub, onApagarSub }) {
    const [aCriarSub, setACriarSub] = useState(false);
    const [novaSub, setNovaSub] = useState('');
    const [novaSubPatrimonio, setNovaSubPatrimonio] = useState(false);
    const [novaSubClasse, setNovaSubClasse] = useState(null);
    const eDespesa = cat.tipo === 'despesa';

    function submeterNovaSub() {
        if (!novaSub.trim()) return;
        onAdicionarSub(cat.id, novaSub, novaSubPatrimonio, eDespesa ? novaSubClasse : undefined);
        setNovaSub('');
        setNovaSubPatrimonio(false);
        setNovaSubClasse(null);
        setACriarSub(false);
    }

    function cancelarNovaSub() {
        setACriarSub(false);
        setNovaSub('');
        setNovaSubPatrimonio(false);
        setNovaSubClasse(null);
    }

    function confirmarSub(sub) {
        onRenomearSub(cat.id, sub.id, editando.valor, editando.trataPatrimonio, eDespesa ? editando.classeDespesa : undefined);
    }
    const estaAEditar = editando.tipoEdicao === 'categoria' && editando.id === cat.id;

    return (
        <div className="item-lista">
            <div className="item-cabecalho">
                {estaAEditar ? (
                    <>
                        <input
                            autoFocus
                            value={editando.valor}
                            onChange={e => setEditando(prev => ({ ...prev, valor: e.target.value }))}
                            onKeyDown={e => {
                                if (e.key === 'Enter') onRenomear(cat.id, editando.valor, editando.tipoCategoria);
                                if (e.key === 'Escape') setEditando({});
                            }}
                        />
                        <select
                            value={editando.tipoCategoria}
                            onChange={e => setEditando(prev => ({ ...prev, tipoCategoria: e.target.value }))}
                        >
                            <option value="despesa">Despesa</option>
                            <option value="receita">Receita</option>
                            <option value="investimento">Investimento</option>
                            <option value="transferencia">Transferência</option>
                        </select>
                        <button className="btn-confirmar" onClick={() => onRenomear(cat.id, editando.valor, editando.tipoCategoria)}>✓</button>
                        <button className="btn-cancelar" onClick={() => setEditando({})}>✕</button>
                    </>
                ) : (
                    <>
                        <div style={{ display: 'flex', alignItems: 'center' }}>
                            <span className="item-nome">{cat.nome}</span>
                            <span className={`badge-tipo badge-tipo-${cat.tipo}`}>{cat.tipo}</span>
                            <span className="tipo-info" title={"Despesa: gastos normais (alimentação, transportes, etc.)\nReceita: entradas de dinheiro (salário, vendas, etc.)\nInvestimento: alocação de capital (ETFs, poupança, etc.)\nTransferência: movimentos internos entre contas (excluídos das métricas)"}>ℹ</span>
                        </div>
                    </>
                )}
                <div className="accoes">
                    <button onClick={() => setEditando({ tipoEdicao: 'categoria', id: cat.id, valor: cat.nome, tipoCategoria: cat.tipo })}>✏️</button>
                    <button className="btn-ghost" onClick={() => onApagar(cat.id)}>🗑</button>
                </div>
            </div>

            <div className="subcategorias">
                {cat.subcategorias?.map(sub => {
                    const estaAEditarSub = editando.tipo === 'subcategoria' && editando.id === sub.id;
                    return (
                        <div key={sub.id} className="subcategoria-item">
                            {estaAEditarSub ? (
                                <>
                                    <input
                                        autoFocus
                                        value={editando.valor}
                                        onChange={e => setEditando(prev => ({ ...prev, valor: e.target.value }))}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter') confirmarSub(sub);
                                            if (e.key === 'Escape') setEditando({});
                                        }}
                                    />
                                    <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                        <input
                                            type="checkbox"
                                            checked={!!editando.trataPatrimonio}
                                            onChange={e => setEditando(prev => ({ ...prev, trataPatrimonio: e.target.checked }))}
                                            style={{ width: 'auto' }}
                                        />
                                        Património
                                    </label>
                                    {eDespesa && (
                                        <SelectClasse
                                            valor={editando.classeDespesa}
                                            onChange={v => setEditando(prev => ({ ...prev, classeDespesa: v }))}
                                        />
                                    )}
                                    <button className="btn-confirmar" onClick={() => confirmarSub(sub)}>✓</button>
                                    <button className="btn-cancelar" onClick={() => setEditando({})}>✕</button>
                                </>
                            ) : (
                                <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
                                    <span>{sub.nome}</span>
                                    {sub.trata_patrimonio && (
                                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>P</span>
                                    )}
                                    {eDespesa && sub.classe_despesa && (
                                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', opacity: 0.8 }}>
                                            {NOMES_CLASSE_DESPESA[sub.classe_despesa]}
                                        </span>
                                    )}
                                </span>
                            )}
                            <div className="accoes">
                                <button onClick={() => setEditando({ tipo: 'subcategoria', id: sub.id, categoriaId: cat.id, valor: sub.nome, trataPatrimonio: sub.trata_patrimonio, classeDespesa: sub.classe_despesa })}>✏️</button>
                                <button className="btn-ghost" onClick={() => onApagarSub(cat.id, sub.id)}>🗑</button>
                            </div>
                        </div>
                    );
                })}

                {aCriarSub ? (
                    <div className="nova-subcategoria">
                        <input
                            type="text"
                            autoFocus
                            placeholder="Nova subcategoria..."
                            value={novaSub}
                            onChange={e => setNovaSub(e.target.value)}
                            onKeyDown={e => {
                                if (e.key === 'Enter') submeterNovaSub();
                                if (e.key === 'Escape') cancelarNovaSub();
                            }}
                        />
                        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                            <input
                                type="checkbox"
                                checked={novaSubPatrimonio}
                                onChange={e => setNovaSubPatrimonio(e.target.checked)}
                                style={{ width: 'auto' }}
                            />
                            Património
                        </label>
                        {eDespesa && <SelectClasse valor={novaSubClasse} onChange={setNovaSubClasse} />}
                        <button className="btn-confirmar" onClick={submeterNovaSub}>✓</button>
                        <button className="btn-cancelar" onClick={cancelarNovaSub}>✕</button>
                    </div>
                ) : (
                    <button className="btn-nova-subcategoria" onClick={() => setACriarSub(true)}>+ Nova subcategoria</button>
                )}
            </div>
        </div>
    );
}
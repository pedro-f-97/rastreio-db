import { useState, useEffect } from 'react';
import {
    listarCategorias, criarCategoria, renomearCategoria, apagarCategoria,
    criarSubcategoria, renomearSubcategoria, apagarSubcategoria
} from '../api/categorias';
import '../componentes.css';
import './Categorias.css';

export default function Categorias() {
    const [categorias, setCategorias] = useState([]);
    const [novaCategoria, setNovaCategoria] = useState({ nome: '', tipo: 'despesa' });
    const [editando, setEditando] = useState({}); // { tipo: 'categoria'|'subcategoria', id, categoriaId, valor }

    useEffect(() => {
        carregar();
    }, []);

    async function carregar() {
        const res = await listarCategorias();
        setCategorias(res.data);
    }

    async function aoAdicionarCategoria() {
        if (!novaCategoria.nome.trim()) return;
        await criarCategoria(novaCategoria.nome.trim(), novaCategoria.tipo);
        setNovaCategoria({ nome: '', tipo: 'despesa' });
        carregar();
    }

    async function aoRenomearCategoria(id, nome, tipo) {
        await renomearCategoria(id, nome, tipo);
        setEditando({});
        carregar();
    }

    async function aoApagarCategoria(id) {
        if (!confirm('Apagar categoria e todas as suas subcategorias?')) return;
        await apagarCategoria(id);
        carregar();
    }

    async function aoAdicionarSubcategoria(categoriaId, nome, trataPatrimonio = false) {
        if (!nome.trim()) return;
        await criarSubcategoria(categoriaId, nome.trim(), trataPatrimonio);
        carregar();
    }

    async function aoRenomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio) {
        await renomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio);
        setEditando({});
        carregar();
    }

    async function aoApagarSubcategoria(categoriaId, subcategoriaId) {
        if (!confirm('Apagar subcategoria?')) return;
        await apagarSubcategoria(categoriaId, subcategoriaId);
        carregar();
    }

    return (
        <div className="categorias-page">
            <h1>Categorias</h1>

            <div className="nova-categoria" data-tour="categorias-nova-categoria">
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

            <div className="lista-categorias">
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

    function submeterNovaSub() {
        if (!novaSub.trim()) return;
        onAdicionarSub(cat.id, novaSub, novaSubPatrimonio);
        setNovaSub('');
        setNovaSubPatrimonio(false);
        setACriarSub(false);
    }

    function cancelarNovaSub() {
        setACriarSub(false);
        setNovaSub('');
        setNovaSubPatrimonio(false);
    }
    const estaAEditar = editando.tipoEdicao === 'categoria' && editando.id === cat.id;

    return (
        <div className="categoria-item">
            <div className="categoria-header">
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
                            <span className="categoria-nome">{cat.nome}</span>
                            <span className={`badge-tipo badge-tipo-${cat.tipo}`}>{cat.tipo}</span>
                            <span className="tipo-info" title={"Despesa: gastos normais (alimentação, transportes, etc.)\nReceita: entradas de dinheiro (salário, vendas, etc.)\nInvestimento: alocação de capital (ETFs, poupança, etc.)\nTransferência: movimentos internos entre contas (excluídos das métricas)"}>ℹ</span>
                        </div>
                    </>
                )}
                <div className="accoes">
                    <button onClick={() => setEditando({ tipoEdicao: 'categoria', id: cat.id, valor: cat.nome, tipoCategoria: cat.tipo })}>✏️</button>
                    <button className="btn-apagar" onClick={() => onApagar(cat.id)}>🗑</button>
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
                                            if (e.key === 'Enter') onRenomearSub(cat.id, sub.id, editando.valor, editando.trataPatrimonio);
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
                                    <button className="btn-confirmar" onClick={() => onRenomearSub(cat.id, sub.id, editando.valor, editando.trataPatrimonio)}>✓</button>
                                    <button className="btn-cancelar" onClick={() => setEditando({})}>✕</button>
                                </>
                            ) : (
                                <>
                                    <span>{sub.nome}</span>
                                    {sub.trata_patrimonio && (
                                        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>P</span>
                                    )}
                                </>
                            )}
                            <div className="accoes">
                                <button onClick={() => setEditando({ tipo: 'subcategoria', id: sub.id, categoriaId: cat.id, valor: sub.nome, trataPatrimonio: sub.trata_patrimonio })}>✏️</button>
                                <button className="btn-apagar" onClick={() => onApagarSub(cat.id, sub.id)}>🗑</button>
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
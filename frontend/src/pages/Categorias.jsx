import { useState, useEffect } from 'react';
import {
    listarCategorias, criarCategoria, renomearCategoria, apagarCategoria,
    criarSubcategoria, renomearSubcategoria, apagarSubcategoria
} from '../api/categorias';
import './Categorias.css';

export default function Categorias() {
    const [categorias, setCategorias] = useState([]);
    const [novaCategoria, setNovaCategoria] = useState('');
    const [editando, setEditando] = useState({}); // { tipo: 'categoria'|'subcategoria', id, categoriaId, valor }

    useEffect(() => {
        carregar();
    }, []);

    async function carregar() {
        const res = await listarCategorias();
        setCategorias(res.data);
    }

    async function aoAdicionarCategoria() {
        if (!novaCategoria.trim()) return;
        await criarCategoria(novaCategoria.trim());
        setNovaCategoria('');
        carregar();
    }

    async function aoRenomearCategoria(id, nome) {
        await renomearCategoria(id, nome);
        setEditando({});
        carregar();
    }

    async function aoApagarCategoria(id) {
        if (!confirm('Apagar categoria e todas as suas subcategorias?')) return;
        await apagarCategoria(id);
        carregar();
    }

    async function aoAdicionarSubcategoria(categoriaId, nome) {
        if (!nome.trim()) return;
        await criarSubcategoria(categoriaId, nome.trim());
        carregar();
    }

    async function aoRenomearSubcategoria(categoriaId, subcategoriaId, nome) {
        await renomearSubcategoria(categoriaId, subcategoriaId, nome);
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

            <div className="nova-categoria">
                <input
                    type="text"
                    placeholder="Nova categoria..."
                    value={novaCategoria}
                    onChange={e => setNovaCategoria(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && aoAdicionarCategoria()}
                />
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
    const [novaSub, setNovaSub] = useState('');
    const estaAEditar = editando.tipo === 'categoria' && editando.id === cat.id;

    return (
        <div className="categoria-item">
            <div className="categoria-header">
                {estaAEditar ? (
                    <input
                        autoFocus
                        value={editando.valor}
                        onChange={e => setEditando(prev => ({ ...prev, valor: e.target.value }))}
                        onKeyDown={e => {
                            if (e.key === 'Enter') onRenomear(cat.id, editando.valor);
                            if (e.key === 'Escape') setEditando({});
                        }}
                        onBlur={() => onRenomear(cat.id, editando.valor)}
                    />
                ) : (
                    <span className="categoria-nome">{cat.nome}</span>
                )}
                <div className="accoes">
                    <button onClick={() => setEditando({ tipo: 'categoria', id: cat.id, valor: cat.nome })}>✏️</button>
                    <button className="btn-apagar" onClick={() => onApagar(cat.id)}>🗑</button>
                </div>
            </div>

            <div className="subcategorias">
                {cat.subcategorias?.map(sub => {
                    const estaAEditarSub = editando.tipo === 'subcategoria' && editando.id === sub.id;
                    return (
                        <div key={sub.id} className="subcategoria-item">
                            {estaAEditarSub ? (
                                <input
                                    autoFocus
                                    value={editando.valor}
                                    onChange={e => setEditando(prev => ({ ...prev, valor: e.target.value }))}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter') onRenomearSub(cat.id, sub.id, editando.valor);
                                        if (e.key === 'Escape') setEditando({});
                                    }}
                                    onBlur={() => onRenomearSub(cat.id, sub.id, editando.valor)}
                                />
                            ) : (
                                <span>{sub.nome}</span>
                            )}
                            <div className="accoes">
                                <button onClick={() => setEditando({ tipo: 'subcategoria', id: sub.id, categoriaId: cat.id, valor: sub.nome })}>✏️</button>
                                <button className="btn-apagar" onClick={() => onApagarSub(cat.id, sub.id)}>🗑</button>
                            </div>
                        </div>
                    );
                })}

                <div className="nova-subcategoria">
                    <input
                        type="text"
                        placeholder="Nova subcategoria..."
                        value={novaSub}
                        onChange={e => setNovaSub(e.target.value)}
                        onKeyDown={e => {
                            if (e.key !== 'Enter') return;
                            onAdicionarSub(cat.id, novaSub);
                            setNovaSub('');
                        }}
                    />
                    <button onClick={() => { onAdicionarSub(cat.id, novaSub); setNovaSub(''); }}>+</button>
                </div>
            </div>
        </div>
    );
}
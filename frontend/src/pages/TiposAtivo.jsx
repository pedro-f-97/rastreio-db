import { useState, useEffect } from 'react';
import {
    listarTiposAtivo, criarTipoAtivo, renomearTipoAtivo, apagarTipoAtivo
} from '../api/tiposAtivo';
import './Categorias.css';
import './TiposAtivo.css';

export default function TiposAtivo() {
    const [tipos, setTipos] = useState([]);
    const [novoTipo, setNovoTipo] = useState({ nome: '', tem_unidades: false });
    const [editando, setEditando] = useState({}); // { id, valor, temUnidades }
    const [erro, setErro] = useState('');

    useEffect(() => {
        carregar();
    }, []);

    async function carregar() {
        const res = await listarTiposAtivo();
        setTipos(res.data);
    }

    async function aoAdicionar() {
        if (!novoTipo.nome.trim()) return;
        setErro('');
        try {
            await criarTipoAtivo(novoTipo.nome.trim(), novoTipo.tem_unidades);
            setNovoTipo({ nome: '', tem_unidades: false });
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao criar tipo de ativo.');
        }
    }

    async function aoRenomear(id, nome, temUnidades) {
        setErro('');
        try {
            await renomearTipoAtivo(id, nome, temUnidades);
            setEditando({});
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao editar tipo de ativo.');
        }
    }

    async function aoApagar(id) {
        if (!confirm('Apagar tipo de ativo?')) return;
        setErro('');
        try {
            await apagarTipoAtivo(id);
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao apagar tipo de ativo.');
        }
    }

    return (
        <div className="categorias-page tipos-ativo-page">
            <h1>Tipos de Ativo</h1>

            <div className="nova-categoria">
                <input
                    type="text"
                    placeholder="Novo tipo de ativo..."
                    value={novoTipo.nome}
                    onChange={e => setNovoTipo(prev => ({ ...prev, nome: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && aoAdicionar()}
                />
                <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                    <input
                        type="checkbox"
                        checked={novoTipo.tem_unidades}
                        onChange={e => setNovoTipo(prev => ({ ...prev, tem_unidades: e.target.checked }))}
                        style={{ width: 'auto' }}
                    />
                    Tem unidades
                </label>
                <button onClick={aoAdicionar}>Adicionar</button>
            </div>

            {erro && <p className="erro">{erro}</p>}

            <div className="lista-categorias">
                {tipos.map(tipo => {
                    const estaAEditar = editando.id === tipo.id;
                    return (
                        <div key={tipo.id} className="categoria-item">
                            <div className="categoria-header">
                                {estaAEditar ? (
                                    <>
                                        <input
                                            autoFocus
                                            value={editando.valor}
                                            onChange={e => setEditando(prev => ({ ...prev, valor: e.target.value }))}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter') aoRenomear(tipo.id, editando.valor, editando.temUnidades);
                                                if (e.key === 'Escape') setEditando({});
                                            }}
                                        />
                                        <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-xs)', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                                            <input
                                                type="checkbox"
                                                checked={editando.temUnidades}
                                                onChange={e => setEditando(prev => ({ ...prev, temUnidades: e.target.checked }))}
                                                style={{ width: 'auto' }}
                                            />
                                            Tem unidades
                                        </label>
                                        <button className="btn-confirmar" onClick={() => aoRenomear(tipo.id, editando.valor, editando.temUnidades)}>✓</button>
                                        <button className="btn-cancelar" onClick={() => setEditando({})}>✕</button>
                                    </>
                                ) : (
                                    <div style={{ display: 'flex', alignItems: 'center' }}>
                                        <span className="categoria-nome">{tipo.nome}</span>
                                        {tipo.tem_unidades && (
                                            <span style={{ fontSize: 'var(--text-sm)', color: 'var(--accent)', fontFamily: 'var(--font-mono)', marginLeft: 'var(--space-sm)' }}>
                                                unidades
                                            </span>
                                        )}
                                    </div>
                                )}
                                <div className="accoes">
                                    <button onClick={() => setEditando({ id: tipo.id, valor: tipo.nome, temUnidades: tipo.tem_unidades })}>✏️</button>
                                    <button className="btn-apagar" onClick={() => aoApagar(tipo.id)}>🗑</button>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
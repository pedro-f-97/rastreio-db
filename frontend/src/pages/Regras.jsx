import { useState, useEffect } from 'react';
import { listarRegras, criarRegra, apagarRegra } from '../api/regras';
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
            setFeedback(`Regra criada. ${res.data.transacoes_atualizadas} transações actualizadas.`);
            setForm({ palavra_chave: '', categoria_id: '', subcategoria_id: '' });
            setSubcategorias([]);
            carregar();
        } catch (e) {
            setFeedback(e.response?.data?.detail ?? 'Erro ao criar regra.');
        }
    }

    async function aoApagar(id) {
        if (!confirm('Apagar regra?')) return;
        await apagarRegra(id);
        carregar();
    }

    return (
        <div className="regras-page">
            <h1>Regras de categorização</h1>

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

            {feedback && <p className="feedback">{feedback}</p>}

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
        </div>
    );
}
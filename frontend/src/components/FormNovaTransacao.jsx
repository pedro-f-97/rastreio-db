import { useState, useEffect } from 'react';
import { criarTransacao } from '../api/transacoes';
import { listarCategorias, listarSubcategorias } from '../api/categorias';
import { getContas } from '../api/contas';
import '../componentes.css';

// Criar uma transação à mão, para corrigir o saldo. `inicial` pode trazer a
// conta, a data e o valor já preenchidos (a correção sugerida pela verificação)
export default function FormNovaTransacao({ inicial = {}, onFechar, onCriada }) {
    const [contas, setContas] = useState([]);
    const [categorias, setCategorias] = useState([]);
    const [subcategorias, setSubcategorias] = useState([]);
    const [form, setForm] = useState({
        conta_id: inicial.conta_id ?? '',
        data: inicial.data ?? '',
        descricao: inicial.descricao ?? '',
        valor: inicial.valor ?? '',
        categoria_id: '',
        subcategoria_id: '',
        notas: '',
    });
    const [erro, setErro] = useState(null);
    const [aGuardar, setAGuardar] = useState(false);

    useEffect(() => {
        getContas().then(res => setContas(res.data));
        listarCategorias().then(res => setCategorias(res.data));
    }, []);

    useEffect(() => {
        if (!form.categoria_id) return;
        listarSubcategorias(form.categoria_id).then(res => setSubcategorias(res.data));
    }, [form.categoria_id]);

    const campo = (nome, valor) => setForm(f => ({ ...f, [nome]: valor }));

    async function guardar() {
        if (!form.conta_id || !form.data || !form.descricao.trim() || form.valor === '') {
            setErro('Preenche a conta, a data, a descrição e o valor.');
            return;
        }
        setAGuardar(true);
        setErro(null);
        try {
            const res = await criarTransacao({
                conta_id: Number(form.conta_id),
                data: form.data,
                descricao: form.descricao,
                valor: parseFloat(form.valor),
                // Sem categoria nem subcategoria, o backend aplica as regras
                categoria_id: form.categoria_id ? Number(form.categoria_id) : null,
                subcategoria_id: form.subcategoria_id ? Number(form.subcategoria_id) : null,
                notas: form.notas || null,
            });
            onCriada?.(res.data);
        } catch (err) {
            setErro(err.response?.data?.detail?.toString() || 'Erro ao criar a transação.');
        } finally {
            setAGuardar(false);
        }
    }

    return (
        <div className="modal-overlay" onClick={onFechar}>
            <div className="modal" onClick={e => e.stopPropagation()}>
                <h3>Nova transação</h3>
                <p className="modal-descricao">
                    Inserir transações à mão não é recomendado: o normal é importar o extracto do banco.
                    Usa isto só para corrigir uma diferença no saldo, por exemplo uma transação que o
                    extracto não trouxe.
                </p>

                <label className="label">Conta
                    <select value={form.conta_id} onChange={e => campo('conta_id', e.target.value)}>
                        <option value="">—</option>
                        {contas.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
                    </select>
                </label>
                <label className="label">Data
                    <input type="date" value={form.data} onChange={e => campo('data', e.target.value)} />
                </label>
                <label className="label">Descrição
                    <input value={form.descricao} onChange={e => campo('descricao', e.target.value)} />
                </label>
                <label className="label">Valor, em euros (€), negativo nas saídas
                    <input type="number" step="0.01" value={form.valor} onChange={e => campo('valor', e.target.value)} />
                </label>
                <label className="label">Categoria (sem categoria, aplicam-se as regras)
                    <select
                        value={form.categoria_id}
                        onChange={e => setForm(f => ({ ...f, categoria_id: e.target.value, subcategoria_id: '' }))}
                    >
                        <option value="">—</option>
                        {categorias.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
                    </select>
                </label>
                <label className="label">Subcategoria
                    <select
                        value={form.subcategoria_id}
                        onChange={e => campo('subcategoria_id', e.target.value)}
                        disabled={!form.categoria_id}
                    >
                        <option value="">—</option>
                        {form.categoria_id && subcategorias.map(s => <option key={s.id} value={s.id}>{s.nome}</option>)}
                    </select>
                </label>
                <label className="label">Notas
                    <input value={form.notas} onChange={e => campo('notas', e.target.value)} />
                </label>

                {erro && <p className="erro">{erro}</p>}

                <div className="modal-acoes">
                    <button className="btn-ghost" onClick={onFechar}>Cancelar</button>
                    <button className="btn-primario" onClick={guardar} disabled={aGuardar}>
                        {aGuardar ? 'A guardar…' : 'Criar transação'}
                    </button>
                </div>

                <button className="modal-fechar" onClick={onFechar}>✕</button>
            </div>
        </div>
    );
}

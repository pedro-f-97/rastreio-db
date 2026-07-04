import { useState, useEffect } from 'react';
import { getContas, criarConta, actualizarConta, apagarConta } from '../api/contas';
import './Contas.css';
import { formatarEuros } from '../utils/formatacao';

export default function Contas() {
    const [contas, setContas] = useState([]);
    const [incluirInativas, setIncluirInativas] = useState(false);
    const [novaConta, setNovaConta] = useState({ nome: '', saldo_referencia: '', data_referencia: '' });
    const [editando, setEditando] = useState(null); // { id, nome, saldo_referencia, data_referencia }
    const [erro, setErro] = useState('');

    useEffect(() => {
        carregar();
    }, [incluirInativas]);

    async function carregar() {
        const res = await getContas(incluirInativas);
        setContas(res.data);
    }

    async function aoAdicionarConta() {
        const { nome, saldo_referencia, data_referencia } = novaConta;
        if (!nome.trim() || data_referencia === '') return;
        setErro('');
        try {
            await criarConta({
                nome: nome.trim(),
                saldo_referencia: parseFloat(saldo_referencia) || 0,
                data_referencia,
            });
            setNovaConta({ nome: '', saldo_referencia: '', data_referencia: '' });
            carregar();
        } catch (e) {
            if (e.response?.status === 409) setErro('Já existe uma conta com este nome.');
            else setErro('Erro ao criar conta.');
        }
    }

    async function aoGuardarEdicao() {
        if (!editando.nome.trim() || !editando.data_referencia) return;
        await actualizarConta(editando.id, {
            nome: editando.nome.trim(),
            saldo_referencia: parseFloat(editando.saldo_referencia) || 0,
            data_referencia: editando.data_referencia,
        });
        setEditando(null);
        carregar();
    }

    async function aoApagarOuDesativar(id) {
        const conta = contas.find(c => c.id === id);
        const msg = `Eliminar a conta "${conta.nome}"? Se tiver transacções associadas, será desactivada em vez de eliminada.`;
        if (!confirm(msg)) return;
        const res = await apagarConta(id);
        const acao = res.data?.acao;
        if (acao === 'desativada') alert(`A conta "${conta.nome}" foi desactivada (tem transacções associadas).`);
        carregar();
    }

    async function aoReativar(id) {
        await actualizarConta(id, { ativa: true });
        carregar();
    }

    return (
        <div className="contas-page">
            <h1>Contas</h1>

            <div className="nova-conta">
                <input
                    type="text"
                    placeholder="Nome da conta..."
                    value={novaConta.nome}
                    onChange={e => setNovaConta(p => ({ ...p, nome: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && aoAdicionarConta()}
                />
                <input
                    type="number"
                    placeholder="Saldo de referência"
                    value={novaConta.saldo_referencia}
                    onChange={e => setNovaConta(p => ({ ...p, saldo_referencia: e.target.value }))}
                    step="0.01"
                />
                <input
                    type="date"
                    value={novaConta.data_referencia}
                    onChange={e => setNovaConta(p => ({ ...p, data_referencia: e.target.value }))}
                />
                <button onClick={aoAdicionarConta}>Adicionar</button>
            </div>
            {erro && <p className="erro-conta">{erro}</p>}

            <label className="toggle-inativas">
                <input
                    type="checkbox"
                    checked={incluirInativas}
                    onChange={e => setIncluirInativas(e.target.checked)}
                />
                Mostrar contas inactivas
            </label>

            <div className="lista-contas">
                {contas.map(conta => (
                    <div key={conta.id} className={`conta-item${!conta.ativa ? ' conta-inativa' : ''}`}>
                        {editando?.id === conta.id ? (
                            <div className="conta-edicao">
                                <input
                                    autoFocus
                                    type="text"
                                    value={editando.nome}
                                    onChange={e => setEditando(p => ({ ...p, nome: e.target.value }))}
                                    onKeyDown={e => {
                                        if (e.key === 'Enter') aoGuardarEdicao();
                                        if (e.key === 'Escape') setEditando(null);
                                    }}
                                />
                                <div className="campo-referencia">
                                    <label>Saldo de referência</label>
                                    <input
                                        type="number"
                                        value={editando.saldo_referencia}
                                        onChange={e => setEditando(p => ({ ...p, saldo_referencia: e.target.value }))}
                                        step="0.01"
                                    />
                                </div>
                                <div className="campo-referencia">
                                    <label>Data de referência</label>
                                    <input
                                        type="date"
                                        value={editando.data_referencia}
                                        onChange={e => setEditando(p => ({ ...p, data_referencia: e.target.value }))}
                                    />
                                </div>
                                <div className="accoes">
                                    <button className="btn-confirmar" onClick={aoGuardarEdicao}>✓</button>
                                    <button className="btn-cancelar" onClick={() => setEditando(null)}>✕</button>
                                </div>
                            </div>
                        ) : (
                            <div className="conta-header">
                                <div className="conta-info">
                                    <span className="conta-nome">{conta.nome}</span>
                                    {!conta.ativa && <span className="badge-inativa">inactiva</span>}
                                    <span className="conta-detalhe">
                                        Ref. <span className="valor-mono">{formatarEuros(Number(conta.saldo_referencia))}</span>
                                        {' '}em <span className="valor-mono">{conta.data_referencia}</span>
                                    </span>
                                </div>
                                <div className="accoes">
                                    {conta.ativa ? (
                                        <>
                                            <button onClick={() => setEditando({
                                                id: conta.id,
                                                nome: conta.nome,
                                                saldo_referencia: conta.saldo_referencia,
                                                data_referencia: conta.data_referencia,
                                            })}>✏️</button>
                                            <button onClick={() => aoApagarOuDesativar(conta.id)}>🗑</button>
                                        </>
                                    ) : (
                                        <button className="btn-reativar" onClick={() => aoReativar(conta.id)}>Reactivar</button>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                ))}
                {contas.length === 0 && (
                    <p className="sem-contas">Nenhuma conta encontrada.</p>
                )}
            </div>
        </div>
    );
}
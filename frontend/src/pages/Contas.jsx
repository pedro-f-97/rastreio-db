import { useState, useEffect, useCallback } from 'react';
import { getContas, getSaldoConta, criarConta, actualizarConta, apagarConta } from '../api/contas';
import './Contas.css';
import '../componentes.css';
import { formatarEuros } from '../utils/formatacao';
import CabecalhoPagina from '../components/CabecalhoPagina';
import Montante from '../components/Montante';
import Icone from '../components/Icone';

export default function Contas() {
    const [contas, setContas] = useState([]);
    const [incluirInativas, setIncluirInativas] = useState(false);
    const [novaConta, setNovaConta] = useState({ nome: '', saldo_referencia: '', data_referencia: '' });
    const [editando, setEditando] = useState(null); // { id, nome, saldo_referencia, data_referencia }
    const [erro, setErro] = useState('');
    // O saldo de hoje de cada conta, só para mostrar
    const [saldos, setSaldos] = useState({});

    const carregar = useCallback(async () => {
        const res = await getContas(incluirInativas);
        setContas(res.data);
        const pares = await Promise.all(
            res.data.map(c => getSaldoConta(c.id).then(r => [c.id, r.data.saldo_atual]).catch(() => [c.id, null]))
        );
        setSaldos(Object.fromEntries(pares));
    }, [incluirInativas]);

    useEffect(() => {
        // Falso positivo: o setState de carregar() corre depois do await
        // eslint-disable-next-line react-hooks/set-state-in-effect
        carregar();
    }, [carregar]);

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
        setErro('');
        let res;
        try {
            res = await apagarConta(id);
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao apagar conta.');
            return;
        }
        const acao = res.data?.acao;
        if (acao === 'desativada') alert(`A conta "${conta.nome}" foi desactivada (tem transacções associadas). Deixa de aparecer nas listas de contas, mas o seu histórico continua a contar no património, e o saldo também, se não for zero.`);
        carregar();
    }

    async function aoReativar(id) {
        await actualizarConta(id, { ativa: true });
        carregar();
    }

    return (
        <div className="pagina-container">
            <CabecalhoPagina
                secao="02 · Configuração"
                titulo="Contas"
                descricao="Uma conta por banco. O saldo de referência é o ponto de partida: o saldo de hoje é ele mais as transações."
            />

            <div className="form-linha nova-conta" data-tour="contas-nova-conta">
                <span className="form-linha-titulo">Nova</span>
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
                    title="Dia a que o saldo de referência diz respeito, no fim do dia (por exemplo, hoje, com o saldo que o banco mostra)"
                    value={novaConta.data_referencia}
                    onChange={e => setNovaConta(p => ({ ...p, data_referencia: e.target.value }))}
                />
                <button onClick={aoAdicionarConta}><Icone nome="mais" /> Adicionar</button>
            </div>
            {erro && <p className="erro">{erro}</p>}

            <label className="toggle-inativas caixa-marcar">
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
                                        title="Dia a que o saldo de referência diz respeito, no fim do dia (por exemplo, hoje, com o saldo que o banco mostra)"
                                        value={editando.data_referencia}
                                        onChange={e => setEditando(p => ({ ...p, data_referencia: e.target.value }))}
                                    />
                                </div>
                                <div className="accoes">
                                    <button className="btn-confirmar" onClick={aoGuardarEdicao} title="Guardar"><Icone nome="confirmar" /></button>
                                    <button className="btn-cancelar" onClick={() => setEditando(null)} title="Cancelar"><Icone nome="fechar" /></button>
                                </div>
                            </div>
                        ) : (
                            <div className="conta-header revelar-accoes">
                                <div className="conta-info">
                                    <div className="conta-titulo">
                                        <span className="conta-icone"><Icone nome="contas" tamanho={18} /></span>
                                        <span className="conta-nome">{conta.nome}</span>
                                        {!conta.ativa && <span className="badge-inativa">inactiva</span>}
                                    </div>
                                    <div className="conta-saldo">
                                        <span className="cartao-titulo">Saldo de hoje</span>
                                        <Montante valor={saldos[conta.id]} className="conta-saldo-valor" />
                                    </div>
                                    <span className="conta-detalhe">
                                        Referência <span className="valor-mono">{formatarEuros(Number(conta.saldo_referencia))}</span>
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
                                            })} title="Editar a conta"><Icone nome="editar" /></button>
                                            <button className="perigo" onClick={() => aoApagarOuDesativar(conta.id)} title="Apagar ou desactivar a conta"><Icone nome="apagar" /></button>
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
                    <p className="estado-vazio conta-vazia">Nenhuma conta encontrada.</p>
                )}
            </div>
        </div>
    );
}
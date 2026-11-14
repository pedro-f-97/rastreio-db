import { useState, useEffect } from 'react';
import {
    listarTiposAtivo, criarTipoAtivo, renomearTipoAtivo, apagarTipoAtivo
} from '../api/tiposAtivo';
import './Categorias.css';
import './TiposAtivo.css';
import '../componentes.css';
import CabecalhoPagina from '../components/CabecalhoPagina';
import Icone from '../components/Icone';
import { NOMES_CLASSIFICACAO_FISCAL } from '../utils/formatacao';

// Como o tipo entra no relatório do IRS: fora, valores mobiliários ou criptoativos
function SelectClassificacao({ valor, onChange }) {
    return (
        <select
            value={valor}
            onChange={e => onChange(e.target.value)}
            className="select-pequeno"
            title="Como os ativos deste tipo entram no relatório do IRS"
        >
            {Object.entries(NOMES_CLASSIFICACAO_FISCAL).map(([chave, nome]) => (
                <option key={chave} value={chave}>{nome}</option>
            ))}
        </select>
    );
}

export default function TiposAtivo() {
    const [tipos, setTipos] = useState([]);
    const [novoTipo, setNovoTipo] = useState({ nome: '', tem_unidades: false, classificacao_fiscal: 'fora' });
    const [editando, setEditando] = useState({}); // { id, valor, temUnidades, classificacao }
    const [erro, setErro] = useState('');

    async function carregar() {
        const res = await listarTiposAtivo();
        setTipos(res.data);
    }

    useEffect(() => {
        // Falso positivo: o setState de carregar() corre depois do await
        // eslint-disable-next-line react-hooks/set-state-in-effect
        carregar();
    }, []);

    async function aoAdicionar() {
        if (!novoTipo.nome.trim()) return;
        setErro('');
        try {
            await criarTipoAtivo(novoTipo.nome.trim(), novoTipo.tem_unidades, novoTipo.classificacao_fiscal);
            setNovoTipo({ nome: '', tem_unidades: false, classificacao_fiscal: 'fora' });
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao criar tipo de ativo.');
        }
    }

    async function aoRenomear({ id, valor, temUnidades, classificacao }) {
        setErro('');
        try {
            await renomearTipoAtivo(id, valor, temUnidades, classificacao);
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
        <div className="pagina-container tipos-ativo-page">
            <CabecalhoPagina
                secao="02 · Configuração"
                titulo="Tipos de Ativo"
                descricao="Com unidades, o custo segue o FIFO das compras e vendas (ETFs, ações). Sem unidades, o custo acumula-se e o valor é o preço registado (um carro, uma casa)."
            />

            <div className="form-linha nova-categoria">
                <span className="form-linha-titulo">Novo</span>
                <input
                    type="text"
                    placeholder="Novo tipo de ativo..."
                    value={novoTipo.nome}
                    onChange={e => setNovoTipo(prev => ({ ...prev, nome: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && aoAdicionar()}
                />
                <label className="caixa-marcar">
                    <input
                        type="checkbox"
                        checked={novoTipo.tem_unidades}
                        onChange={e => setNovoTipo(prev => ({ ...prev, tem_unidades: e.target.checked }))}
                    />
                    Tem unidades
                </label>
                <SelectClassificacao
                    valor={novoTipo.classificacao_fiscal}
                    onChange={v => setNovoTipo(prev => ({ ...prev, classificacao_fiscal: v }))}
                />
                <button onClick={aoAdicionar}><Icone nome="mais" /> Adicionar</button>
            </div>

            {erro && <p className="erro">{erro}</p>}

            <div className="grelha-itens grelha-iguais grelha-tipos">
                {tipos.map(tipo => {
                    const estaAEditar = editando.id === tipo.id;
                    return (
                        <div key={tipo.id} className="item-lista">
                            <div className={`item-cabecalho item-cabecalho-limpo ${estaAEditar ? '' : 'revelar-accoes'}`}>
                                {estaAEditar ? (
                                    <>
                                        <input
                                            autoFocus
                                            value={editando.valor}
                                            onChange={e => setEditando(prev => ({ ...prev, valor: e.target.value }))}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter') aoRenomear(editando);
                                                if (e.key === 'Escape') setEditando({});
                                            }}
                                        />
                                        <label className="caixa-marcar">
                                            <input
                                                type="checkbox"
                                                checked={editando.temUnidades}
                                                onChange={e => setEditando(prev => ({ ...prev, temUnidades: e.target.checked }))}
                                            />
                                            Tem unidades
                                        </label>
                                        <SelectClassificacao
                                            valor={editando.classificacao}
                                            onChange={v => setEditando(prev => ({ ...prev, classificacao: v }))}
                                        />
                                        <button className="btn-confirmar" onClick={() => aoRenomear(editando)} title="Guardar"><Icone nome="confirmar" /></button>
                                        <button className="btn-cancelar" onClick={() => setEditando({})} title="Cancelar"><Icone nome="fechar" /></button>
                                    </>
                                ) : (
                                    <div className="item-titulo">
                                        <span className="tipo-icone"><Icone nome="tipos" tamanho={16} /></span>
                                        <span className="item-nome" title={tipo.nome}>{tipo.nome}</span>
                                        {(tipo.tem_unidades || tipo.classificacao_fiscal !== 'fora') && (
                                            <span className="item-etiquetas">
                                                {tipo.tem_unidades && <span className="chip chip-accent">unidades</span>}
                                                {tipo.classificacao_fiscal !== 'fora' && (
                                                    <span className="chip" title="Os ativos deste tipo entram no relatório do IRS">
                                                        IRS · {NOMES_CLASSIFICACAO_FISCAL[tipo.classificacao_fiscal]}
                                                    </span>
                                                )}
                                            </span>
                                        )}
                                    </div>
                                )}
                                {!estaAEditar && (
                                    <div className="accoes">
                                        <button onClick={() => setEditando({ id: tipo.id, valor: tipo.nome, temUnidades: tipo.tem_unidades, classificacao: tipo.classificacao_fiscal })} title="Editar o tipo"><Icone nome="editar" /></button>
                                        <button className="perigo" onClick={() => aoApagar(tipo.id)} title="Apagar o tipo"><Icone nome="apagar" /></button>
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
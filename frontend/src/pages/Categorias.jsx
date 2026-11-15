import { useState, useEffect } from 'react';
import {
    listarCategorias, criarCategoria, renomearCategoria, apagarCategoria,
    criarSubcategoria, renomearSubcategoria, apagarSubcategoria
} from '../api/categorias';
import { NOMES_CLASSE_DESPESA } from '../utils/formatacao';
import '../componentes.css';
import './Categorias.css';
import CabecalhoPagina from '../components/CabecalhoPagina';
import Icone from '../components/Icone';

const AJUDA_TIPOS = "Despesa: gastos normais (alimentação, transportes, etc.)\nReceita: entradas de dinheiro (salário, vendas, etc.)\nInvestimento: alocação de capital (ETFs, poupança, etc.)\nTransferência: movimentos internos entre contas (excluídos das métricas)";

// A classificação só existe nas subcategorias de categorias de despesa; o valor
// vazio é «sem classificação» (null na API)
function SelectClasse({ valor, onChange }) {
    return (
        <select
            value={valor ?? ''}
            onChange={e => onChange(e.target.value || null)}
            className="select-pequeno"
            title="Classificação da despesa, para o mês típico das Estatísticas"
        >
            <option value="">Sem classificação</option>
            {Object.entries(NOMES_CLASSE_DESPESA).map(([chave, nome]) => (
                <option key={chave} value={chave}>{nome}</option>
            ))}
        </select>
    );
}

// A marca de juros: as transações da subcategoria contam como juros no IRS
function CaixaJuros({ valor, onChange }) {
    return (
        <label className="caixa-marcar" title="As transações desta subcategoria contam como juros no relatório do IRS">
            <input type="checkbox" checked={!!valor} onChange={e => onChange(e.target.checked)} />
            Juros (IRS)
        </label>
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

    async function aoAdicionarSubcategoria(categoriaId, nome, trataPatrimonio = false, classeDespesa = undefined, jurosIrs = undefined) {
        if (!nome.trim()) return;
        setErro('');
        try {
            await criarSubcategoria(categoriaId, nome.trim(), trataPatrimonio, classeDespesa, jurosIrs);
            carregar();
        } catch (e) {
            setErro(e.response?.data?.detail || 'Erro ao criar subcategoria.');
        }
    }

    async function aoRenomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio, classeDespesa, jurosIrs) {
        setErro('');
        try {
            await renomearSubcategoria(categoriaId, subcategoriaId, nome, trataPatrimonio, classeDespesa, jurosIrs);
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
            <CabecalhoPagina
                secao="02 · Configuração"
                titulo="Categorias"
                descricao="O tipo da categoria decide como entra nas Estatísticas. Nas subcategorias de despesa, a classificação separa o essencial do evitável."
            />

            <div className="form-linha nova-categoria" data-tour="categorias-nova-categoria">
                <span className="form-linha-titulo">Nova</span>
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
                <button onClick={aoAdicionarCategoria}><Icone nome="mais" /> Adicionar</button>
                <span className="tipo-info" title={AJUDA_TIPOS}><Icone nome="info" tamanho={14} /></span>
            </div>

            {erro && <p className="erro">{erro}</p>}

            <div className="grelha-itens grelha-colunas">
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
    const [novaSubJuros, setNovaSubJuros] = useState(false);
    const eDespesa = cat.tipo === 'despesa';
    // A marca de juros só existe nas subcategorias de receita
    const eReceita = cat.tipo === 'receita';

    function submeterNovaSub() {
        if (!novaSub.trim()) return;
        onAdicionarSub(cat.id, novaSub, novaSubPatrimonio, eDespesa ? novaSubClasse : undefined, eReceita ? novaSubJuros : undefined);
        setNovaSub('');
        setNovaSubPatrimonio(false);
        setNovaSubClasse(null);
        setNovaSubJuros(false);
        setACriarSub(false);
    }

    function cancelarNovaSub() {
        setACriarSub(false);
        setNovaSub('');
        setNovaSubPatrimonio(false);
        setNovaSubClasse(null);
        setNovaSubJuros(false);
    }

    function confirmarSub(sub) {
        onRenomearSub(cat.id, sub.id, editando.valor, editando.trataPatrimonio, eDespesa ? editando.classeDespesa : undefined, eReceita ? editando.jurosIrs : undefined);
    }
    const estaAEditar = editando.tipoEdicao === 'categoria' && editando.id === cat.id;

    return (
        <div className={`item-lista categoria-cartao categoria-${cat.tipo}`}>
            <div className="item-cabecalho revelar-accoes">
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
                        <button className="btn-confirmar" onClick={() => onRenomear(cat.id, editando.valor, editando.tipoCategoria)} title="Guardar"><Icone nome="confirmar" /></button>
                        <button className="btn-cancelar" onClick={() => setEditando({})} title="Cancelar"><Icone nome="fechar" /></button>
                    </>
                ) : (
                    <>
                        <div className="item-titulo">
                            <span className="item-nome">{cat.nome}</span>
                            <span className={`badge-tipo badge-tipo-${cat.tipo}`} title={AJUDA_TIPOS}>{cat.tipo}</span>
                        </div>
                    </>
                )}
                {!estaAEditar && (
                    <div className="accoes">
                        <button onClick={() => setEditando({ tipoEdicao: 'categoria', id: cat.id, valor: cat.nome, tipoCategoria: cat.tipo })} title="Editar a categoria"><Icone nome="editar" /></button>
                        <button className="perigo" onClick={() => onApagar(cat.id)} title="Apagar a categoria"><Icone nome="apagar" /></button>
                    </div>
                )}
            </div>

            <div className="subcategorias">
                {cat.subcategorias?.map(sub => {
                    const estaAEditarSub = editando.tipo === 'subcategoria' && editando.id === sub.id;
                    return (
                        <div key={sub.id} className={`subcategoria-item ${estaAEditarSub ? 'a-editar' : 'revelar-accoes'}`}>
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
                                    <label className="caixa-marcar">
                                        <input
                                            type="checkbox"
                                            checked={!!editando.trataPatrimonio}
                                            onChange={e => setEditando(prev => ({ ...prev, trataPatrimonio: e.target.checked }))}
                                        />
                                        Património
                                    </label>
                                    {eDespesa && (
                                        <SelectClasse
                                            valor={editando.classeDespesa}
                                            onChange={v => setEditando(prev => ({ ...prev, classeDespesa: v }))}
                                        />
                                    )}
                                    {eReceita && (
                                        <CaixaJuros
                                            valor={editando.jurosIrs}
                                            onChange={v => setEditando(prev => ({ ...prev, jurosIrs: v }))}
                                        />
                                    )}
                                    <button className="btn-confirmar" onClick={() => confirmarSub(sub)} title="Guardar"><Icone nome="confirmar" /></button>
                                    <button className="btn-cancelar" onClick={() => setEditando({})} title="Cancelar"><Icone nome="fechar" /></button>
                                </>
                            ) : (
                                <span className="subcategoria-nome">
                                    <span>{sub.nome}</span>
                                    {sub.trata_patrimonio && (
                                        <span className="chip chip-accent" title="As transações desta subcategoria contam para o património">Património</span>
                                    )}
                                    {eDespesa && sub.classe_despesa && (
                                        <span className={`chip chip-ponto classe-${sub.classe_despesa}`}>
                                            {NOMES_CLASSE_DESPESA[sub.classe_despesa]}
                                        </span>
                                    )}
                                    {eReceita && sub.juros_irs && (
                                        <span className="chip" title="As transações desta subcategoria contam como juros no relatório do IRS">Juros (IRS)</span>
                                    )}
                                </span>
                            )}
                            {!estaAEditarSub && (
                                <div className="accoes">
                                    <button onClick={() => setEditando({ tipo: 'subcategoria', id: sub.id, categoriaId: cat.id, valor: sub.nome, trataPatrimonio: sub.trata_patrimonio, classeDespesa: sub.classe_despesa, jurosIrs: sub.juros_irs })} title="Editar a subcategoria"><Icone nome="editar" tamanho={14} /></button>
                                    <button className="perigo" onClick={() => onApagarSub(cat.id, sub.id)} title="Apagar a subcategoria"><Icone nome="apagar" tamanho={14} /></button>
                                </div>
                            )}
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
                        <label className="caixa-marcar">
                            <input
                                type="checkbox"
                                checked={novaSubPatrimonio}
                                onChange={e => setNovaSubPatrimonio(e.target.checked)}
                            />
                            Património
                        </label>
                        {eDespesa && <SelectClasse valor={novaSubClasse} onChange={setNovaSubClasse} />}
                        {eReceita && <CaixaJuros valor={novaSubJuros} onChange={setNovaSubJuros} />}
                        <button className="btn-confirmar" onClick={submeterNovaSub} title="Criar"><Icone nome="confirmar" /></button>
                        <button className="btn-cancelar" onClick={cancelarNovaSub} title="Cancelar"><Icone nome="fechar" /></button>
                    </div>
                ) : (
                    <button className="btn-ghost btn-nova-subcategoria" onClick={() => setACriarSub(true)}><Icone nome="mais" tamanho={14} /> Nova subcategoria</button>
                )}
            </div>
        </div>
    );
}
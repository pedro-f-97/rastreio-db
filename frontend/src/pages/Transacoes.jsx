import { useState, useEffect, useCallback } from 'react';
import { listarTransacoes, atualizarTransacao, apagarTransacao } from '../api/transacoes';
import { listarCategorias, listarSubcategorias } from '../api/categorias';
import TabelaTransacoes from '../components/TabelaTransacoes';
import FiltrosTransacoes from '../components/FiltrosTransacoes';
import FormNovaTransacao from '../components/FormNovaTransacao';
import VerificacaoSaldo from '../components/VerificacaoSaldo';
import { listarRegras, criarRegra } from '../api/regras';
import { exportarBackup, importarBackup } from '../api/backups';
import { getContas } from '../api/contas';
import './Transacoes.css';
import '../componentes.css';
import CabecalhoPagina from '../components/CabecalhoPagina';
import Icone from '../components/Icone';

export default function Transacoes({ onDadosAlterados }) {
    // Dados
    const [transacoes, setTransacoes] = useState([]);
    const [categorias, setCategorias] = useState([]);
    const [total, setTotal] = useState(0);
    const [contas, setContas] = useState([]);

    // Filtros e paginação
    const [filtros, setFiltros] = useState({
        pagina: 1,
        tamanho: 50,
        mes: null,
        ano: null,
        categoria_id: null,
        subcategoria_id: null,
        conta_id: null,       // ← linha nova
        sinal: null,
        descricao: null,
    });

    // Estado da UI
    const [carregando, setCarregando] = useState(false);
    const [erro, setErro] = useState(null);
    const [regras, setRegras] = useState([]);
    const [novaAberta, setNovaAberta] = useState(false);
    // Um contador por conta, para pedir a verificação do saldo de novo. Ao abrir
    // a página verificam-se todas as contas activas
    const [verificacoes, setVerificacoes] = useState({});

    const totalPaginas = Math.ceil(total / filtros.tamanho);

    const handleImportarFicheiro = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const confirmar = window.confirm(
            "⚠️ Restaurar um backup substitui os dados atuais.\n\n" +
            "O estado atual fica guardado numa cópia com a data e a hora no nome (rastreio.db.anterior-...), na pasta dados, ao lado da base de dados. Ficam as 5 cópias mais recentes.\n\n" +
            "Queres continuar?"
        );
        if (!confirmar) return;

        try {
            await importarBackup(file);
            alert("Base de dados restaurada com sucesso!");
            
            // Limpa o valor do input para permitir importar o mesmo ficheiro duas vezes seguidas se necessário
            e.target.value = null; 

            // Força o recarregamento total da página
            window.location.reload(); 
        } catch (err) {
            console.error(err);
            alert("Erro ao importar backup: " + (err.response?.data?.detail || err.message));
        }
    };

    // Carrega transações sempre que os filtros mudam
    const carregarTransacoes = useCallback(async () => {
        setCarregando(true);
        setErro(null);
        try {
            // Remove nulls antes de enviar — axios não envia params null
            const params = Object.fromEntries(
                Object.entries(filtros).filter(([, v]) => v !== null)
            );
            const res = await listarTransacoes(params);
            setTransacoes(res.data.items);
            setTotal(res.data.total);
        } catch {
            setErro('Erro ao carregar transações.');
        } finally {
            setCarregando(false);
        }
    }, [filtros]);

    useEffect(() => {
        carregarTransacoes();
    }, [carregarTransacoes]);

    // Carrega categorias e regras uma só vez
    useEffect(() => {
        listarCategorias().then(res => setCategorias(res.data));
        listarRegras().then(res => setRegras(res.data));
        getContas().then(res => setContas(res.data));
    }, []);

    function mudarFiltro(novosFiltros) {
        // Ao mudar filtros, volta sempre à página 1
        setFiltros(prev => ({ ...prev, ...novosFiltros, pagina: 1 }));
    }

    // Grava vários campos num só pedido: categoria e subcategoria mudam juntas,
    // senão o backend recusa o par intermédio. Devolve se gravou.
    async function guardarCampos(id, campos) {
        try {
            await atualizarTransacao(id, campos);
        } catch (err) {
            alert("Erro ao guardar a transação: " + (err.response?.data?.detail || err.message));
            return false;
        }
        // Atualiza só a linha afetada localmente — sem recarregar tudo
        setTransacoes(prev =>
            prev.map(t => t.id === id ? { ...t, ...campos } : t)
        );
        // A categorização afeta o contador "por categorizar" da sidebar
        if ('categoria_id' in campos || 'subcategoria_id' in campos) onDadosAlterados?.();
        return true;
    }

    // Depois de mudar transações ou saldos de uma conta, verifica o seu saldo
    function verificarConta(contaId) {
        setVerificacoes(v => ({ ...v, [contaId]: (v[contaId] ?? 0) + 1 }));
    }

    async function aoCriarTransacao(t) {
        setNovaAberta(false);
        await carregarTransacoes();
        onDadosAlterados?.();
        verificarConta(t.conta_id);
    }

    async function aoApagar(t) {
        if (!window.confirm(`Apagar a transação manual «${t.descricao}» de ${t.data}?`)) return;
        try {
            await apagarTransacao(t.id);
        } catch (err) {
            alert("Erro ao apagar a transação: " + (err.response?.data?.detail || err.message));
            return;
        }
        await carregarTransacoes();
        onDadosAlterados?.();
        verificarConta(t.conta_id);
    }

    async function aoGuardarSaldo(t, saldo) {
        // A verificação compara ao fim do dia: com outras transações no mesmo
        // dia, o saldo tem de ser o do fim do dia. Procuram-se no mês da conta,
        // e não só na página, que pode estar filtrada
        const [ano, mes] = t.data.split('-').map(Number);
        const doMes = await listarTransacoes({ conta_id: t.conta_id, ano, mes, tamanho: 200 });
        const outrasNoDia = doMes.data.items.some(o => o.id !== t.id && o.data === t.data);
        if (saldo !== null && outrasNoDia && !window.confirm(
            "Há outras transações desta conta neste dia. Indica o saldo da conta no fim deste dia, " +
            "depois de todas elas. Guardar?"
        )) return;
        if (await guardarCampos(t.id, { saldo })) verificarConta(t.conta_id);
    }

    async function aoCriarRegra(novaRegra) {
        const res = await criarRegra(novaRegra);
        setRegras(prev => [...prev, res.data.regra]);
        await carregarTransacoes();
        onDadosAlterados?.();
    }

    

    return (
        <div className="pagina-container transacoes-page">
            <CabecalhoPagina
                secao="01 · Transações"
                titulo="Transações"
                descricao="Os movimentos de todas as contas. Categoriza, escreve notas e o saldo que o banco mostra."
            >
                <button onClick={exportarBackup} className="btn-secundario" title="Descarregar uma cópia da base de dados">
                    <Icone nome="descarregar" /> Exportar DB
                </button>

                <label className="btn-secundario" title="Substituir os dados por uma cópia guardada">
                    <Icone nome="carregar" /> Restaurar DB
                    <input
                        type="file"
                        accept=".db"
                        onChange={handleImportarFicheiro}
                        hidden
                    />
                </label>

                <button onClick={() => setNovaAberta(true)} className="btn-primario">
                    <Icone nome="mais" /> Nova transação
                </button>
            </CabecalhoPagina>

            <FiltrosTransacoes
                filtros={filtros}
                categorias={categorias}
                contas={contas}
                onChange={mudarFiltro}
            />

            {contas.filter(c => c.ativa || verificacoes[c.id]).map(c => (
                <VerificacaoSaldo
                    key={c.id}
                    contaId={c.id}
                    contaNome={c.nome}
                    chave={verificacoes[c.id] ?? 0}
                    onTransacaoCriada={aoCriarTransacao}
                />
            ))}

            {novaAberta && (
                <FormNovaTransacao onFechar={() => setNovaAberta(false)} onCriada={aoCriarTransacao} />
            )}

            {erro && <p className="erro-grande">{erro}</p>}
            {carregando ? (
                <p className="carregando">A carregar...</p>
            ) : (
                <>
                    <TabelaTransacoes
                        transacoes={transacoes}
                        categorias={categorias}
                        regras={regras}
                        onGuardar={guardarCampos}
                        onCriarRegra={aoCriarRegra}
                        listarSubcategorias={listarSubcategorias}
                        onGuardarSaldo={aoGuardarSaldo}
                        onApagar={aoApagar}
                    />
                    <div className="paginacao">
                        <span className="total-info"><strong>{total}</strong> transações</span>
                        <div className="paginacao-botoes">
                            <button
                                className="btn-secundario"
                                disabled={filtros.pagina === 1}
                                onClick={() => setFiltros(p => ({ ...p, pagina: p.pagina - 1 }))}
                            >
                                <Icone nome="esquerda" /> Anterior
                            </button>
                            <span className="paginacao-pagina">{filtros.pagina} / {totalPaginas}</span>
                            <button
                                className="btn-secundario"
                                disabled={filtros.pagina === totalPaginas}
                                onClick={() => setFiltros(p => ({ ...p, pagina: p.pagina + 1 }))}
                            >
                                Seguinte <Icone nome="direita" />
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

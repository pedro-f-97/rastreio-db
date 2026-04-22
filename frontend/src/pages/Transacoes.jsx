import { useState, useEffect, useCallback } from 'react';
import { listarTransacoes, atualizarTransacao, importarExtrato } from '../api/transacoes';
import { listarCategorias, listarSubcategorias } from '../api/categorias';
import TabelaTransacoes from '../components/TabelaTransacoes';
import FiltrosTransacoes from '../components/FiltrosTransacoes';
import { listarRegras, criarRegra } from '../api/regras';
import './Transacoes.css';

export default function Transacoes() {
    // Dados
    const [transacoes, setTransacoes] = useState([]);
    const [categorias, setCategorias] = useState([]);
    const [total, setTotal] = useState(0);

    // Filtros e paginação
    const [filtros, setFiltros] = useState({
        pagina: 1,
        tamanho: 50,
        mes: null,
        ano: new Date().getFullYear(),
        categoria_id: null,
    });

    // Estado da UI
    const [carregando, setCarregando] = useState(false);
    const [erro, setErro] = useState(null);
    const [regras, setRegras] = useState([]);

    const totalPaginas = Math.ceil(total / filtros.tamanho);

    // Carrega transações sempre que os filtros mudam
    const carregarTransacoes = useCallback(async () => {
        setCarregando(true);
        setErro(null);
        try {
            // Remove nulls antes de enviar — axios não envia params null
            const params = Object.fromEntries(
                Object.entries(filtros).filter(([_, v]) => v !== null)
            );
            const res = await listarTransacoes(params);
            setTransacoes(res.data.items);
            setTotal(res.data.total);
        } catch (e) {
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
    }, []);

    function mudarFiltro(novosFiltros) {
        // Ao mudar filtros, volta sempre à página 1
        setFiltros(prev => ({ ...prev, ...novosFiltros, pagina: 1 }));
    }

    async function guardarCampo(id, campo, valor) {
        await atualizarTransacao(id, { [campo]: valor });
        // Atualiza só a linha afetada localmente — sem recarregar tudo
        setTransacoes(prev =>
            prev.map(t => t.id === id ? { ...t, [campo]: valor } : t)
        );
    }

    async function aoImportar(e) {
        const ficheiro = e.target.files[0];
        if (!ficheiro) return;
        try {
            const res = await importarExtrato(ficheiro);
            alert(`Importadas: ${res.data.importadas} | Duplicados: ${res.data.duplicados}`);
            carregarTransacoes();
        } catch {
            alert('Erro na importação.');
        }
    }

    async function aoCriarRegra(novaRegra) {
        const res = await criarRegra(novaRegra);
        setRegras(prev => [...prev, res.data.regra]);
    }

    return (
        <div className="transacoes-page">
            <div className="transacoes-header">
                <h1>Transações</h1>
                <label className="btn-importar">
                    Importar extrato
                    <input type="file" accept=".xlsx" onChange={aoImportar} hidden />
                </label>
            </div>

            <FiltrosTransacoes
                filtros={filtros}
                categorias={categorias}
                onChange={mudarFiltro}
            />

            {erro && <p className="erro">{erro}</p>}
            {carregando ? (
                <p className="carregando">A carregar...</p>
            ) : (
                <>
                    <p className="total-info">{total} transações encontradas</p>
                    <TabelaTransacoes
                        transacoes={transacoes}
                        categorias={categorias}
                        regras={regras}
                        onGuardar={guardarCampo}
                        onCriarRegra={aoCriarRegra}
                        listarSubcategorias={listarSubcategorias}
                    />
                    <div className="paginacao">
                        <button
                            disabled={filtros.pagina === 1}
                            onClick={() => setFiltros(p => ({ ...p, pagina: p.pagina - 1 }))}
                        >
                            ← Anterior
                        </button>
                        <span>Página {filtros.pagina} de {totalPaginas}</span>
                        <button
                            disabled={filtros.pagina === totalPaginas}
                            onClick={() => setFiltros(p => ({ ...p, pagina: p.pagina + 1 }))}
                        >
                            Seguinte →
                        </button>
                    </div>
                </>
            )}
        </div>
    );
}
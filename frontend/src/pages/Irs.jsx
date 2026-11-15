import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { obterAnosIrs, obterRelatorioIrs, descarregarCsvIrs } from '../api/irs';
import { classeValor, formatarEuros } from '../utils/formatacao';
import CabecalhoPagina from '../components/CabecalhoPagina';
import Icone from '../components/Icone';
import '../componentes.css';
import './Irs.css';

const formatarData = (iso) => iso.split('-').reverse().join('/');

// O código numérico do país, como no Portal, com as duas letras a seguir
const formatarPais = (pais) => (pais.numero ? `${pais.numero} (${pais.codigo})` : pais.codigo);

// O título de cada quadro das vendas, pelo anexo e pelo quadro
const TITULOS_VENDAS = {
    'G 9': 'Anexo G, quadro 9: valores mobiliários numa corretora portuguesa',
    'J 9.2A': 'Anexo J, quadro 9.2A: valores mobiliários numa corretora estrangeira',
    'G 18A': 'Anexo G, quadro 18A: criptoativos detidos menos de 365 dias',
    'G1 7': 'Anexo G1, quadro 7: criptoativos detidos 365 dias ou mais (não tributados, mas declarados)',
};

async function exportarCsv(ano, tabela) {
    const { data } = await descarregarCsvIrs(ano, tabela);
    const url = URL.createObjectURL(data);
    const ligacao = document.createElement('a');
    ligacao.href = url;
    ligacao.download = `irs-${ano}-${tabela}.csv`;
    ligacao.click();
    // Revogar logo a seguir ao clique podia cortar o download
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function CabecalhoSecao({ numero, titulo, nota, ano, tabela, vazia }) {
    return (
        <div className="secao-cabecalho">
            <h2 className="titulo-secao">
                <span className="titulo-secao-numero">{numero}</span>{titulo}
                {nota && <span className="titulo-secao-nota">{nota}</span>}
            </h2>
            {!vazia && (
                <button className="btn-secundario" onClick={() => exportarCsv(ano, tabela)} title="Um ficheiro com as linhas desta secção, para copiar para o Portal">
                    <Icone nome="descarregar" /> Exportar CSV
                </button>
            )}
        </div>
    );
}

function GrupoVendas({ grupo }) {
    return (
        <div className="irs-grupo">
            <h3 className="irs-grupo-titulo">{TITULOS_VENDAS[`${grupo.anexo} ${grupo.quadro}`]}</h3>
            <div className="tabela-wrapper">
                <table className="tabela-base irs-tabela">
                    <thead>
                        <tr>
                            <th>Ativo</th>
                            <th>País da fonte</th>
                            <th>Código</th>
                            <th>Realização</th>
                            <th className="col-num">Valor</th>
                            <th>Aquisição</th>
                            <th className="col-num">Valor</th>
                            <th className="col-num">Despesas</th>
                            <th>Contraparte</th>
                            <th className="col-num">Dias</th>
                            <th className="col-num">Ganho</th>
                        </tr>
                    </thead>
                    <tbody>
                        {grupo.linhas.map((li, i) => (
                            <tr key={i}>
                                <td>{li.ativo}</td>
                                <td className="col-mono">{formatarPais(li.pais_fonte)}</td>
                                <td className="col-mono">{li.codigo ?? '—'}</td>
                                <td className="col-mono irs-data">{formatarData(li.data_realizacao)}</td>
                                <td className="col-num col-mono">{formatarEuros(li.valor_realizacao)}</td>
                                <td className="col-mono irs-data">{formatarData(li.data_aquisicao)}</td>
                                <td className="col-num col-mono">{formatarEuros(li.valor_aquisicao)}</td>
                                <td className="col-num col-mono">{formatarEuros(li.despesas)}</td>
                                <td className="col-mono">{formatarPais(li.pais_contraparte)}</td>
                                <td className="col-num col-mono">{li.dias}</td>
                                <td className={`col-num col-mono ${classeValor(li.ganho)}`}>{formatarEuros(li.ganho)}</td>
                            </tr>
                        ))}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colSpan={4}>Totais</td>
                            <td className="col-num col-mono">{formatarEuros(grupo.totais.realizacao)}</td>
                            <td />
                            <td className="col-num col-mono">{formatarEuros(grupo.totais.aquisicao)}</td>
                            <td className="col-num col-mono">{formatarEuros(grupo.totais.despesas)}</td>
                            <td colSpan={2} />
                            <td className={`col-num col-mono ${classeValor(grupo.totais.saldo)}`}>{formatarEuros(grupo.totais.saldo)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    );
}

// Os dividendos ou os juros: os portugueses à parte, os do estrangeiro por país
function GrupoRecebido({ grupo, quadroEstrangeiro, comConta }) {
    const titulo = grupo.portugues
        ? 'Portugal: retidos na fonte; só se declaram (anexo E) se optares por juntá-los aos outros rendimentos'
        : `Anexo J, ${quadroEstrangeiro}: ${formatarPais(grupo.pais)}`;
    return (
        <div className="irs-grupo">
            <h3 className="irs-grupo-titulo">{titulo}</h3>
            <div className="tabela-wrapper">
                <table className="tabela-base irs-tabela">
                    <thead>
                        <tr>
                            <th>Data</th>
                            <th>{comConta ? 'Descrição' : 'Ativo'}</th>
                            {comConta && <th>Conta</th>}
                            <th className="col-num">Valor recebido</th>
                        </tr>
                    </thead>
                    <tbody>
                        {grupo.linhas.map((li, i) => (
                            <tr key={i}>
                                <td className="col-mono irs-data">{formatarData(li.data)}</td>
                                <td>{li.descricao}</td>
                                {comConta && <td>{li.conta ?? '—'}</td>}
                                <td className="col-num col-mono">{formatarEuros(li.valor)}</td>
                            </tr>
                        ))}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colSpan={comConta ? 3 : 2}>Total</td>
                            <td className="col-num col-mono">{formatarEuros(grupo.total)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    );
}

export default function Irs() {
    const navigate = useNavigate();
    const [anos, setAnos] = useState(null);
    const [ano, setAno] = useState(null);
    const [relatorio, setRelatorio] = useState(null);

    useEffect(() => {
        obterAnosIrs().then(res => {
            setAnos(res.data);
            if (res.data.length > 0) setAno(res.data[0]);
        });
    }, []);

    useEffect(() => {
        if (ano === null) return;
        // Uma resposta antiga, que chegue depois da do ano escolhido, ignora-se
        let ignorar = false;
        obterRelatorioIrs(ano).then(res => !ignorar && setRelatorio(res.data));
        return () => { ignorar = true; };
    }, [ano]);

    return (
        <div className="pagina-container irs-page">
            <CabecalhoPagina
                secao="04 · Exportar"
                titulo="IRS"
                descricao="As vendas, os dividendos e os juros de um ano, pelos anexos e quadros do Modelo 3, para copiar linha a linha para o Portal das Finanças. Não calcula o imposto."
            >
                {anos?.length > 0 && (
                    <div className="segmentado" role="group" aria-label="Ano">
                        {anos.map(a => (
                            <button key={a} className={a === ano ? 'activo' : ''} aria-pressed={a === ano} onClick={() => setAno(a)}>
                                {a}
                            </button>
                        ))}
                    </div>
                )}
            </CabecalhoPagina>

            {anos?.length === 0 && (
                <p className="estado-vazio">
                    Ainda não há vendas, dividendos nem juros para declarar. Entram as vendas e os dividendos dos tipos de ativo
                    classificados para o IRS, e os juros das subcategorias marcadas como juros.
                </p>
            )}

            {relatorio && (
                <>
                    {relatorio.pendentes > 0 && (
                        <div className="aviso">
                            <Icone nome="aviso" />
                            <span className="aviso-texto">
                                {relatorio.pendentes === 1 ? '1 transação' : `${relatorio.pendentes} transações`} de {relatorio.ano} por
                                tratar como ativo: vendas ou dividendos que ainda não estão neste relatório.
                            </span>
                            <button className="btn-ghost" onClick={() => navigate('/ativos')}>Tratar nos Ativos</button>
                        </div>
                    )}

                    <p className="cartao-nota">
                        As colunas seguem as instruções do Modelo 3 que se encontraram: confirma a ordem no modelo do ano. Os países
                        vão no código numérico da tabela das instruções, com as duas letras entre parênteses.
                    </p>

                    <section className="secao">
                        <CabecalhoSecao numero="01" titulo="Vendas" ano={relatorio.ano} tabela="vendas" vazia={relatorio.vendas.length === 0} />
                        {relatorio.vendas.length === 0
                            ? <p className="estado-vazio">Sem vendas neste ano.</p>
                            : relatorio.vendas.map(g => <GrupoVendas key={`${g.anexo} ${g.quadro}`} grupo={g} />)}
                    </section>

                    <section className="secao">
                        <CabecalhoSecao
                            numero="02"
                            titulo="Dividendos"
                            nota="O valor recebido; o bruto e o imposto retido estão no relatório anual da corretora."
                            ano={relatorio.ano}
                            tabela="dividendos"
                            vazia={relatorio.dividendos.length === 0}
                        />
                        {relatorio.dividendos.length === 0
                            ? <p className="estado-vazio">Sem dividendos neste ano.</p>
                            : relatorio.dividendos.map((g, i) => <GrupoRecebido key={i} grupo={g} quadroEstrangeiro="quadro 8A" />)}
                    </section>

                    <section className="secao">
                        <CabecalhoSecao
                            numero="03"
                            titulo="Juros"
                            nota="O valor recebido; o bruto e o imposto retido estão no documento anual do banco."
                            ano={relatorio.ano}
                            tabela="juros"
                            vazia={relatorio.juros.length === 0}
                        />
                        {relatorio.juros.length === 0
                            ? <p className="estado-vazio">Sem juros neste ano.</p>
                            : relatorio.juros.map((g, i) => <GrupoRecebido key={i} grupo={g} quadroEstrangeiro="quadro 8A" comConta />)}
                    </section>
                </>
            )}
        </div>
    );
}

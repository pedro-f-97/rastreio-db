import { useState, useEffect } from 'react';
import { verificarSaldo } from '../api/contas';
import { formatarEuros, prefixoSinal } from '../utils/formatacao';
import FormNovaTransacao from './FormNovaTransacao';
import '../componentes.css';

const formatarData = (iso) => iso.split('-').reverse().join('/');

// O resumo da verificação do saldo de uma conta, pedido de novo sempre que
// `chave` muda (depois de importar, de criar ou apagar uma transação manual, ou
// de escrever um saldo). Com diferenças, abre um pop-up; sem elas, uma linha.
export default function VerificacaoSaldo({ contaId, contaNome, chave, onTransacaoCriada }) {
    const [resultado, setResultado] = useState(null);
    const [aberto, setAberto] = useState(false);
    const [correcao, setCorrecao] = useState(null);

    useEffect(() => {
        if (!contaId) return;
        // Uma resposta antiga, que chegue depois de um pedido mais recente, ignora-se
        let ignorar = false;
        verificarSaldo(contaId)
            .then(res => {
                if (ignorar) return;
                setResultado(res.data);
                setAberto(res.data.intervalos.length > 0);
            })
            .catch(() => !ignorar && setResultado(null));
        return () => { ignorar = true; };
    }, [contaId, chave]);

    if (!resultado) return null;

    const { diferenca_atual, data_ultimo_saldo, intervalos, dias_ordem_incerta, sugerir_saldo } = resultado;
    const nome = contaNome ? `de «${contaNome}»` : 'da conta';

    const sugestao = sugerir_saldo && (
        <p>
            O último saldo {nome} é de {formatarData(data_ultimo_saldo)}. Escreve o saldo de uma transação
            recente para o confirmar.
        </p>
    );

    function descreverDiferenca() {
        // O último saldo bate certo, mas os anteriores não: falta ou sobra uma
        // transação no passado, que muda o histórico e as estatísticas
        if (diferenca_atual === 0) {
            return `O último saldo ${nome} bate certo com o do banco, mas os anteriores não.`;
        }
        const sentido = diferenca_atual > 0 ? 'acima' : 'abaixo';
        return `O saldo calculado ${nome} está ${formatarEuros(Math.abs(diferenca_atual))} ${sentido} do banco.`;
    }

    return (
        <>
            {intervalos.length === 0 ? (
                <div className="resumo-saldo-linha">
                    <span>Saldo {nome} confirmado em {formatarData(data_ultimo_saldo)}.</span>
                    {sugestao}
                </div>
            ) : (
                <div className="resumo-saldo-linha">
                    <span>O saldo {nome} tem diferenças em relação ao banco.</span>
                    <button className="btn-ghost" onClick={() => setAberto(true)}>Ver</button>
                </div>
            )}

            {aberto && (
                <div className="modal-overlay" onClick={() => setAberto(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <h3>Verificação do saldo</h3>
                        <p>{descreverDiferenca()}</p>
                        <p className="modal-subtitulo">A diferença mudou nestes intervalos:</p>
                        <table className="tabela-base">
                            <tbody>
                                {intervalos.map(i => (
                                    <tr key={i.ate}>
                                        <td>
                                            {i.de
                                                ? `Entre ${formatarData(i.de)} e ${formatarData(i.ate)}`
                                                : `No saldo de referência, de ${formatarData(i.ate)}`}
                                        </td>
                                        <td className="valor" style={{ whiteSpace: 'nowrap' }}>{prefixoSinal(i.variacao)}{formatarEuros(i.variacao)}</td>
                                        <td>
                                            {/* Uma transação não corrige o saldo de referência:
                                                é o saldo no fim desse dia, seja qual for */}
                                            {i.de ? (
                                                <button
                                                    className="btn-secundario"
                                                    onClick={() => setCorrecao({
                                                        conta_id: contaId,
                                                        data: i.ate,
                                                        // O calculado está acima do banco: falta uma saída
                                                        valor: -i.variacao,
                                                    })}
                                                >
                                                    Criar transação de correção
                                                </button>
                                            ) : 'Corrige o saldo de referência na página Contas.'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {dias_ordem_incerta.length > 0 && (
                            <p className="modal-descricao">
                                Nestes dias não foi possível saber qual foi a última transação, e a comparação
                                pode não ser exacta: {dias_ordem_incerta.map(formatarData).join(', ')}.
                            </p>
                        )}
                        {sugestao}
                        <div className="modal-acoes">
                            <button className="btn-ghost" onClick={() => setAberto(false)}>Fechar</button>
                        </div>
                        <button className="modal-fechar" onClick={() => setAberto(false)}>✕</button>
                    </div>
                </div>
            )}

            {correcao && (
                <FormNovaTransacao
                    inicial={correcao}
                    onFechar={() => setCorrecao(null)}
                    onCriada={t => {
                        setCorrecao(null);
                        onTransacaoCriada?.(t);
                    }}
                />
            )}
        </>
    );
}

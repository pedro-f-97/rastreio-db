import { useState, useEffect } from "react";
import { getContas, getSaldoConta } from "../api/contas";
import { useAtivos } from "../hooks/useAtivos";
import "./Patrimonio.css";
import '../componentes.css';
import { classeValor, formatarEuros, formatarEurosEixo, formatarPercentagem, labelMes, prefixoSinal } from '../utils/formatacao';
import { obterCrescimento, obterEvolucao } from "../api/patrimonio";
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid
} from "recharts";
import CabecalhoPagina from "../components/CabecalhoPagina";
import SeletorAno from "../components/SeletorAno";
import Montante from "../components/Montante";
import { TooltipGrafico, TickMes } from "../components/Graficos";
import { EIXO, GRELHA } from "../utils/graficos";

// As três partes do património, pela ordem em que se empilham no gráfico
const PARTES = [
  { chave: "liquidez", nome: "Liquidez", cor: "var(--chart-6)" },
  { chave: "investimentos", nome: "Investimentos", cor: "var(--type-investimento-text)" },
  { chave: "ativos_fisicos", nome: "Bens", cor: "var(--chart-8)" },
];

// Uma linha de detalhe de um cartão: o nome, os pontos de guia e o valor
function LinhaGuia({ nome, children, className = "" }) {
  return (
    <div className="cartao-breakdown-linha">
      <span className="cartao-breakdown-label">{nome}</span>
      <span className="guia-pontos" />
      <span className={`cartao-breakdown-valor ${className}`}>{children}</span>
    </div>
  );
}



export default function Patrimonio() {
  const { ativos, resumos } = useAtivos();
  const [contas, setContas] = useState([]);

  const [evolucao, setEvolucao] = useState([]);

  useEffect(() => {
    obterEvolucao().then(res => setEvolucao(res.data));
  }, []);

  async function carregarContas() {
    // As desactivadas contam no património como no gráfico, mas só aparecem
    // se ainda tiverem dinheiro
    const resContas = await getContas(true);
    const contasComSaldo = await Promise.all(
      resContas.data.map(async (c) => {
        const res = await getSaldoConta(c.id);
        return { ...c, saldo_atual: res.data.saldo_atual };
      })
    );
    setContas(contasComSaldo.filter((c) => c.ativa || c.saldo_atual !== 0));
  }

  useEffect(() => {
    // Falso positivo: o setState de carregarContas() corre depois do await
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarContas();
  }, []);

  // --- Totais ---
  const totalLiquidez = contas.reduce((acc, c) => acc + (c.saldo_atual ?? 0), 0);
  const totalPatrimonioAtivos = Object.values(resumos).reduce((acc, r) => acc + (r.valor_atual ?? 0), 0);
  const totalPatrimonio = totalLiquidez + totalPatrimonioAtivos;

  const ativosInvestimento = ativos.filter((a) => a.contabilizacao === "investimento");
  const ativosBens = ativos.filter((a) => a.contabilizacao === "patrimonio");
  const totalInvestimentos = ativosInvestimento.reduce((acc, a) => {
    const r = resumos[a.id];
    return acc + (r?.valor_atual ?? r?.custo_total ?? 0);
  }, 0);
  const totalBens = ativosBens.reduce((acc, a) => {
    const r = resumos[a.id];
    return acc + (r?.valor_atual ?? 0);
  }, 0);
  const totalCusto = ativosInvestimento.reduce((acc, a) => acc + (resumos[a.id]?.custo_total ?? 0), 0);
  // custo_total vem negativo (dinheiro que saiu), por isso soma-se ao valor
  const totalMaisValia = totalInvestimentos + totalCusto;
  const pctMaisValia = totalCusto !== 0 ? (totalMaisValia / Math.abs(totalCusto)) * 100 : null;

  const [anoSeleccionado, setAnoSeleccionado] = useState('todos');

  function labelMesEvolucao(dataISO) {
    const [ano, mes] = dataISO.split('-');
    return labelMes(ano, parseInt(mes));
  }

  const dadosEvolucao = evolucao.map(p => ({
    ...p,
    ano: parseInt(p.data.split('-')[0]),
    label: labelMesEvolucao(p.data),
  }));

  const anosDisponiveis = [...new Set(dadosEvolucao.map(p => p.ano))].sort();

  const dadosEvolucaoFiltrados = anoSeleccionado === 'todos'
    ? dadosEvolucao
    : dadosEvolucao.filter(p => p.ano === parseInt(anoSeleccionado));

  // Quanto cresce por mês, pela tendência dos meses completos do filtro
  const [crescimento, setCrescimento] = useState(null);

  useEffect(() => {
    let ignorar = false;
    obterCrescimento(anoSeleccionado === 'todos' ? null : parseInt(anoSeleccionado))
      .then(res => !ignorar && setCrescimento(res.data));
    return () => { ignorar = true; };
  }, [anoSeleccionado]);

  const mesAno = (dataISO) => dataISO.slice(0, 7).split('-').reverse().join('/');
  const porMes = (valor, grande = false) => (
    grande
      ? <Montante valor={valor} cor sinal sufixo="/mês" />
      : <span className={classeValor(valor)}>{prefixoSinal(valor)}{formatarEuros(valor)}/mês</span>
  );

  const valoresPartes = { liquidez: totalLiquidez, investimentos: totalInvestimentos, ativos_fisicos: totalBens };
  // A barra da composição só tem as partes positivas: uma liquidez negativa não ocupa espaço
  const somaPositiva = PARTES.reduce((s, p) => s + Math.max(valoresPartes[p.chave], 0), 0);

  return (
    <div className="patrimonio-page">
      <CabecalhoPagina
        secao="03 · Análise"
        titulo="Património"
        descricao="O que tens hoje em contas, investimentos e bens, e como evoluiu no fim de cada mês."
      />

      {/* TOTAL E COMPOSIÇÃO */}
      <section className="painel patrimonio-heroi">
        <div className="heroi-total">
          <span className="cartao-titulo">Património total</span>
          <Montante valor={totalPatrimonio} className="heroi-valor" />
        </div>
        <div className="heroi-composicao">
          <div className="composicao-barra composicao-barra-grossa">
            {somaPositiva > 0 && PARTES.filter(p => valoresPartes[p.chave] > 0).map(p => (
              <div
                key={p.chave}
                style={{ width: `${(valoresPartes[p.chave] / somaPositiva) * 100}%`, background: p.cor }}
                title={p.nome}
              />
            ))}
          </div>
          <div className="heroi-partes">
            {PARTES.map(p => (
              <div key={p.chave} className="heroi-parte">
                <span className="heroi-parte-nome">
                  <span className="legenda-cor" style={{ background: p.cor }} />
                  {p.nome}
                </span>
                <span className="heroi-parte-valor">{formatarEuros(valoresPartes[p.chave])}</span>
                <span className="heroi-parte-pct">
                  {totalPatrimonio > 0 ? formatarPercentagem((valoresPartes[p.chave] / totalPatrimonio) * 100) : '—'}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CARTÕES */}
      <div className="cartoes">
        {/* Liquidez */}
        <div className="cartao" style={{ '--cartao-cor': 'var(--chart-6)' }}>
          <span className="cartao-titulo">Liquidez</span>
          <Montante valor={totalLiquidez} className="cartao-valor" />
          <div className="cartao-breakdown">
            {contas.length === 0 && (
              <span className="cartao-breakdown-label">Nenhuma conta activa</span>
            )}
            {contas.map((c) => (
              <LinhaGuia key={c.id} nome={c.ativa ? c.nome : `${c.nome} (inactiva)`}>
                {formatarEuros(c.saldo_atual)}
              </LinhaGuia>
            ))}
          </div>
        </div>

        {/* Investimentos */}
        <div className="cartao" style={{ '--cartao-cor': 'var(--type-investimento-text)' }}>
          <span className="cartao-titulo">Investimentos</span>
          <Montante valor={totalInvestimentos} className="cartao-valor" />
          <div className="cartao-breakdown">
            {ativosInvestimento.length === 0 && (
              <span className="cartao-breakdown-label">Nenhum ativo</span>
            )}
            {ativosInvestimento.map((a) => {
              const r = resumos[a.id];
              const valor = r?.valor_atual ?? r?.custo_total ?? 0;
              const pct = totalInvestimentos > 0 ? (valor / totalInvestimentos) * 100 : 0;
              return (
                <LinhaGuia key={a.id} nome={a.nome}>
                  {formatarEuros(valor)} <span className="linha-guia-pct">{formatarPercentagem(pct)}</span>
                </LinhaGuia>
              );
            })}
          </div>
        </div>

        {/* Valorização */}
        <div className="cartao" style={{ '--cartao-cor': 'var(--accent)' }}>
          <span className="cartao-titulo">Resultados</span>
          <div className="cartao-valor-linha">
            <Montante valor={totalMaisValia} cor className="cartao-valor" />
            {pctMaisValia !== null && (
              <span className={`chip cartao-subvalor ${classeValor(pctMaisValia, 2)}`}>
                {prefixoSinal(pctMaisValia)}{formatarPercentagem(pctMaisValia, 2)}
              </span>
            )}
          </div>
          <div className="cartao-breakdown">
            {ativosInvestimento.length === 0 && (
              <span className="cartao-breakdown-label">Nenhum ativo</span>
            )}
            {ativosInvestimento.map((a) => {
              const r = resumos[a.id];
              const custo = r?.custo_total ?? 0;
              const mmv = r?.mais_menos_valia;
              const pct = custo !== 0 && mmv != null ? (mmv / Math.abs(custo)) * 100 : null;
              return pct !== null ? (
                <LinhaGuia key={a.id} nome={a.nome} className={classeValor(pct, 2)}>
                  {prefixoSinal(pct)}{formatarPercentagem(pct, 2)}
                </LinhaGuia>
              ) : (
                <LinhaGuia key={a.id} nome={a.nome}>—</LinhaGuia>
              );
            })}
          </div>
        </div>
      </div>

      {/* EVOLUÇÃO DO PATRIMÓNIO */}
      <section className="secao">
        <div className="secao-cabecalho">
          <h2 className="titulo-secao"><span className="titulo-secao-numero">01</span>Evolução do património</h2>
          <SeletorAno anos={anosDisponiveis} valor={anoSeleccionado} onChange={setAnoSeleccionado} />
        </div>
        {crescimento && (
          <div className="crescimento">
            {crescimento.total == null ? (
              <span className="cartao-nota">Poucos meses para calcular a tendência.</span>
            ) : (
              <>
                <div className="crescimento-principal">
                  <span className="cartao-titulo">Crescimento por mês</span>
                  <span className="crescimento-valor">{porMes(crescimento.total, true)}</span>
                </div>
                <div className="crescimento-partes">
                  <div className="crescimento-parte">
                    <span className="crescimento-parte-nome">Do que poupas</span>
                    {porMes(crescimento.poupanca)}
                  </div>
                  <div className="crescimento-parte">
                    <span className="crescimento-parte-nome">Da valorização</span>
                    {porMes(crescimento.valorizacao)}
                  </div>
                </div>
                <span className="crescimento-nota">
                  Tendência de {crescimento.meses} meses, de {mesAno(crescimento.de)} a{' '}
                  {mesAno(crescimento.ate)}
                  {/* Só um período que chega a hoje deixa de fora o mês em curso */}
                  {(anoSeleccionado === 'todos' || parseInt(anoSeleccionado) === new Date().getFullYear())
                    && ', sem o mês em curso'}.
                </span>
              </>
            )}
          </div>
        )}
        <div className="grafico-moldura">
          <div className="legenda grafico-legenda">
            <span className="legenda-item"><span className="legenda-cor linha" style={{ background: 'var(--accent)' }} />Total</span>
            {PARTES.map(p => (
              <span key={p.chave} className="legenda-item"><span className="legenda-cor" style={{ background: p.cor }} />{p.nome}</span>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={380}>
            <ComposedChart data={dadosEvolucaoFiltrados} margin={{ top: 10, right: 16, left: 8, bottom: 10 }}>
              <defs>
                {PARTES.map(p => (
                  <linearGradient key={p.chave} id={`grad-${p.chave}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={p.cor} stopOpacity={0.55} />
                    <stop offset="100%" stopColor={p.cor} stopOpacity={0.12} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid {...GRELHA} />
              <XAxis dataKey="label" {...EIXO} tick={<TickMes />} interval={0} height={40} />
              <YAxis {...EIXO} tickFormatter={formatarEurosEixo} width={84} />
              <Tooltip content={<TooltipGrafico />} cursor={{ stroke: 'var(--accent-linha)', strokeDasharray: '3 3' }} />
              {PARTES.map(p => (
                <Area
                  key={p.chave}
                  dataKey={p.chave}
                  name={p.nome}
                  type="monotone"
                  stackId="patrimonio"
                  stroke={p.cor}
                  strokeWidth={1.5}
                  fill={`url(#grad-${p.chave})`}
                  activeDot={{ r: 3 }}
                />
              ))}
              <Line dataKey="total" name="Total" type="monotone" stroke="var(--accent)" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}

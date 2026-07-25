import { useState, useEffect } from "react";
import { getContas, getSaldoConta } from "../api/contas";
import { useAtivos } from "../hooks/useAtivos";
import "./Patrimonio.css";
import { formatarEuros } from '../utils/formatacao';
import { obterEvolucao } from "../api/patrimonio";
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid
} from "recharts";

export default function Patrimonio() {
  const { ativos, resumos } = useAtivos();
  const [contas, setContas] = useState([]);

  useEffect(() => {
    carregarContas();
  }, []);

  const [evolucao, setEvolucao] = useState([]);

  useEffect(() => {
    obterEvolucao().then(res => setEvolucao(res.data));
  }, []);

  async function carregarContas() {
    const resContas = await getContas(false);
    const contasComSaldo = await Promise.all(
      resContas.data.map(async (c) => {
        const res = await getSaldoConta(c.id);
        return { ...c, saldo_atual: res.data.saldo_atual };
      })
    );
    setContas(contasComSaldo);
  }

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
  const totalMaisValia = totalInvestimentos + totalCusto;
  const pctMaisValia = totalCusto !== 0 ? (totalMaisValia / Math.abs(totalCusto)) * 100 : null;

  const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

  function labelMesEvolucao(dataISO) {
    const [ano, mes] = dataISO.split('-');
    return `${MESES[parseInt(mes) - 1]} ${ano}`;
  }

  const dadosEvolucao = evolucao.map(p => ({
    ...p,
    label: labelMesEvolucao(p.data),
  }));

  return (
    <div className="patrimonio-page">
      <div className="patrimonio-header">
        <h1>Património</h1>
      </div>

      {/* CARTÕES DE TOPO */}
      <div className="cartoes">
        {/* Património total */}
        <div className="cartao">
          <span className="cartao-titulo">Património</span>
          <span className="cartao-valor">{formatarEuros(totalPatrimonio)}</span>
          <div className="cartao-breakdown">
              <div className="cartao-breakdown-linha">
                  <span className="cartao-breakdown-label">Liquidez</span>
                  <span className="cartao-breakdown-valor">{formatarEuros(totalLiquidez)}</span>
              </div>
              <div className="cartao-breakdown-linha">
                  <span className="cartao-breakdown-label">Investimentos</span>
                  <span className="cartao-breakdown-valor">{formatarEuros(totalInvestimentos)}</span>
              </div>
              <div className="cartao-breakdown-linha">
                  <span className="cartao-breakdown-label">Bens</span>
                  <span className="cartao-breakdown-valor">{formatarEuros(totalBens)}</span>
              </div>
          </div>
        </div>

        {/* Liquidez */}
        <div className="cartao">
          <span className="cartao-titulo">Liquidez</span>
          <span className="cartao-valor">{formatarEuros(totalLiquidez)}</span>
          <div className="cartao-breakdown">
            {contas.length === 0 && (
              <span className="cartao-breakdown-label">Nenhuma conta activa</span>
            )}
            {contas.map((c) => (
              <div key={c.id} className="cartao-breakdown-linha">
                <span className="cartao-breakdown-label">{c.nome}</span>
                <span className="cartao-breakdown-valor">
                  {formatarEuros(c.saldo_atual)}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Investimentos */}
        <div className="cartao">
          <span className="cartao-titulo">Investimentos</span>
          <span className="cartao-valor">{formatarEuros(totalInvestimentos)}</span>
          <div className="cartao-breakdown">
            {ativosInvestimento.length === 0 && (
              <span className="cartao-breakdown-label">Nenhum ativo</span>
            )}
            {ativosInvestimento.map((a) => {
              const r = resumos[a.id];
              const valor = r?.valor_atual ?? r?.custo_total ?? 0;
              const pct = totalInvestimentos > 0 ? (valor / totalInvestimentos) * 100 : 0;
              return (
                <div key={a.id} className="cartao-breakdown-linha">
                  <span className="cartao-breakdown-label">{a.nome}</span>
                  <span className="cartao-breakdown-valor">{pct.toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Valorização */}
        <div className="cartao">
          <span className="cartao-titulo">Resultados</span>
          <div className="cartao-valor-linha">
            <span className={`cartao-valor ${totalMaisValia >= 0 ? "valor-positivo" : "valor-negativo"}`}>
              {formatarEuros(totalMaisValia)}
            </span>
            {pctMaisValia !== null && (
              <span className={`cartao-subvalor ${totalMaisValia >= 0 ? "valor-positivo" : "valor-negativo"}`}>
                {pctMaisValia >= 0 ? "+" : ""}{pctMaisValia.toFixed(2)}%
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
              return (
                <div key={a.id} className="cartao-breakdown-linha">
                  <span className="cartao-breakdown-label">{a.nome}</span>
                  {pct !== null ? (
                    <span className={`cartao-breakdown-valor ${pct >= 0 ? "valor-positivo" : "valor-negativo"}`}>
                      {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
                    </span>
                  ) : (
                    <span className="cartao-breakdown-valor">—</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      {/* EVOLUÇÃO DO PATRIMÓNIO */}
      <section className="secao">
        <h2>Evolução do património</h2>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={dadosEvolucao} margin={{ top: 10, right: 40, left: 20, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="label" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} angle={-45} textAnchor="end" />
            <YAxis tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} tickFormatter={v => `${v} €`} />
            <Tooltip
              contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}
              labelStyle={{ color: 'var(--text-primary)' }}
              formatter={(v) => formatarEuros(v)}
            />
            <Legend wrapperStyle={{ color: 'var(--text-secondary)', paddingTop: '2rem' }} />
            <Line dataKey="total" name="Total" type="monotone" stroke="var(--text-primary)" strokeWidth={2} dot={false} />
            <Line dataKey="liquidez" name="Liquidez" type="monotone" stroke="var(--accent)" strokeWidth={2} dot={false} />
            <Line dataKey="investimentos" name="Investimentos" type="monotone" stroke="var(--success)" strokeWidth={2} dot={false} />
            <Line dataKey="ativos_fisicos" name="Ativos físicos" type="monotone" stroke="#a78bfa" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}
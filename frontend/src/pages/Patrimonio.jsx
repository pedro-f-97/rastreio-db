import { useState, useEffect } from "react";
import { getPendentes, getAtivos, criarAtivo, criarMovimento, registarPreco, getMovimentos, getResumoAtivo, eliminarMovimento, eliminarAtivo } from "../api/patrimonio";
import { getContas, getSaldoConta } from "../api/contas";
import "./Patrimonio.css";
import { formatarEuros } from '../utils/formatacao';

const TIPOS_ATIVO = ["etf", "crypto", "veiculo", "imovel", "outro"];
const LABELS_TIPO = { etf: "ETF", crypto: "Crypto", veiculo: "Veículo", imovel: "Imóvel", outro: "Outro" };
const TIPOS_COM_UNIDADES = ["etf", "crypto"];

const estadoModalInicial = {
  aberto: false,
  transacao: null,
  passo: 1,
  tipoAtivo: "",
  ativoExistenteId: "",
  simbolo: "",
  nomeAtivo: "",
  tipoMovimento: "compra",
  contabilizacao: "",
  quantidade: "",
  comissao: "",
  valorTotal: "",
};

export default function Patrimonio() {
  const [pendentes, setPendentes] = useState([]);
  const [ativos, setAtivos] = useState([]);
  const [contas, setContas] = useState([]);
  const [seccoesExpandidas, setSeccoesExpandidas] = useState({});
  const [expandidos, setExpandidos] = useState({});
  const [modal, setModal] = useState(estadoModalInicial);
  const [erro, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalPreco, setModalPreco] = useState({ aberto: false, ativo: null, data: new Date().toISOString().split('T')[0], preco: '' });
  const [resumos, setResumos] = useState({});

  useEffect(() => {
    carregarDados();
  }, []);

  async function carregarDados() {
    const [resPendentes, resAtivos, resContas] = await Promise.all([
      getPendentes(),
      getAtivos(),
      getContas(false),
    ]);
    setPendentes(resPendentes.data);
    setAtivos(resAtivos.data);

    const contasComSaldo = await Promise.all(
      resContas.data.map(async (c) => {
        const res = await getSaldoConta(c.id);
        return { ...c, saldo_atual: res.data.saldo_atual };
      })
    );
    setContas(contasComSaldo);

    const resumosNovos = {};
    await Promise.all(
      resAtivos.data.map(async (a) => {
        const res = await getResumoAtivo(a.id);
        resumosNovos[a.id] = res.data;
      })
    );
    setResumos(resumosNovos);
  }

  function abrirModal(transacao) {
    setModal({ ...estadoModalInicial, aberto: true, transacao });
    setErro("");
  }

  function fecharModal() {
    setModal(estadoModalInicial);
    setErro("");
  }

  function toggleExpandido(ativoId) {
    setExpandidos((prev) => ({ ...prev, [ativoId]: !prev[ativoId] }));
  }

  function toggleSeccao(tipo) {
    setSeccoesExpandidas((prev) => ({ ...prev, [tipo]: !prev[tipo] }));
  }

  async function submeterModal() {
    setErro("");
    setLoading(true);
    try {
      const { transacao, tipoAtivo, simbolo, nomeAtivo, tipoMovimento, quantidade, comissao, valorTotal } = modal;
      const comUnidades = TIPOS_COM_UNIDADES.includes(tipoAtivo);
      const precisaContabilizacao = !modal.ativoExistenteId;

      if (!tipoAtivo) { setErro("Selecciona o tipo de ativo."); setLoading(false); return; }
      if (!modal.ativoExistenteId && !nomeAtivo.trim()) { setErro("Nome do ativo obrigatório."); setLoading(false); return; }
      if (comUnidades && (!quantidade || !valorTotal)) { setErro("Quantidade e total pago obrigatórios."); setLoading(false); return; }
      if (!comUnidades && !valorTotal) { setErro("Valor total obrigatório."); setLoading(false); return; }
      if (precisaContabilizacao && !modal.contabilizacao) { setErro("Selecciona a contabilização."); setLoading(false); return; }

      let ativo = null;
      if (modal.ativoExistenteId) {
        ativo = ativos.find((a) => a.id === parseInt(modal.ativoExistenteId));
      }
      if (!ativo) {
        const res = await criarAtivo({
          nome: nomeAtivo.trim(),
          tipo: tipoAtivo,
          simbolo: comUnidades && simbolo.trim() ? simbolo.trim().toUpperCase() : null,
          moeda: "EUR",
          contabilizacao: modal.contabilizacao,
        });
        ativo = res.data;
      }

      let valorFinal;
      let precoUnitarioCalculado;
      const sinal = tipoMovimento === "compra" ? -1 : 1;

      if (comUnidades) {
        const q = parseFloat(quantidade);
        const totalNormalizado = sinal * Math.abs(parseFloat(valorTotal));
        const comissaoNormalizada = -Math.abs(parseFloat(comissao || 0));
        valorFinal = totalNormalizado + comissaoNormalizada;
        precoUnitarioCalculado = Math.abs(parseFloat(valorTotal)) / q;
      } else {
        valorFinal = sinal * Math.abs(parseFloat(valorTotal));
        precoUnitarioCalculado = null;
      }

      await criarMovimento({
        ativo_id: ativo.id,
        transacao_id: transacao.id,
        tipo_movimento: tipoMovimento,
        data: transacao.data,
        quantidade: comUnidades ? parseFloat(quantidade) : null,
        preco_unitario: precoUnitarioCalculado,
        comissao: comUnidades ? parseFloat(comissao || 0) : null,
        valor_total: valorFinal,
      });

      fecharModal();
      await carregarDados();
    } catch (e) {
      setErro(e.response?.data?.detail || "Erro ao guardar.");
    } finally {
      setLoading(false);
    }
  }

  const ativosPorTipo = TIPOS_ATIVO.reduce((acc, tipo) => {
    acc[tipo] = ativos.filter((a) => a.tipo === tipo);
    return acc;
  }, {});

  function abrirModalPreco(ativo) {
    setModalPreco({ aberto: true, ativo, data: new Date().toISOString().split('T')[0], preco: '' });
    setErro("");
  }

  function fecharModalPreco() {
    setModalPreco({ aberto: false, ativo: null, data: '', preco: '' });
    setErro("");
  }

  async function submeterPreco() {
    if (!modalPreco.preco) { setErro("Preço obrigatório."); return; }
    setLoading(true);
    try {
      await registarPreco({
        ativo_id: modalPreco.ativo.id,
        data: modalPreco.data,
        preco: parseFloat(modalPreco.preco),
      });
      fecharModalPreco();
      await carregarDados();
    } catch (e) {
      setErro(e.response?.data?.detail || "Erro ao guardar preço.");
    } finally {
      setLoading(false);
    }
  }

  async function handleEliminarAtivo(ativo) {
    const temMovimentos = resumos[ativo.id]?.quantidade !== undefined &&
      (await getMovimentos(ativo.id)).data.length > 0;
    if (temMovimentos) {
      if (!window.confirm(`Apagar o ativo "${ativo.nome}" vai eliminar todos os movimentos associados. Tem a certeza?`)) return;
    }
    await eliminarAtivo(ativo.id);
    await carregarDados();
  }

  // --- Totais ---
  const totalLiquidez = contas.reduce((acc, c) => acc + (c.saldo_atual ?? 0), 0);
  const totalPatrimonioAtivos = Object.values(resumos).reduce((acc, r) => acc + (r.valor_atual ?? 0), 0);
  const totalPatrimonio = totalLiquidez + totalPatrimonioAtivos;

  const ativosInvestimento = ativos.filter((a) => a.contabilizacao === "investimento");
  const totalInvestimentos = ativosInvestimento.reduce((acc, a) => {
    const r = resumos[a.id];
    return acc + (r?.valor_atual ?? r?.custo_total ?? 0);
  }, 0);
  const totalCusto = ativosInvestimento.reduce((acc, a) => acc + (resumos[a.id]?.custo_total ?? 0), 0);
  const totalMaisValia = totalInvestimentos + totalCusto;
  const pctMaisValia = totalCusto !== 0 ? (totalMaisValia / Math.abs(totalCusto)) * 100 : null;

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

      {/* PENDENTES */}
      {pendentes.length > 0 && (
        <section className="secao">
          <h2 className="secao-titulo">Pendentes <span className="badge-pendentes">{pendentes.length}</span></h2>
          <table className="tabela-patrimonio">
            <thead>
              <tr>
                <th>Data</th>
                <th>Descrição</th>
                <th className="col-valor">Valor</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {pendentes.map((t) => (
                <tr key={t.id}>
                  <td className="col-mono">{t.data}</td>
                  <td>{t.descricao}</td>
                  <td className={`col-valor col-mono ${t.valor < 0 ? "valor-negativo" : "valor-positivo"}`}>
                    {formatarEuros(t.valor)}
                  </td>
                  <td>
                    <button className="btn-secundario" onClick={() => abrirModal(t)}>Tratar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* ATIVOS POR TIPO */}
      {TIPOS_ATIVO.map((tipo) => {
        const lista = ativosPorTipo[tipo];
        if (lista.length === 0) return null;
        const expandida = seccoesExpandidas[tipo] ?? false;
        return (
          <div key={tipo} className={`secao-ativo ${expandida ? "secao-ativo-expandida" : ""}`}>
            <button className="secao-titulo-colapsavel" onClick={() => toggleSeccao(tipo)}>
              <span>{LABELS_TIPO[tipo]}</span>
              <span className="secao-chevron">{expandida ? "▲" : "▼"}</span>
            </button>
            {expandida && (
              <table className="tabela-patrimonio">
                <colgroup>
                  <col style={{ width: '22%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '13%' }} />
                  <col style={{ width: '18%' }} />
                  <col style={{ width: '13%' }} />
                  <col style={{ width: '14%' }} />
                </colgroup>
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Identificador</th>
                    <th className="col-valor">Quantidade</th>
                    <th className="col-valor">Custo total</th>
                    <th className="col-valor">Valor actual</th>
                    <th className="col-valor">+/− valia</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {lista.map((ativo) => {
                    const r = resumos[ativo.id];
                    const mmv = r?.mais_menos_valia;
                    const custo = r?.custo_total;
                    const pctAtivo = custo && custo !== 0 ? (mmv / Math.abs(custo)) * 100 : null;
                    return (
                      <>
                        <tr key={ativo.id}>
                          <td>
                            {ativo.nome}
                            {ativo.isin && (
                              <span className="tooltip-isin" title={`ISIN: ${ativo.isin}`}>ⓘ</span>
                            )}
                          </td>
                          <td className="col-mono">
                            {ativo.simbolo ? (
                              <span className="tooltip-simbolo" title={ativo.simbolo}>
                                {ativo.simbolo}
                              </span>
                            ) : "—"}
                          </td>
                          <td className="col-valor col-mono">
                            {r ? (TIPOS_COM_UNIDADES.includes(ativo.tipo) ? r.quantidade : "—") : "—"}
                          </td>
                          <td className="col-valor col-mono">
                            {r ? formatarEuros(r.custo_total) : "—"}
                          </td>
                          <td className="col-valor col-mono">
                            {r?.valor_atual != null ? (
                              <div className="celula-valor-data">
                                <span>{formatarEuros(r.valor_atual)}</span>
                                {r.data_preco && (
                                  <span className="data-preco">{r.data_preco}</span>
                                )}
                              </div>
                            ) : "—"}
                          </td>
                          <td className={`col-valor col-mono ${mmv != null ? (mmv >= 0 ? "valor-positivo" : "valor-negativo") : ""}`}>
                            {mmv != null ? (
                              <div className="celula-valor-data">
                                <span>{formatarEuros(mmv)}</span>
                                {pctAtivo !== null && (
                                  <span className="data-preco">
                                    {pctAtivo >= 0 ? "+" : ""}{pctAtivo.toFixed(2)}%
                                  </span>
                                )}
                              </div>
                            ) : "—"}
                          </td>
                          <td>
                            <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                              <button className="btn-ghost" onClick={() => toggleExpandido(ativo.id)}>
                                <span className="seta-expansao">{expandidos[ativo.id] ? "▲" : "▼"}</span>
                                {expandidos[ativo.id] ? " Fechar" : " Movimentos"}
                              </button>
                              <button className="btn-ghost" onClick={() => abrirModalPreco(ativo)}>
                                ◎ Preço
                              </button>
                              <button className="btn-ghost" onClick={() => handleEliminarAtivo(ativo)}>
                                🧹
                              </button>
                            </div>
                          </td>
                        </tr>
                        {expandidos[ativo.id] && (
                          <tr key={`exp-${ativo.id}`} className="linha-movimentos-container">
                            <td colSpan={7} className="celula-movimentos">
                              <MovimentosAtivo ativoId={ativo.id} onEliminar={carregarDados} />
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        );
      })}

      {pendentes.length === 0 && ativos.length === 0 && contas.length === 0 && (
        <p className="estado-vazio">Sem dados de património.</p>
      )}

      {/* MODAL TRATAR PENDENTE */}
      {modal.aberto && (
        <div className="modal-overlay" onClick={fecharModal}>
          <div className="modal modal-patrimonio" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-titulo">Tratar pendente</h3>
            <p className="modal-subtitulo">{modal.transacao.descricao} · {modal.transacao.data} · {formatarEuros(modal.transacao.valor)}</p>

            {modal.passo === 1 && (
              <>
                <p className="label">Tipo de ativo</p>
                <div className="grid-tipos">
                  {TIPOS_ATIVO.map((t) => (
                    <button
                      key={t}
                      className={`btn-tipo ${modal.tipoAtivo === t ? "ativo" : ""}`}
                      onClick={() => setModal((m) => ({ ...m, tipoAtivo: t, passo: 2 }))}
                    >
                      {LABELS_TIPO[t]}
                    </button>
                  ))}
                </div>
              </>
            )}

            {modal.passo === 2 && (
              <>
                {TIPOS_COM_UNIDADES.includes(modal.tipoAtivo) ? (
                  <>
                    {(() => {
                      const ativosTipo = ativos.filter((a) => a.tipo === modal.tipoAtivo);
                      return ativosTipo.length > 0 ? (
                        <label className="label">Ativo
                          <select className="input" value={modal.ativoExistenteId} onChange={(e) => setModal((m) => ({ ...m, ativoExistenteId: e.target.value, nomeAtivo: "", simbolo: "" }))}>
                            <option value="">— Criar novo —</option>
                            {ativosTipo.map((a) => (
                              <option key={a.id} value={a.id}>{a.nome}{a.simbolo ? ` (${a.simbolo})` : ""}</option>
                            ))}
                          </select>
                        </label>
                      ) : null;
                    })()}
                    {!modal.ativoExistenteId && (
                      <>
                        <label className="label">Identificador (ex: VWCE)
                          <input className="input" value={modal.simbolo} onChange={(e) => setModal((m) => ({ ...m, simbolo: e.target.value }))} />
                        </label>
                        <label className="label">Nome do ativo
                          <input className="input" value={modal.nomeAtivo} onChange={(e) => setModal((m) => ({ ...m, nomeAtivo: e.target.value }))} />
                        </label>
                      </>
                    )}
                    <label className="label">Tipo de movimento
                      <select className="input" value={modal.tipoMovimento} onChange={(e) => setModal((m) => ({ ...m, tipoMovimento: e.target.value }))}>
                        <option value="compra">Compra</option>
                        <option value="venda">Venda</option>
                        <option value="dividendo">Dividendo</option>
                      </select>
                    </label>
                    <label className="label">Quantidade
                      <input className="input" type="number" value={modal.quantidade} onChange={(e) => setModal((m) => ({ ...m, quantidade: e.target.value }))} />
                    </label>
                    <label className="label">Total da operação (sem comissão) (€)
                      <input className="input" type="number" value={modal.valorTotal} onChange={(e) => setModal((m) => ({ ...m, valorTotal: e.target.value }))} />
                    </label>
                    <label className="label">Comissão (€)
                      <input className="input" type="number" value={modal.comissao} onChange={(e) => setModal((m) => ({ ...m, comissao: e.target.value }))} />
                    </label>
                  </>
                ) : (
                  <>
                    {(() => {
                      const ativosTipo = ativos.filter((a) => a.tipo === modal.tipoAtivo);
                      return ativosTipo.length > 0 ? (
                        <label className="label">Ativo
                          <select className="input" value={modal.ativoExistenteId} onChange={(e) => setModal((m) => ({ ...m, ativoExistenteId: e.target.value, nomeAtivo: "" }))}>
                            <option value="">— Criar novo —</option>
                            {ativosTipo.map((a) => (
                              <option key={a.id} value={a.id}>{a.nome}</option>
                            ))}
                          </select>
                        </label>
                      ) : null;
                    })()}
                    {!modal.ativoExistenteId && (
                      <label className="label">Nome do ativo
                        <input className="input" value={modal.nomeAtivo} onChange={(e) => setModal((m) => ({ ...m, nomeAtivo: e.target.value }))} />
                      </label>
                    )}
                    <label className="label">Tipo de movimento
                      <select className="input" value={modal.tipoMovimento} onChange={(e) => setModal((m) => ({ ...m, tipoMovimento: e.target.value }))}>
                        <option value="compra">Compra</option>
                        <option value="venda">Venda</option>
                      </select>
                    </label>
                    <label className="label">Total da operação (sem comissão) (€)
                      <input className="input" type="number" value={modal.valorTotal} onChange={(e) => setModal((m) => ({ ...m, valorTotal: e.target.value }))} />
                    </label>
                  </>
                )}
                {!modal.ativoExistenteId && (
                  <label className="label">Contabilização
                    <select
                      className="input"
                      value={modal.contabilizacao}
                      onChange={(e) => setModal((m) => ({ ...m, contabilizacao: e.target.value }))}
                    >
                      <option value="">— Seleccionar —</option>
                      <option value="investimento">Investimento</option>
                      <option value="patrimonio">Património</option>
                    </select>
                  </label>
                )}
                {erro && <p className="erro">{erro}</p>}

                <div className="modal-acoes">
                  <button className="btn-ghost" onClick={() => setModal((m) => ({ ...m, passo: 1 }))}>← Voltar</button>
                  <button className="btn-primario" onClick={submeterModal} disabled={loading}>
                    {loading ? "A guardar…" : "Guardar"}
                  </button>
                </div>
              </>
            )}

            <button className="modal-fechar" onClick={fecharModal}>✕</button>
          </div>
        </div>
      )}

      {/* MODAL PREÇO */}
      {modalPreco.aberto && (
        <div className="modal-overlay" onClick={fecharModalPreco}>
          <div className="modal modal-patrimonio" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-titulo">Actualizar preço</h3>
            <p className="modal-subtitulo">{modalPreco.ativo.nome} {modalPreco.ativo.simbolo ? `· ${modalPreco.ativo.simbolo}` : ''}</p>

            <label className="label">Data
              <input className="input" type="date" value={modalPreco.data} onChange={(e) => setModalPreco((m) => ({ ...m, data: e.target.value }))} />
            </label>
            <label className="label">Preço unitário (€)
              <input className="input" type="number" step="0.0001" value={modalPreco.preco} onChange={(e) => setModalPreco((m) => ({ ...m, preco: e.target.value }))} />
            </label>

            {erro && <p className="erro">{erro}</p>}

            <div className="modal-acoes">
              <button className="btn-ghost" onClick={fecharModalPreco}>Cancelar</button>
              <button className="btn-primario" onClick={submeterPreco} disabled={loading}>
                {loading ? "A guardar…" : "Guardar"}
              </button>
            </div>

            <button className="modal-fechar" onClick={fecharModalPreco}>✕</button>
          </div>
        </div>
      )}
    </div>
  );
}

function MovimentosAtivo({ ativoId, onEliminar }) {
  const [movimentos, setMovimentos] = useState([]);

  useEffect(() => {
    getMovimentos(ativoId).then((r) => setMovimentos(r.data));
  }, [ativoId]);

  async function handleEliminar(movimentoId) {
    await eliminarMovimento(movimentoId);
    const res = await getMovimentos(ativoId);
    setMovimentos(res.data);
    onEliminar();
  }

  if (movimentos.length === 0) return <p className="estado-vazio">Sem movimentos registados.</p>;

  return (
    <table className="tabela-patrimonio tabela-aninhada">
      <thead>
        <tr>
          <th>Data</th>
          <th>Tipo</th>
          <th>Quantidade</th>
          <th>Preço unit.</th>
          <th>Comissão</th>
          <th className="col-valor">Valor total</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {movimentos.map((m) => (
          <tr key={m.id}>
            <td className="col-mono">{m.data}</td>
            <td>{m.tipo_movimento}</td>
            <td className="col-mono">{m.quantidade ?? "—"}</td>
            <td className="col-mono">{m.preco_unitario != null ? `${m.preco_unitario.toFixed(4)} €` : "—"}</td>
            <td className="col-mono">{m.comissao != null ? `${m.comissao.toFixed(2)} €` : "—"}</td>
            <td className="col-valor col-mono">{formatarEuros(m.valor_total)}</td>
            <td><button className="btn-ghost" onClick={() => handleEliminar(m.id)}>🧹</button></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
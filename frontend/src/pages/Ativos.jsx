import { useState, useEffect, Fragment } from "react";
import { getPendentes, criarAtivo, editarAtivo, criarMovimento, registarPreco, getMovimentos, eliminarMovimento, eliminarAtivo, getPrecos, eliminarPreco } from "../api/patrimonio";
import { useAtivos } from "../hooks/useAtivos";
import "./Ativos.css";
import { classeValor, formatarEuros, formatarPercentagem, formatarQuantidade, prefixoSinal } from '../utils/formatacao';
import "../componentes.css";
import CabecalhoPagina from "../components/CabecalhoPagina";
import Icone from "../components/Icone";

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

export default function Ativos({ onDadosAlterados }) {
  const { ativos, resumos, tiposAtivo, recarregar } = useAtivos();
  const [pendentes, setPendentes] = useState([]);
  const [seccoesExpandidas, setSeccoesExpandidas] = useState({});
  const [expandidos, setExpandidos] = useState({});
  const [modal, setModal] = useState(estadoModalInicial);
  const [erro, setErro] = useState("");
  const [loading, setLoading] = useState(false);
  const [modalPreco, setModalPreco] = useState({ aberto: false, ativo: null, data: new Date().toISOString().split('T')[0], preco: '', porTotal: false });
  const [menuAbertoId, setMenuAbertoId] = useState(null);
  const [editando, setEditando] = useState({}); // { id, nome, simbolo }

  useEffect(() => {
    carregarPendentes();
  }, []);

  useEffect(() => {
    if (menuAbertoId === null) return;
    function fecharAoClicarFora(e) {
      if (!e.target.closest(".menu-acoes")) {
        setMenuAbertoId(null);
      }
    }
    document.addEventListener("mousedown", fecharAoClicarFora);
    return () => document.removeEventListener("mousedown", fecharAoClicarFora);
  }, [menuAbertoId]);

  async function carregarPendentes() {
    const res = await getPendentes();
    setPendentes(res.data);
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

  function iniciarEdicao(ativo, e) {
    e.stopPropagation();
    setEditando({ id: ativo.id, nome: ativo.nome, simbolo: ativo.simbolo || "" });
    setMenuAbertoId(null);
  }

  function cancelarEdicao(e) {
    e.stopPropagation();
    setEditando({});
    setErro("");
  }

  async function confirmarEdicao(e) {
    e.stopPropagation();
    if (!editando.nome.trim()) { setErro("Nome obrigatório."); return; }
    setErro("");
    try {
      await editarAtivo(editando.id, {
        nome: editando.nome.trim(),
        simbolo: editando.simbolo.trim() ? editando.simbolo.trim().toUpperCase() : null,
      });
      setEditando({});
      await recarregar();
    } catch (err) {
      setErro(err.response?.data?.detail || "Erro ao editar ativo.");
    }
  }

  async function submeterModal() {
    setErro("");
    setLoading(true);
    try {
      const { transacao, tipoAtivo, simbolo, nomeAtivo, tipoMovimento, quantidade, comissao, valorTotal } = modal;
      const tipoSelecionado = tiposAtivo.find((t) => t.id === tipoAtivo);
      const comUnidades = tipoSelecionado?.tem_unidades ?? false;
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
          tipo_id: tipoAtivo,
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
      await carregarPendentes();
      await recarregar();
      onDadosAlterados?.();
    } catch (e) {
      setErro(e.response?.data?.detail || "Erro ao guardar.");
    } finally {
      setLoading(false);
    }
  }

  const ativosPorTipo = tiposAtivo.reduce((acc, tipo) => {
    acc[tipo.id] = ativos.filter((a) => a.tipo.id === tipo.id);
    return acc;
  }, {});

  // Data local em AAAA-MM-DD, comparável com `data_preco`
  const hoje = new Date().toLocaleDateString("sv-SE");

  function calcularResumoTipo(listaAtivos, resumos) {
    let custoTotal = 0;
    let valorAtualTotal = 0;
    let resultadoTotal = 0;
    let custoConsiderado = 0;
    let temValorAtual = false;

    listaAtivos.forEach((ativo) => {
      const r = resumos[ativo.id];
      const custo = r?.custo_total ?? 0;
      custoTotal += custo;
      if (r?.valor_atual != null) {
        valorAtualTotal += r.valor_atual;
        resultadoTotal += r.mais_menos_valia ?? 0;
        custoConsiderado += custo;
        temValorAtual = true;
      }
    });

    const pct = temValorAtual && custoConsiderado !== 0
      ? (resultadoTotal / Math.abs(custoConsiderado)) * 100
      : null;

    return {
      custoTotal,
      valorAtualTotal: temValorAtual ? valorAtualTotal : null,
      resultadoTotal: temValorAtual ? resultadoTotal : null,
      pct,
    };
  }

  function abrirModalPreco(ativo) {
    setModalPreco({ aberto: true, ativo, data: new Date().toISOString().split('T')[0], preco: '', porTotal: false });
    setErro("");
  }

  function fecharModalPreco() {
    setModalPreco({ aberto: false, ativo: null, data: '', preco: '', porTotal: false });
    setErro("");
  }

  async function submeterPreco() {
    if (!modalPreco.preco) { setErro(modalPreco.porTotal ? "Valor total obrigatório." : "Preço obrigatório."); return; }
    setLoading(true);
    try {
      // Pelo valor total, o backend divide-o pelas unidades que havia na data
      await registarPreco({
        ativo_id: modalPreco.ativo.id,
        data: modalPreco.data,
        [modalPreco.porTotal ? "valor_total" : "preco"]: parseFloat(modalPreco.preco),
      });
      fecharModalPreco();
      await recarregar();
    } catch (e) {
      setErro(e.response?.data?.detail || "Erro ao guardar preço.");
    } finally {
      setLoading(false);
    }
  }

  async function handleEliminarAtivo(ativo) {
    const temMovimentos = (await getMovimentos(ativo.id)).data.length > 0;
    if (temMovimentos) {
      if (!window.confirm(`Apagar o ativo "${ativo.nome}" vai eliminar todos os movimentos associados. Tem a certeza?`)) return;
    }
    await eliminarAtivo(ativo.id);
    await recarregar();
    onDadosAlterados?.();
  }

  async function aoEliminarMovimento() {
    await carregarPendentes();
    await recarregar();
    onDadosAlterados?.();
  }

  return (
    <div className="patrimonio-page">
      <CabecalhoPagina
        secao="03 · Análise"
        titulo="Ativos"
        descricao="Os investimentos e os bens, com o custo, o valor e o resultado. As compras e vendas por tratar ficam em cima."
      />

      {/* PENDENTES */}
      {pendentes.length > 0 && (
        <section className="secao pendentes">
          <div className="pendentes-cabecalho">
            <Icone nome="aviso" tamanho={18} />
            <h2 className="secao-titulo">Pendentes <span className="badge-pendentes">{pendentes.length}</span></h2>
            <span className="cartao-nota">Transações de subcategorias de património que ainda não são movimentos de um ativo.</span>
          </div>
          <div className="tabela-wrapper">
            <table className="tabela-base tabela-patrimonio">
              <thead>
                <tr>
                  <th style={{ width: '14%' }}>Data</th>
                  <th>Descrição</th>
                  <th className="col-valor" style={{ width: '18%' }}>Valor</th>
                  <th style={{ width: '12%' }}></th>
                </tr>
              </thead>
              <tbody>
                {pendentes.map((t) => (
                  <tr key={t.id}>
                    <td className="col-data">{t.data}</td>
                    <td>{t.descricao}</td>
                    <td className={`col-valor col-mono ${classeValor(t.valor)}`}>
                      {formatarEuros(t.valor)}
                    </td>
                    <td className="col-accoes">
                      <button className="btn-primario btn-pequeno" onClick={() => abrirModal(t)}>Tratar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ATIVOS POR TIPO */}
      {tiposAtivo.map((tipo) => {
          const lista = ativosPorTipo[tipo.id] || [];
          if (lista.length === 0) return null;
          const expandida = seccoesExpandidas[tipo.id] ?? false;
          const resumoTipo = calcularResumoTipo(lista, resumos);
          return (
            <div key={tipo.id} className={`secao-ativo ${expandida ? "secao-ativo-expandida" : ""}`}>
              <button className="secao-titulo-colapsavel" onClick={() => toggleSeccao(tipo.id)}>
                <div className="secao-titulo-grupo">
                  <span className="secao-titulo-nome">{tipo.nome}</span>
                  <span className="chip">{lista.length} {lista.length === 1 ? "ativo" : "ativos"}</span>
                </div>
                <div className="secao-titulo-grupo">
                  {resumoTipo.valorAtualTotal != null && (
                    <span className="secao-resumo">
                      <span className="secao-resumo-valor">{formatarEuros(resumoTipo.valorAtualTotal)}</span>
                      <span className={classeValor(resumoTipo.resultadoTotal)}>
                        {prefixoSinal(resumoTipo.resultadoTotal)}{formatarEuros(resumoTipo.resultadoTotal)}
                        {resumoTipo.pct != null && ` (${prefixoSinal(resumoTipo.pct)}${formatarPercentagem(resumoTipo.pct, 2)})`}
                      </span>
                    </span>
                  )}
                  <span className={`secao-chevron ${expandida ? "aberta" : ""}`}><Icone nome="baixo" /></span>
                </div>
              </button>
            {expandida && (
              <table className="tabela-base tabela-patrimonio tabela-ativos">
                {/* Nome, identificador, custo total, valor atual, resultado atual,
                    quantidade e ações. Sem espaços entre os <col>: o React avisa */}
                <colgroup>
                  <col style={{ width: '22%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '13%' }} />
                  <col style={{ width: '18%' }} />
                  <col style={{ width: '13%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '14%' }} />
                </colgroup>
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Identificador</th>
                    <th className="col-valor">Custo total</th>
                    <th className="col-valor">Valor actual</th>
                    <th className="col-valor">Resultado actual</th>
                    <th className="col-valor">Quantidade</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {lista.map((ativo) => {
                    const r = resumos[ativo.id];
                    const mmv = r?.mais_menos_valia;
                    const custo = r?.custo_total;
                    const pctAtivo = custo && custo !== 0 ? (mmv / Math.abs(custo)) * 100 : null;
                    // Ainda detido e sem preço: a mais-valia não se sabe, não é zero
                    const semPreco = r != null && r.preco_atual == null &&
                      (ativo.tipo.tem_unidades ? r.quantidade > 0 : r.custo_total !== 0);
                    return (
                      <Fragment key={ativo.id}>
                        <tr
                            className={`linha-clicavel ${expandidos[ativo.id] ? "linha-aberta" : ""}`}
                            onClick={() => toggleExpandido(ativo.id)}
                        >
                          <td>
                            {editando.id === ativo.id ? (
                              <input
                                className="input-inline"
                                autoFocus
                                value={editando.nome}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => setEditando((ed) => ({ ...ed, nome: e.target.value }))}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") confirmarEdicao(e);
                                  if (e.key === "Escape") cancelarEdicao(e);
                                }}
                              />
                            ) : (
                              <>
                                {ativo.nome}
                                {ativo.isin && (
                                  <span className="tooltip-isin" title={`ISIN: ${ativo.isin}`}><Icone nome="info" tamanho={13} /></span>
                                )}
                              </>
                            )}
                          </td>
                          <td className="col-mono">
                            {editando.id === ativo.id ? (
                              <input
                                className="input-inline"
                                value={editando.simbolo}
                                onClick={(e) => e.stopPropagation()}
                                onChange={(e) => setEditando((ed) => ({ ...ed, simbolo: e.target.value }))}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") confirmarEdicao(e);
                                  if (e.key === "Escape") cancelarEdicao(e);
                                }}
                              />
                            ) : ativo.simbolo ? (
                              <span className="tooltip-simbolo chip" title={ativo.simbolo}>{ativo.simbolo}</span>
                            ) : "—"}
                          </td>
                          <td className="col-valor col-mono">
                            {r ? formatarEuros(r.custo_total) : "—"}
                          </td>
                          <td className="col-valor col-mono">
                            {r?.valor_atual != null ? (
                              <div className="celula-valor-data">
                                <span>{formatarEuros(r.valor_atual)}</span>
                                {r.data_preco && (
                                  r.data_preco > hoje ? (
                                    <span className="data-preco" title="Preço com data futura: confirma se a data está certa.">⚠ {r.data_preco}</span>
                                  ) : (
                                    <span className="data-preco">{r.data_preco}</span>
                                  )
                                )}
                              </div>
                            ) : "—"}
                          </td>
                          <td className={`col-valor col-mono ${mmv != null && !semPreco ? classeValor(mmv) : ""}`}>
                            {semPreco ? (
                              <span className="data-preco" title="Sem preço registado: regista um preço para ver a mais-valia.">sem preço</span>
                            ) : mmv != null ? (
                              <div className="celula-valor-data">
                                <span>{formatarEuros(mmv)}</span>
                                {pctAtivo !== null && (
                                  <span className="data-preco">
                                    {prefixoSinal(pctAtivo)}{formatarPercentagem(pctAtivo, 2)}
                                  </span>
                                )}
                              </div>
                            ) : "—"}
                          </td>
                          <td className="col-valor col-mono">
                            {r ? (ativo.tipo.tem_unidades ? formatarQuantidade(r.quantidade) : "—") : "—"}
                          </td>
                          <td onClick={(e) => e.stopPropagation()}>
                            <div className="accoes">
                              {editando.id === ativo.id ? (
                                <>
                                  <button className="btn-confirmar" onClick={confirmarEdicao} title="Guardar"><Icone nome="confirmar" /></button>
                                  <button className="btn-cancelar" onClick={cancelarEdicao} title="Cancelar"><Icone nome="fechar" /></button>
                                </>
                              ) : (
                                <>
                                  <span className={`secao-chevron ${expandidos[ativo.id] ? "aberta" : ""}`}><Icone nome="baixo" tamanho={14} /></span>
                                  <div className="menu-acoes">
                                    <button
                                      className="btn-menu"
                                      title="Mais ações"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setMenuAbertoId(menuAbertoId === ativo.id ? null : ativo.id);
                                      }}
                                    >
                                      <Icone nome="menu" />
                                    </button>

                                    {menuAbertoId === ativo.id && (
                                      <div className="menu-dropdown">
                                        <button onClick={(e) => iniciarEdicao(ativo, e)}>
                                          Editar
                                        </button>
                                        <button
                                          onClick={() => {
                                            abrirModalPreco(ativo);
                                            setMenuAbertoId(null);
                                          }}
                                        >
                                          Atualizar preço
                                        </button>
                                        <button
                                          className="menu-item-perigo"
                                          onClick={() => {
                                            handleEliminarAtivo(ativo);
                                            setMenuAbertoId(null);
                                          }}
                                        >
                                          Eliminar ativo
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                        {expandidos[ativo.id] && (
                          <tr key={`exp-${ativo.id}`} className="linha-movimentos-container">
                            <td colSpan={7} className="celula-movimentos">
                              <div className="detalhe-ativo">
                                <div className="detalhe-ativo-bloco">
                                  <h4 className="detalhe-ativo-titulo">Movimentos</h4>
                                  <MovimentosAtivo ativoId={ativo.id} onEliminar={aoEliminarMovimento} />
                                </div>
                                <div className="detalhe-ativo-bloco">
                                  <h4 className="detalhe-ativo-titulo">Preços registados</h4>
                                  <PrecosAtivo ativoId={ativo.id} onEliminar={aoEliminarMovimento} />
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        );
      })}

      {pendentes.length === 0 && ativos.length === 0 && (
        <p className="estado-vazio">Sem dados de ativos.</p>
      )}

      {/* MODAL TRATAR PENDENTE */}
      {modal.aberto && (
        <div className="modal-overlay" onClick={fecharModal}>
          <div className="modal modal-patrimonio" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-titulo">Tratar pendente</h3>
            <p className="modal-subtitulo">{modal.transacao.descricao} · {modal.transacao.data} · {formatarEuros(modal.transacao.valor)}</p>

            {modal.passo === 1 && (
              <>
                <p className="label">Que tipo de ativo é?</p>
                <div className="grid-tipos">
                  {tiposAtivo.map((t) => (
                    <button
                      key={t.id}
                      className={`btn-tipo ${modal.tipoAtivo === t.id ? "ativo" : ""}`}
                      onClick={() => setModal((m) => ({ ...m, tipoAtivo: t.id, passo: 2 }))}
                    >
                      {t.nome}
                    </button>
                  ))}
                </div>
              </>
            )}

            {modal.passo === 2 && (
              <>
                {tiposAtivo.find((t) => t.id === modal.tipoAtivo)?.tem_unidades ? (
                  <>
                    {(() => {
                      const ativosTipo = ativos.filter((a) => a.tipo.id === modal.tipoAtivo);
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
                      const ativosTipo = ativos.filter((a) => a.tipo.id === modal.tipoAtivo);
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
                      <option value="patrimonio">Bens</option>
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

            <button className="modal-fechar" onClick={fecharModal} title="Fechar"><Icone nome="fechar" /></button>
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
              <input className="input" type="date" max={hoje} value={modalPreco.data} onChange={(e) => setModalPreco((m) => ({ ...m, data: e.target.value }))} />
            </label>
            {modalPreco.ativo.tipo.tem_unidades && (
              <label className="label">Actualizar por
                <select className="input" value={modalPreco.porTotal ? "total" : "unitario"} onChange={(e) => setModalPreco((m) => ({ ...m, porTotal: e.target.value === "total" }))}>
                  <option value="unitario">Preço unitário</option>
                  <option value="total">Valor total das unidades nesta data</option>
                </select>
              </label>
            )}
            <label className="label">{modalPreco.porTotal ? "Valor total" : "Preço unitário"}, em euros (€)
              <input className="input" type="number" step={modalPreco.porTotal ? "0.01" : "0.0001"} value={modalPreco.preco} onChange={(e) => setModalPreco((m) => ({ ...m, preco: e.target.value }))} />
            </label>

            {erro && <p className="erro">{erro}</p>}

            <div className="modal-acoes">
              <button className="btn-ghost" onClick={fecharModalPreco}>Cancelar</button>
              <button className="btn-primario" onClick={submeterPreco} disabled={loading}>
                {loading ? "A guardar…" : "Guardar"}
              </button>
            </div>

            <button className="modal-fechar" onClick={fecharModalPreco} title="Fechar"><Icone nome="fechar" /></button>
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
    try {
      await eliminarMovimento(movimentoId);
    } catch (e) {
      alert(e.response?.data?.detail || "Erro ao eliminar movimento.");
      return;
    }
    const res = await getMovimentos(ativoId);
    setMovimentos(res.data);
    onEliminar();
  }

  if (movimentos.length === 0) return <p className="estado-vazio">Sem movimentos registados.</p>;

  return (
    <table className="tabela-base tabela-patrimonio tabela-aninhada">
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
            <td><span className={`chip movimento-${m.tipo_movimento}`}>{m.tipo_movimento}</span></td>
            <td className="col-mono">{formatarQuantidade(m.quantidade)}</td>
            <td className="col-mono">{formatarEuros(m.preco_unitario, 4)}</td>
            <td className="col-mono">{formatarEuros(m.comissao)}</td>
            <td className="col-valor col-mono">{formatarEuros(m.valor_total)}</td>
            <td className="col-accoes"><button title="Eliminar registo" className="btn-icone perigo" onClick={() => handleEliminar(m.id)}><Icone nome="apagar" tamanho={14} /></button></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PrecosAtivo({ ativoId, onEliminar }) {
  const [precos, setPrecos] = useState([]);

  useEffect(() => {
    getPrecos(ativoId).then((r) => setPrecos(r.data));
  }, [ativoId]);

  async function handleEliminar(precoId) {
    try {
      await eliminarPreco(precoId);
    } catch (e) {
      alert(e.response?.data?.detail || "Erro ao eliminar preço.");
      return;
    }
    const res = await getPrecos(ativoId);
    setPrecos(res.data);
    onEliminar();
  }

  if (precos.length === 0) return <p className="estado-vazio">Sem preços registados.</p>;

  return (
    <table className="tabela-base tabela-patrimonio tabela-aninhada">
      <thead>
        <tr>
          <th>Data do preço</th>
          <th className="col-valor">Preço</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {precos.map((p) => (
          <tr key={p.id}>
            <td className="col-mono">{p.data}</td>
            <td className="col-valor col-mono">{formatarEuros(p.preco)}</td>
            <td className="col-accoes"><button title="Eliminar preço" className="btn-icone perigo" onClick={() => handleEliminar(p.id)}><Icone nome="apagar" tamanho={14} /></button></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

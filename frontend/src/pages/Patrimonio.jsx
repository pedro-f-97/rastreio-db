import { useState, useEffect } from "react";
import { getPendentes, getAtivos, criarAtivo, criarMovimento, registarPreco, getMovimentos, getResumoAtivo } from "../api/patrimonio";
import "./Patrimonio.css";

const TIPOS_ATIVO = ["etf", "crypto", "veiculo", "imovel", "outro"];
const LABELS_TIPO = { etf: "ETF", crypto: "Crypto", veiculo: "Veículo", imovel: "Imóvel", outro: "Outro" };
const TIPOS_COM_UNIDADES = ["etf", "crypto"];

const estadoModalInicial = {
  aberto: false,
  transacao: null,
  passo: 1,
  tipoAtivo: "",
  // campos comuns
  simbolo: "",
  nomeAtivo: "",
  tipoMovimento: "compra",
  // ETF/Crypto
  quantidade: "",
  precoUnitario: "",
  comissao: "",
  // Veículo/Imóvel/Outro
  valorTotal: "",
};

export default function Patrimonio() {
  const [pendentes, setPendentes] = useState([]);
  const [ativos, setAtivos] = useState([]);
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
    const [resPendentes, resAtivos] = await Promise.all([getPendentes(), getAtivos()]);
    setPendentes(resPendentes.data);
    setAtivos(resAtivos.data);

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
    setModal({ ...estadoModalInicial, aberto: true, transacao, valorTotal: String(Math.abs(transacao.valor)) });
    setErro("");
  }

  function fecharModal() {
    setModal(estadoModalInicial);
    setErro("");
  }

  function toggleExpandido(ativoId) {
    setExpandidos((prev) => ({ ...prev, [ativoId]: !prev[ativoId] }));
  }

  async function submeterModal() {
    setErro("");
    setLoading(true);
    try {
      const { transacao, tipoAtivo, simbolo, nomeAtivo, tipoMovimento, quantidade, precoUnitario, comissao, valorTotal } = modal;
      const comUnidades = TIPOS_COM_UNIDADES.includes(tipoAtivo);

      // Validação
      if (!tipoAtivo) { setErro("Selecciona o tipo de ativo."); setLoading(false); return; }
      if (!nomeAtivo.trim()) { setErro("Nome do ativo obrigatório."); setLoading(false); return; }
      if (comUnidades && (!quantidade || !precoUnitario)) { setErro("Quantidade e preço unitário obrigatórios."); setLoading(false); return; }
      if (!comUnidades && !valorTotal) { setErro("Valor total obrigatório."); setLoading(false); return; }

      // Resolve ativo — procura por símbolo ou cria novo
      let ativo = null;
      if (comUnidades && simbolo.trim()) {
        ativo = ativos.find((a) => a.simbolo?.toLowerCase() === simbolo.trim().toLowerCase());
      }
      if (!ativo) {
        const res = await criarAtivo({
          nome: nomeAtivo.trim(),
          tipo: tipoAtivo,
          simbolo: comUnidades && simbolo.trim() ? simbolo.trim().toUpperCase() : null,
          moeda: "EUR",
        });
        ativo = res.data;
      }

      // Calcula valor_total
      let valorFinal;
      if (comUnidades) {
        const q = parseFloat(quantidade);
        const p = parseFloat(precoUnitario);
        const c = parseFloat(comissao || 0);
        valorFinal = q * p + c;
      } else {
        valorFinal = parseFloat(valorTotal);
      }

      // Cria movimento
      await criarMovimento({
        ativo_id: ativo.id,
        transacao_id: transacao.id,
        tipo_movimento: tipoMovimento,
        data: transacao.data,
        quantidade: comUnidades ? parseFloat(quantidade) : null,
        preco_unitario: comUnidades ? parseFloat(precoUnitario) : null,
        comissao: comUnidades ? parseFloat(comissao || 0) : null,
        valor_total: valorFinal,
      });

      // Para veículo/imóvel/outro — regista também preço actual
      if (!comUnidades) {
        await registarPreco({
          ativo_id: ativo.id,
          data: transacao.data,
          preco: valorFinal,
        });
      }

      fecharModal();
      await carregarDados();
    } catch (e) {
      setErro(e.response?.data?.detail || "Erro ao guardar.");
    } finally {
      setLoading(false);
    }
  }

  // Agrupa ativos por tipo
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

  return (
    <div className="patrimonio-page">
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
                    {t.valor.toFixed(2)} €
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
        return (
          <section key={tipo} className="secao-patrimonio">
            <h2 className="secao-titulo">{LABELS_TIPO[tipo]}</h2>
            <table className="tabela-patrimonio">
              <colgroup>
                <col style={{ width: '25%' }} />
                <col style={{ width: '8%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '27%' }} />
              </colgroup>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Símbolo</th>
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
                  return (
                    <>
                      <tr key={ativo.id}>
                        <td>{ativo.nome}</td>
                        <td className="col-mono">{ativo.simbolo ?? "—"}</td>
                        <td className="col-valor col-mono">{r ? r.quantidade : "—"}</td>
                        <td className="col-valor col-mono">{r ? `${r.custo_total.toFixed(2)} €` : "—"}</td>
                        <td className="col-valor col-mono">{r?.valor_atual != null ? `${r.valor_atual.toFixed(2)} €` : "—"}</td>
                        <td className={`col-valor col-mono ${r?.mais_menos_valia != null ? (r.mais_menos_valia >= 0 ? "valor-positivo" : "valor-negativo") : ""}`}>
                          {r?.mais_menos_valia != null ? `${r.mais_menos_valia.toFixed(2)} €` : "—"}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 'var(--space-sm)' }}>
                            <button className="btn-ghost" onClick={() => toggleExpandido(ativo.id)}>
                              {expandidos[ativo.id] ? "▲ Fechar" : "▼ Movimentos"}
                            </button>
                            <button className="btn-ghost" onClick={() => abrirModalPreco(ativo)}>
                              ◎ Preço
                            </button>
                          </div>
                        </td>
                      </tr>
                      {expandidos[ativo.id] && (
                        <tr key={`exp-${ativo.id}`}>
                          <td colSpan={7}>
                            <MovimentosAtivo ativoId={ativo.id} />
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </section>
        );
      })}

      {pendentes.length === 0 && ativos.length === 0 && (
        <p className="estado-vazio">Sem dados de património. Marca subcategorias com "trata património" para começar.</p>
      )}

      {/* MODAL */}
      {modal.aberto && (
        <div className="modal-overlay" onClick={fecharModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-titulo">Tratar pendente</h3>
            <p className="modal-subtitulo">{modal.transacao.descricao} · {modal.transacao.data} · {modal.transacao.valor.toFixed(2)} €</p>

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
                    <label className="label">Símbolo (ex: VWCE)
                      <input className="input" value={modal.simbolo} onChange={(e) => setModal((m) => ({ ...m, simbolo: e.target.value }))} />
                    </label>
                    <label className="label">Nome do ativo
                      <input className="input" value={modal.nomeAtivo} onChange={(e) => setModal((m) => ({ ...m, nomeAtivo: e.target.value }))} />
                    </label>
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
                    <label className="label">Preço unitário (€)
                      <input className="input" type="number" value={modal.precoUnitario} onChange={(e) => setModal((m) => ({ ...m, precoUnitario: e.target.value }))} />
                    </label>
                    <label className="label">Comissão (€)
                      <input className="input" type="number" value={modal.comissao} onChange={(e) => setModal((m) => ({ ...m, comissao: e.target.value }))} />
                    </label>
                    {modal.quantidade && modal.precoUnitario && (
                      <p className="label">
                        Valor total: <strong>{(parseFloat(modal.quantidade) * parseFloat(modal.precoUnitario) + parseFloat(modal.comissao || 0)).toFixed(2)} €</strong>
                      </p>
                    )}
                  </>
                ) : (
                  <>
                    <label className="label">Nome do ativo
                      <input className="input" value={modal.nomeAtivo} onChange={(e) => setModal((m) => ({ ...m, nomeAtivo: e.target.value }))} />
                    </label>
                    <label className="label">Tipo de movimento
                      <select className="input" value={modal.tipoMovimento} onChange={(e) => setModal((m) => ({ ...m, tipoMovimento: e.target.value }))}>
                        <option value="compra">Compra</option>
                        <option value="venda">Venda</option>
                      </select>
                    </label>
                    <label className="label">Valor total (€)
                      <input className="input" type="number" value={modal.valorTotal} onChange={(e) => setModal((m) => ({ ...m, valorTotal: e.target.value }))} />
                    </label>
                  </>
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

      {modalPreco.aberto && (
        <div className="modal-overlay" onClick={fecharModalPreco}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-titulo">Actualizar preço</h3>
            <p className="modal-subtitulo">{modalPreco.ativo.nome} {modalPreco.ativo.simbolo ? `· ${modalPreco.ativo.simbolo}` : ''}</p>

            <label className="label">Data
              <input
                className="input"
                type="date"
                value={modalPreco.data}
                onChange={(e) => setModalPreco((m) => ({ ...m, data: e.target.value }))}
              />
            </label>
            <label className="label">Preço actual (€)
              <input
                className="input"
                type="number"
                step="0.0001"
                value={modalPreco.preco}
                onChange={(e) => setModalPreco((m) => ({ ...m, preco: e.target.value }))}
              />
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

function MovimentosAtivo({ ativoId }) {
  const [movimentos, setMovimentos] = useState([]);

  useEffect(() => {
    getMovimentos(ativoId).then((r) => setMovimentos(r.data));
  }, [ativoId]);

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
            <td className="col-valor col-mono">{m.valor_total.toFixed(2)} €</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
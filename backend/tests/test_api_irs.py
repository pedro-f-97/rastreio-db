"""Testes do relatório anual do IRS (`GET /api/irs/{ano}` e `GET /api/irs/anos`).

As vendas dão uma linha por dia de compra consumido pelo FIFO, com os valores
brutos e as comissões nas despesas, repartidos pelas unidades. Agrupam-se pelo
anexo e pelo quadro: valores mobiliários numa corretora portuguesa no anexo G,
quadro 9, e numa estrangeira no anexo J, quadro 9.2A; criptoativos detidos
menos de 365 dias no anexo G, quadro 18A, e 365 ou mais no anexo G1, quadro 7.
Os dividendos e os juros mostram o valor recebido, com os portugueses à parte.

Os movimentos gravam-se como a janela «Tratar» os grava: `valor_total`
negativo nas compras (o total mais a comissão) e positivo nas vendas (o total
menos a comissão). Os valores esperados são calculados à mão, com a conta no
docstring. As datas são fixas.
"""

from datetime import date

import pytest

from database import (
    Ativo,
    Categoria,
    ClassificacaoFiscal,
    Conta,
    MovimentoAtivo,
    Subcategoria,
    TipoAtivo,
    TipoCategoria,
    TipoContabilizacao,
    TipoMovimento,
    Transacao,
)


@pytest.fixture
def novo_ativo(session):
    """Cria um ativo de um tipo novo com a classificação dada."""

    def criar(nome, classificacao, pais="PT", pais_emitente=None, tem_unidades=True):
        tipo = TipoAtivo(
            nome=f"Tipo de {nome}", tem_unidades=tem_unidades, classificacao_fiscal=classificacao
        )
        session.add(tipo)
        session.commit()
        ativo = Ativo(
            nome=nome,
            tipo_id=tipo.id,
            contabilizacao=TipoContabilizacao.investimento,
            pais=pais,
            pais_emitente=pais_emitente,
        )
        session.add(ativo)
        session.commit()
        return ativo

    return criar


@pytest.fixture
def mov(session):
    """Grava um movimento: `total` sem comissão e `comissao`, como na janela."""

    def gravar(ativo, tipo, dia, quantidade, total, comissao=0.0, transacao=None):
        if tipo == TipoMovimento.compra:
            valor_total = -(total + comissao)
        else:
            valor_total = total - comissao
        session.add(
            MovimentoAtivo(
                ativo_id=ativo.id,
                tipo_movimento=tipo,
                data=dia,
                quantidade=quantidade,
                comissao=comissao,
                valor_total=valor_total,
                transacao_id=transacao.id if transacao else None,
            )
        )
        session.commit()

    return gravar


COMPRA, VENDA, DIVIDENDO = TipoMovimento.compra, TipoMovimento.venda, TipoMovimento.dividendo


def _relatorio(client, ano):
    r = client.get(f"/api/irs/{ano}")
    assert r.status_code == 200
    return r.json()


def _resumo_linha(linha):
    return (
        linha["data_aquisicao"],
        linha["quantidade"],
        linha["valor_aquisicao"],
        linha["valor_realizacao"],
        linha["despesas"],
        linha["ganho"],
        linha["dias"],
    )


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------


def test_exemplo_das_dezoito_vwce(client, session, novo_ativo, mov):
    """VWCE (fundos, G20) na Trade Republic (DE), emitente na Irlanda (IE).

    Compras: 10 a 10/03/2023 por 1 000 € (+1 €); 5 a 15/06/2023 por 550 € (+1 €);
    5 no mesmo dia por 560 € (+1 €). Venda: 18 a 20/05/2025 por 2 340 € (−1 €).

    Pelo FIFO, a venda leva as 10 de março e 8 de junho (5 da 2.ª e 3 da 3.ª),
    e as de junho juntam-se numa linha:
      linha 1: 10 unidades
        aquisição  1 000,00
        realização 2 340 × 10/18 = 1 300,00
        despesas   1 + 1 × 10/18 = 1,5556 -> 1,56
        ganho      1 300,00 − 1 000,00 − 1,56 = 298,44
        dias       10/03/2023 -> 20/05/2025 = 366 + 365 + 71 = 802
      linha 2: 8 unidades
        aquisição  550 + 560 × 3/5 = 886,00
        realização 2 340 × 8/18 = 1 040,00
        despesas   1 + 1 × 3/5 + 1 × 8/18 = 2,0444 -> 2,04
        ganho      1 040,00 − 886,00 − 2,04 = 151,96
        dias       15/06/2023 -> 20/05/2025 = 366 + 339 = 705
      totais: realização 2 340,00; aquisição 1 886,00; despesas 3,60;
              saldo 298,44 + 151,96 = 450,40
    O saldo bate com o realizado do resumo do ativo:
      2 339 − (1 001 + 551 + 561 × 3/5) = 2 339 − 1 888,60 = 450,40
    """
    vwce = novo_ativo("VWCE", ClassificacaoFiscal.fundos, pais="DE", pais_emitente="IE")
    mov(vwce, COMPRA, date(2023, 3, 10), 10, 1000.0, 1.0)
    mov(vwce, COMPRA, date(2023, 6, 15), 5, 550.0, 1.0)
    mov(vwce, COMPRA, date(2023, 6, 15), 5, 560.0, 1.0)
    mov(vwce, VENDA, date(2025, 5, 20), 18, 2340.0, 1.0)

    r = _relatorio(client, 2025)

    assert len(r["vendas"]) == 1
    grupo = r["vendas"][0]
    assert (grupo["anexo"], grupo["quadro"]) == ("J", "9.2A")
    assert [_resumo_linha(li) for li in grupo["linhas"]] == [
        ("2023-03-10", 10, 1000.0, 1300.0, 1.56, 298.44, 802),
        ("2023-06-15", 8, 886.0, 1040.0, 2.04, 151.96, 705),
    ]
    linha = grupo["linhas"][0]
    assert linha["codigo"] == "G20"
    assert linha["data_realizacao"] == "2025-05-20"
    assert linha["pais_fonte"] == {"codigo": "IE", "numero": "372"}
    assert linha["pais_contraparte"] == {"codigo": "DE", "numero": "276"}
    assert grupo["totais"] == {
        "realizacao": 2340.0,
        "aquisicao": 1886.0,
        "despesas": 3.6,
        "saldo": 450.4,
    }
    resumo = client.get(f"/api/patrimonio/ativos/{vwce.id}/resumo").json()
    assert resumo["realizado"] == grupo["totais"]["saldo"]


def test_venda_numa_corretora_portuguesa_vai_para_o_anexo_g(client, session, novo_ativo, mov):
    """Ações (G01) numa corretora portuguesa, sem emitente: anexo G, quadro 9,
    e os dois países são PT (620)."""
    acao = novo_ativo("EDP", ClassificacaoFiscal.acoes)
    mov(acao, COMPRA, date(2024, 2, 1), 100, 400.0)
    mov(acao, VENDA, date(2025, 2, 1), 100, 450.0)

    grupo = _relatorio(client, 2025)["vendas"][0]

    assert (grupo["anexo"], grupo["quadro"]) == ("G", "9")
    linha = grupo["linhas"][0]
    assert linha["codigo"] == "G01"
    assert linha["pais_fonte"] == linha["pais_contraparte"] == {"codigo": "PT", "numero": "620"}


def test_cada_venda_conta_no_ano_da_data_do_movimento(client, session, novo_ativo, mov):
    """Compra de 10 a 01/06/2024; vendas de 4 a 31/12/2024 e de 6 a 01/01/2025.

    2024: só a venda de 31/12 (4 unidades); 2025: só a de 01/01 (6 unidades).
    Os anos disponíveis são [2025, 2024].
    """
    etf = novo_ativo("ETF", ClassificacaoFiscal.fundos)
    mov(etf, COMPRA, date(2024, 6, 1), 10, 1000.0)
    mov(etf, VENDA, date(2024, 12, 31), 4, 440.0)
    mov(etf, VENDA, date(2025, 1, 1), 6, 660.0)

    v2024 = _relatorio(client, 2024)["vendas"][0]["linhas"]
    v2025 = _relatorio(client, 2025)["vendas"][0]["linhas"]

    assert [(li["data_realizacao"], li["quantidade"]) for li in v2024] == [("2024-12-31", 4)]
    assert [(li["data_realizacao"], li["quantidade"]) for li in v2025] == [("2025-01-01", 6)]
    assert client.get("/api/irs/anos").json() == [2025, 2024]


def test_criptoativos_detidos_364_e_365_dias_ficam_em_quadros_diferentes(
    client, session, novo_ativo, mov
):
    """Bitcoin: 1 comprado a 01/01/2024 e 1 a 02/01/2024, por 100 € cada;
    vendidos os 2 a 31/12/2024 por 300 €.

    2024 é bissexto: 01/01 -> 31/12 são 365 dias, e 02/01 -> 31/12 são 364.
      a de 365 dias -> anexo G1, quadro 7 (excluída, mas declarada)
      a de 364 dias -> anexo G, quadro 18A
      cada uma: realização 300/2 = 150,00; aquisição 100,00; ganho 50,00
    Os quadros mostram-se pela ordem G 18A, G1 7; os criptoativos não têm código.
    """
    btc = novo_ativo("Bitcoin", ClassificacaoFiscal.criptoativos, pais="DE")
    mov(btc, COMPRA, date(2024, 1, 1), 1, 100.0)
    mov(btc, COMPRA, date(2024, 1, 2), 1, 100.0)
    mov(btc, VENDA, date(2024, 12, 31), 2, 300.0)

    vendas = _relatorio(client, 2024)["vendas"]

    assert [(g["anexo"], g["quadro"]) for g in vendas] == [("G", "18A"), ("G1", "7")]
    assert [_resumo_linha(li) for li in vendas[0]["linhas"]] == [
        ("2024-01-02", 1, 100.0, 150.0, 0.0, 50.0, 364)
    ]
    assert [_resumo_linha(li) for li in vendas[1]["linhas"]] == [
        ("2024-01-01", 1, 100.0, 150.0, 0.0, 50.0, 365)
    ]
    assert vendas[0]["linhas"][0]["codigo"] is None


def test_comissao_zero_fica_dentro_dos_valores(client, session, novo_ativo, mov):
    """Um movimento antigo, gravado com a comissão no total e comissão 0:
    compra 10 por 1 000 € e venda 10 por 1 200 €.
      aquisição 1 000,00; realização 1 200,00; despesas 0; ganho 200,00
    """
    etf = novo_ativo("ETF", ClassificacaoFiscal.fundos)
    mov(etf, COMPRA, date(2024, 1, 10), 10, 1000.0)
    mov(etf, VENDA, date(2025, 1, 10), 10, 1200.0)

    linha = _relatorio(client, 2025)["vendas"][0]["linhas"][0]

    assert (linha["valor_aquisicao"], linha["valor_realizacao"], linha["despesas"]) == (
        1000.0,
        1200.0,
        0.0,
    )
    assert linha["ganho"] == 200.0


def test_ativos_fora_do_irs_ou_sem_unidades_nao_aparecem(client, session, novo_ativo, mov):
    """Ouro (fora do IRS) e um tipo sem unidades classificado como valor
    mobiliário: as vendas de nenhum deles entram, e não há anos disponíveis."""
    ouro = novo_ativo("Ouro", ClassificacaoFiscal.fora)
    mov(ouro, COMPRA, date(2024, 1, 10), 1, 1000.0)
    mov(ouro, VENDA, date(2025, 1, 10), 1, 1500.0)
    quadro = novo_ativo("Quadro", ClassificacaoFiscal.outros_mobiliarios, tem_unidades=False)
    mov(quadro, COMPRA, date(2024, 1, 10), None, 500.0)
    mov(quadro, VENDA, date(2025, 1, 10), None, 800.0)

    assert _relatorio(client, 2025)["vendas"] == []
    assert client.get("/api/irs/anos").json() == []


# ---------------------------------------------------------------------------
# Dividendos e juros
# ---------------------------------------------------------------------------


def test_dividendos_do_ano_com_os_portugueses_a_parte(client, session, novo_ativo, mov):
    """Um ETF na Trade Republic (DE), emitente IE: dividendos de 15,00 e de
    5,50 em 2025 e de 9,00 em 2024. Uma ação numa corretora portuguesa:
    dividendo de 10,00 em 2025. Um ETF irlandês (IE) num banco português:
    dividendo de 2,00 em 2025.

    2025: grupo Portugal primeiro, 10,00 + 2,00 = 12,00 (a corretora é
    portuguesa); depois o da Irlanda (o país da fonte é o do emitente),
    15,00 + 5,50 = 20,50. O de 2024 não entra.
    """
    etf = novo_ativo("VHYL", ClassificacaoFiscal.fundos, pais="DE", pais_emitente="IE")
    mov(etf, COMPRA, date(2024, 1, 10), 10, 600.0)
    mov(etf, DIVIDENDO, date(2025, 3, 20), None, 15.0)
    mov(etf, DIVIDENDO, date(2025, 9, 20), None, 5.5)
    mov(etf, DIVIDENDO, date(2024, 9, 20), None, 9.0)
    acao = novo_ativo("EDP", ClassificacaoFiscal.acoes)
    mov(acao, COMPRA, date(2024, 1, 10), 100, 400.0)
    mov(acao, DIVIDENDO, date(2025, 5, 10), None, 10.0)
    # Um ETF irlandês num banco português: é a corretora que decide (decisão
    # 17), por isso fica no grupo de Portugal, e não no da Irlanda
    irl_pt = novo_ativo("IUSA", ClassificacaoFiscal.fundos, pais="PT", pais_emitente="IE")
    mov(irl_pt, COMPRA, date(2024, 1, 10), 10, 300.0)
    mov(irl_pt, DIVIDENDO, date(2025, 7, 1), None, 2.0)

    dividendos = _relatorio(client, 2025)["dividendos"]

    assert [(g["portugues"], g["pais"], g["total"]) for g in dividendos] == [
        (True, None, 12.0),
        (False, {"codigo": "IE", "numero": "372"}, 20.5),
    ]
    assert [(li["data"], li["valor"]) for li in dividendos[1]["linhas"]] == [
        ("2025-03-20", 15.0),
        ("2025-09-20", 5.5),
    ]


@pytest.fixture
def juros_e_salario(session):
    """Receita com Juros (marcada) e Salário (sem marca)."""
    receita = Categoria(nome="Receita", tipo=TipoCategoria.receita)
    session.add(receita)
    session.commit()
    juros = Subcategoria(nome="Juros", categoria_id=receita.id, juros_irs=True)
    salario = Subcategoria(nome="Salário", categoria_id=receita.id)
    session.add_all([juros, salario])
    session.commit()
    return receita, juros, salario


def test_juros_das_subcategorias_marcadas_pelo_pais_da_conta(client, session, juros_e_salario):
    """Contas Banco (PT) e TR (DE). Em 2025: juros de 5,00 no Banco, de 3,21 e
    2,00 na TR, e um salário de 1 000,00 (sem marca); em 2024, juros de 4,00.

    2025: Portugal 5,00; Alemanha 3,21 + 2,00 = 5,21. O salário e os juros de
    2024 não entram. Os anos disponíveis são [2025, 2024].
    """
    receita, juros, salario = juros_e_salario
    banco = Conta(nome="Banco", saldo_referencia=0.0, data_referencia=date(2024, 1, 1))
    tr = Conta(nome="TR", saldo_referencia=0.0, data_referencia=date(2024, 1, 1), pais="DE")
    session.add_all([banco, tr])
    session.commit()

    def transacao(conta, dia, valor, sub):
        session.add(
            Transacao(
                data=dia,
                descricao=f"{sub.nome} {conta.nome}",
                valor=valor,
                conta_id=conta.id,
                categoria_id=receita.id,
                subcategoria_id=sub.id,
            )
        )

    transacao(banco, date(2025, 6, 30), 5.0, juros)
    transacao(tr, date(2025, 3, 1), 3.21, juros)
    transacao(tr, date(2025, 4, 1), 2.0, juros)
    transacao(banco, date(2025, 1, 25), 1000.0, salario)
    transacao(banco, date(2024, 6, 30), 4.0, juros)
    session.commit()

    r = _relatorio(client, 2025)

    assert [(g["portugues"], g["pais"], g["total"]) for g in r["juros"]] == [
        (True, None, 5.0),
        (False, {"codigo": "DE", "numero": "276"}, 5.21),
    ]
    assert [(li["conta"], li["valor"]) for li in r["juros"][1]["linhas"]] == [
        ("TR", 3.21),
        ("TR", 2.0),
    ]
    assert client.get("/api/irs/anos").json() == [2025, 2024]


# ---------------------------------------------------------------------------
# Transações por tratar
# ---------------------------------------------------------------------------


def test_conta_so_as_transacoes_do_ano_por_tratar(client, session, novo_ativo, mov):
    """Subcategoria de investimento que trata património, com três transações:
    uma de 2025 por tratar, uma de 2025 já tratada (tem movimento) e uma de 2024
    por tratar. Para 2025, conta 1; para 2024, conta 1."""
    cat = Categoria(nome="Investimento", tipo=TipoCategoria.investimento)
    session.add(cat)
    session.commit()
    sub = Subcategoria(nome="ETFs", categoria_id=cat.id, trata_patrimonio=True)
    session.add(sub)
    session.commit()

    def transacao(dia):
        t = Transacao(
            data=dia, descricao="Compra", valor=-100.0, categoria_id=cat.id, subcategoria_id=sub.id
        )
        session.add(t)
        session.commit()
        return t

    transacao(date(2025, 2, 1))
    tratada = transacao(date(2025, 3, 1))
    transacao(date(2024, 5, 1))
    etf = novo_ativo("ETF", ClassificacaoFiscal.fundos)
    mov(etf, COMPRA, date(2025, 3, 1), 1, 100.0, transacao=tratada)

    assert _relatorio(client, 2025)["pendentes"] == 1
    assert _relatorio(client, 2024)["pendentes"] == 1


def test_ano_fora_dos_limites_da_422(client, session):
    assert client.get("/api/irs/1999").status_code == 422

"""Testes do crescimento do património por mês (`calcular_crescimento`).

* O crescimento é a inclinação da recta dos mínimos quadrados ajustada ao
  património no fim de cada mês, do mês da primeira transação (ou de janeiro do
  ano filtrado) ao último mês completo: o mês em curso fica de fora.
* Separa-se em valorização (a inclinação do ganho acumulado dos ativos:
  valor − custo + realizado) e no que se poupa (o total menos a valorização).
* Com menos de `MESES_MINIMOS` (3) meses, os valores vêm a `None`.

Os valores esperados são escritos à mão, com a conta no comentário. Com
`x = 0..n-1`, a inclinação é `Σ(x − x̄)·y / Σ(x − x̄)²`; com 4 meses, os pesos
`x − x̄` são -1,5, -0,5, 0,5 e 1,5, e `Σ(x − x̄)² = 5`.
"""

from datetime import date

import pytest

from database import (
    Ativo,
    Conta,
    MovimentoAtivo,
    PrecoAtivo,
    TipoAtivo,
    TipoContabilizacao,
    TipoMovimento,
    Transacao,
)
from routers import patrimonio as patrimonio_router
from servicos.patrimonio_serv import calcular_crescimento, gerar_evolucao

# O último mês completo é abril de 2025
HOJE = date(2025, 5, 15)

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def semear_conta(session, saldo_referencia, data_referencia=date(2024, 12, 31)):
    conta = Conta(
        nome="Ordem",
        saldo_referencia=saldo_referencia,
        data_referencia=data_referencia,
        ativa=True,
    )
    session.add(conta)
    session.commit()
    return conta


def semear_transacoes(session, conta, transacoes):
    session.add_all(
        Transacao(data=d, descricao="T", valor=v, conta_id=conta.id) for d, v in transacoes
    )
    session.commit()


def semear_ativo(session, tem_unidades):
    tipo = TipoAtivo(nome="Tipo", tem_unidades=tem_unidades)
    session.add(tipo)
    session.commit()
    contabilizacao = (
        TipoContabilizacao.investimento if tem_unidades else TipoContabilizacao.patrimonio
    )
    ativo = Ativo(nome="Ativo", tipo_id=tipo.id, contabilizacao=contabilizacao)
    session.add(ativo)
    session.commit()
    return ativo


def semear_movimento(session, ativo, tipo_movimento, data, valor_total, quantidade=None):
    session.add(
        MovimentoAtivo(
            ativo_id=ativo.id,
            tipo_movimento=tipo_movimento,
            data=data,
            quantidade=quantidade,
            valor_total=valor_total,
        )
    )
    session.commit()


def semear_preco(session, ativo, data, preco):
    session.add(PrecoAtivo(ativo_id=ativo.id, data=data, preco=preco))
    session.commit()


def valores(resultado):
    return (resultado["total"], resultado["poupanca"], resultado["valorizacao"])


# ---------------------------------------------------------------------------
# Tendência e mês em curso
# ---------------------------------------------------------------------------


def test_so_poupanca_e_sem_o_mes_em_curso(session):
    """+100 € em cada mês de janeiro a abril: 100, 200, 300, 400 no fim de cada
    mês, inclinação 100. Os +999 € de maio (o mês em curso) ficam de fora; se
    entrassem, a recta mudava."""
    conta = semear_conta(session, 0.0)
    semear_transacoes(
        session,
        conta,
        [
            (date(2025, 1, 10), 100.0),
            (date(2025, 2, 10), 100.0),
            (date(2025, 3, 10), 100.0),
            (date(2025, 4, 10), 100.0),
            (date(2025, 5, 5), 999.0),
        ],
    )

    r = calcular_crescimento(session, None, HOJE)

    assert (r["de"], r["ate"], r["meses"]) == ("2025-01-31", "2025-04-30", 4)
    assert valores(r) == (100.0, 100.0, 0.0)


def test_tendencia_e_nao_media_do_primeiro_ao_ultimo(session):
    """Fins de mês 0, 100, 100, 400 (média 150; desvios -150, -50, -50, 250):
    (-1,5·-150 + -0,5·-50 + 0,5·-50 + 1,5·250) / 5 = (225 + 25 - 25 + 375) / 5
    = 120. A média simples daria (400 - 0) / 3 = 133,33."""
    conta = semear_conta(session, 0.0)
    semear_transacoes(
        session,
        conta,
        [(date(2025, 1, 10), 0.0), (date(2025, 2, 10), 100.0), (date(2025, 4, 10), 300.0)],
    )

    assert valores(calcular_crescimento(session, None, HOJE)) == (120.0, 120.0, 0.0)


# ---------------------------------------------------------------------------
# Valorização
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vender", [False, True])
def test_comprar_nao_muda_e_a_subida_do_preco_e_valorizacao(session, vender):
    """Conta com 1 000 €; em 05/01 compra 10 un. por 500 € (preço 50).
    Em 20/03 o preço sobe para 55: +50 €.

    Fins de mês: total 1000, 1000, 1050, 1050 (500 de liquidez + 500, 500, 550,
    550 do ETF); valorização 0, 0, 50, 50. Ambas com desvios -25, -25, 25, 25:
    (37,5 + 12,5 + 12,5 + 37,5) / 5 = 20. Poupança 20 - 20 = 0.

    Com a venda de tudo em 10/04 por 550 €, abril fica com 1 050 € de liquidez e
    0 de ETF, e a valorização mantém-se em 50 (realizado 550 - 500): nada muda.
    """
    conta = semear_conta(session, 1000.0)
    semear_transacoes(session, conta, [(date(2025, 1, 5), -500.0)])
    etf = semear_ativo(session, tem_unidades=True)
    semear_movimento(session, etf, TipoMovimento.compra, date(2025, 1, 5), -500.0, 10)
    semear_preco(session, etf, date(2025, 1, 5), 50.0)
    semear_preco(session, etf, date(2025, 3, 20), 55.0)
    if vender:
        semear_transacoes(session, conta, [(date(2025, 4, 10), 550.0)])
        semear_movimento(session, etf, TipoMovimento.venda, date(2025, 4, 10), 550.0, 10)

    pontos = gerar_evolucao(
        session, date(2025, 1, 1), date(2025, 4, 30), HOJE, com_valorizacao=True
    )
    assert [(p["total"], p["valorizacao"]) for p in pontos] == [
        (1000.0, 0.0),
        (1000.0, 0.0),
        (1050.0, 50.0),
        (1050.0, 50.0),
    ]
    assert valores(calcular_crescimento(session, None, HOJE)) == (20.0, 0.0, 20.0)


def test_bem_que_desvaloriza(session):
    """Conta com 20 000 €; em 05/01 compra um carro por 15 000 €. Sem preço,
    vale o custo; depois 14 700 (15/02) e 14 400 (15/04).

    Fins de mês: total 20000, 19700, 19700, 19400 (desvios 300, 0, 0, -300);
    valorização 0, -300, -300, -600 (os mesmos desvios). Inclinação
    (-1,5·300 + 1,5·-300) / 5 = -180. A compra não conta como menos poupança."""
    conta = semear_conta(session, 20000.0)
    semear_transacoes(session, conta, [(date(2025, 1, 5), -15000.0)])
    carro = semear_ativo(session, tem_unidades=False)
    semear_movimento(session, carro, TipoMovimento.compra, date(2025, 1, 5), -15000.0)
    semear_preco(session, carro, date(2025, 2, 15), 14700.0)
    semear_preco(session, carro, date(2025, 4, 15), 14400.0)

    assert valores(calcular_crescimento(session, None, HOJE)) == (-180.0, 0.0, -180.0)


def test_as_parcelas_somam_o_total_ao_centimo(session):
    """Três meses (hoje 10/04). Conta com 1 €; em 10/01 compra 1 un. por 1 €
    (preço 1,00); em 10/03 entram 0,01 € e em 15/03 o preço passa a 1,01.

    Fins de mês: total 1, 1, 1,02; valorização 0, 0, 0,01. Com 3 meses, a
    inclinação é (último - primeiro) / 2: total 0,01; valorização 0,005, que
    arredonda para 0,01. A poupança é 0,01 - 0,01 = 0. Calculada à parte, a
    inclinação da poupança (1, 1, 1,01) daria 0,005, arredondada a 0,01, e as
    parcelas somariam 0,02."""
    conta = semear_conta(session, 1.0)
    semear_transacoes(session, conta, [(date(2025, 1, 10), -1.0), (date(2025, 3, 10), 0.01)])
    etf = semear_ativo(session, tem_unidades=True)
    semear_movimento(session, etf, TipoMovimento.compra, date(2025, 1, 10), -1.0, 1)
    semear_preco(session, etf, date(2025, 1, 10), 1.0)
    semear_preco(session, etf, date(2025, 3, 15), 1.01)

    r = calcular_crescimento(session, None, date(2025, 4, 10))

    assert r["meses"] == 3
    assert valores(r) == (0.01, 0.0, 0.01)


# ---------------------------------------------------------------------------
# Filtro de ano e mínimo de meses
# ---------------------------------------------------------------------------


def semear_dois_anos(session):
    """+100 € de outubro a dezembro de 2024, +200 € de janeiro a abril de 2025,
    e +999 € em maio (o mês em curso). Fins de mês: 100, 200, 300 | 500, 700,
    900, 1100."""
    conta = semear_conta(session, 0.0, date(2024, 9, 30))
    semear_transacoes(
        session,
        conta,
        [(date(2024, m, 10), 100.0) for m in (10, 11, 12)]
        + [(date(2025, m, 10), 200.0) for m in (1, 2, 3, 4)]
        + [(date(2025, 5, 10), 999.0)],
    )


@pytest.mark.parametrize(
    "ano, de, ate, meses, total",
    [
        # 100, 200, 300: (300 - 100) / 2 = 100
        (2024, "2024-10-31", "2024-12-31", 3, 100.0),
        # 500, 700, 900, 1100: sobe 200 por mês
        (2025, "2025-01-31", "2025-04-30", 4, 200.0),
        # Sete meses, x̄ = 3: Σ(x − 3)·y = -300 - 400 - 300 + 0 + 700 + 1800 + 3300
        # = 4800; Σ(x − 3)² = 9 + 4 + 1 + 0 + 1 + 4 + 9 = 28; 4800 / 28 = 171,43
        (None, "2024-10-31", "2025-04-30", 7, 171.43),
    ],
)
def test_o_filtro_de_ano_corta_o_periodo(session, ano, de, ate, meses, total):
    semear_dois_anos(session)

    r = calcular_crescimento(session, ano, HOJE)

    assert (r["de"], r["ate"], r["meses"]) == (de, ate, meses)
    assert valores(r) == (total, total, 0.0)


def test_ano_sem_meses(session):
    semear_dois_anos(session)

    r = calcular_crescimento(session, 2023, HOJE)

    assert r == {
        "de": None,
        "ate": None,
        "meses": 0,
        "total": None,
        "poupanca": None,
        "valorizacao": None,
    }


def test_abaixo_do_minimo_de_meses_nao_calcula(session):
    """Hoje 10/03: só janeiro e fevereiro estão completos (2 < 3)."""
    conta = semear_conta(session, 0.0)
    semear_transacoes(session, conta, [(date(2025, 1, 10), 100.0), (date(2025, 2, 10), 100.0)])

    r = calcular_crescimento(session, None, date(2025, 3, 10))

    assert (r["de"], r["ate"], r["meses"]) == ("2025-01-31", "2025-02-28", 2)
    assert valores(r) == (None, None, None)


# ---------------------------------------------------------------------------
# GET /api/patrimonio/crescimento
# ---------------------------------------------------------------------------


def test_api_usa_hoje_e_o_ano(client, session, monkeypatch):
    """O mesmo cenário dos dois anos, com o `date.today()` do router fixo em
    15/05/2025."""
    from datetime import date as Date

    class HojeFixo(Date):
        @classmethod
        def today(cls):
            return cls(2025, 5, 15)

    monkeypatch.setattr(patrimonio_router, "date", HojeFixo)
    semear_dois_anos(session)

    r = client.get("/api/patrimonio/crescimento", params={"ano": 2025})

    assert r.status_code == 200
    assert r.json() == {
        "de": "2025-01-31",
        "ate": "2025-04-30",
        "meses": 4,
        "total": 200.0,
        "poupanca": 200.0,
        "valorizacao": 0.0,
    }

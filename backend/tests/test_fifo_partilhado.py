"""Testes de `percorrer_fifo` (`servicos/patrimonio_serv.py`).

É o percurso FIFO partilhado pelo resumo de um ativo, pela evolução do
património e pelo relatório do IRS. Os testes de caracterização do resumo
(`test_patrimonio_fifo.py`) fixam o que o resumo devolve; estes fixam o que só
a função partilhada devolve: os pedaços de lotes que cada venda consumiu.

Os movimentos são objectos simples com os campos que a função lê, pela ordem
(data, id) em que a BD os entrega. O `valor_total` segue a convenção gravada
pelo frontend: negativo nas compras, positivo nas vendas e nos dividendos. Os
valores esperados são calculados à mão e escritos como constantes.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from database import TipoMovimento
from servicos.dinheiro import arredondar
from servicos.patrimonio_serv import percorrer_fifo


def _movimento(tipo, dia, quantidade, valor_total):
    return SimpleNamespace(
        tipo_movimento=tipo, data=dia, quantidade=quantidade, valor_total=valor_total
    )


def _compra(dia, quantidade, valor_total):
    return _movimento(TipoMovimento.compra, dia, quantidade, valor_total)


def _venda(dia, quantidade, valor_total):
    return _movimento(TipoMovimento.venda, dia, quantidade, valor_total)


def _pedacos(venda):
    """Os pedaços consumidos por uma venda, como (compra, quantidade, custo)."""
    return [(c["compra"], c["quantidade"], c["custo"]) for c in venda["consumidos"]]


def test_venda_dentro_de_um_so_lote():
    """Compra 10 unidades por 1 000 €; vende 4 por 500 €.

    A venda leva 4 das 10 unidades do lote:
      custo = 1 000 × 4 / 10 = 400
      realizado = 500 − 400 = 100
    Fica em carteira o resto do lote: 6 unidades, custo 1 000 − 400 = 600.
    """
    compra = _compra(date(2025, 1, 10), 10, -1000.0)
    venda = _venda(date(2025, 2, 10), 4, 500.0)

    fifo = percorrer_fifo([compra, venda])

    assert len(fifo["vendas"]) == 1
    v = fifo["vendas"][0]
    assert v["venda"] is venda
    assert (v["quantidade"], v["valor"]) == (Decimal(4), Decimal(500))
    assert _pedacos(v) == [(compra, Decimal(4), Decimal(400))]
    assert fifo["realizado"] == Decimal(100)
    assert [(lote["compra"], lote["quantidade"], lote["custo"]) for lote in fifo["lotes"]] == [
        (compra, Decimal(6), Decimal(600))
    ]


def test_venda_que_atravessa_dois_lotes():
    """Compra A: 10 por 1 000 €; compra B: 10 por 1 200 €; vende 15 por 1 800 €.

    Pelo FIFO, a venda leva primeiro o lote A inteiro e depois 5 do lote B:
      A: 10 unidades, custo 1 000
      B: 5 unidades, custo 1 200 × 5 / 10 = 600
      realizado = 1 800 − (1 000 + 600) = 200
    Fica em carteira o resto de B: 5 unidades, custo 600.
    """
    a = _compra(date(2025, 1, 10), 10, -1000.0)
    b = _compra(date(2025, 3, 10), 10, -1200.0)
    venda = _venda(date(2025, 5, 10), 15, 1800.0)

    fifo = percorrer_fifo([a, b, venda])

    assert _pedacos(fifo["vendas"][0]) == [
        (a, Decimal(10), Decimal(1000)),
        (b, Decimal(5), Decimal(600)),
    ]
    assert fifo["realizado"] == Decimal(200)
    assert [(lote["compra"], lote["quantidade"], lote["custo"]) for lote in fifo["lotes"]] == [
        (b, Decimal(5), Decimal(600))
    ]


def test_duas_vendas_seguidas_continuam_onde_a_anterior_parou():
    """Compra A: 10 por 1 000 €; compra B: 10 por 1 200 €.
    Venda 1: 6 por 700 €; venda 2: 8 por 1 000 €.

    Venda 1 leva 6 de A: custo 1 000 × 6 / 10 = 600; ganho 700 − 600 = 100.
    Ficam em A 4 unidades, custo 400.
    Venda 2 leva as 4 de A (custo 400) e 4 de B (custo 1 200 × 4 / 10 = 480);
    ganho 1 000 − 880 = 120.
    realizado = 100 + 120 = 220
    Fica em carteira o resto de B: 6 unidades, custo 1 200 − 480 = 720.
    """
    a = _compra(date(2025, 1, 10), 10, -1000.0)
    b = _compra(date(2025, 2, 10), 10, -1200.0)
    v1 = _venda(date(2025, 3, 10), 6, 700.0)
    v2 = _venda(date(2025, 4, 10), 8, 1000.0)

    fifo = percorrer_fifo([a, b, v1, v2])

    primeira, segunda = fifo["vendas"]
    assert _pedacos(primeira) == [(a, Decimal(6), Decimal(600))]
    assert _pedacos(segunda) == [
        (a, Decimal(4), Decimal(400)),
        (b, Decimal(4), Decimal(480)),
    ]
    assert fifo["realizado"] == Decimal(220)
    assert [(lote["compra"], lote["quantidade"], lote["custo"]) for lote in fifo["lotes"]] == [
        (b, Decimal(6), Decimal(720))
    ]


def test_divisoes_inexactas_deixam_resto_so_abaixo_do_centimo():
    """Compra 3 unidades por 100 €; vende 1 por 40 € e depois 2 por 90 €.

    O `Decimal` guarda 28 algarismos significativos em cada operação:
      venda 1: custo = 100 × 1 / 3 = 33,33333333333333333333333333
               ficam 2 unidades com custo 100 − 33,33333333333333333333333333
                                           = 66,66666666666666666666666667
      venda 2: 66,66666666666666666666666667 × 2 = 133,3333333333333333333333333
               (a multiplicação também arredonda aos 28 algarismos)
               custo = 133,3333333333333333333333333 / 2
                     = 66,66666666666666666666666665
    Os dois pedaços somam 99,99999999999999999999999998: menos 2 × 10⁻²⁶ do
    que a compra, um resto que desaparece ao arredondar ao cêntimo (100,00).
    realizado = (40 − 33,33333333333333333333333333)
              + (90 − 66,66666666666666666666666665)
              = 6,66666666666666666666666667 + 23,33333333333333333333333335
              = 30,00000000000000000000000002
    """
    compra = _compra(date(2025, 1, 10), 3, -100.0)
    v1 = _venda(date(2025, 2, 10), 1, 40.0)
    v2 = _venda(date(2025, 3, 10), 2, 90.0)

    fifo = percorrer_fifo([compra, v1, v2])

    primeira, segunda = fifo["vendas"]
    assert _pedacos(primeira) == [(compra, Decimal(1), Decimal("33.33333333333333333333333333"))]
    assert _pedacos(segunda) == [(compra, Decimal(2), Decimal("66.66666666666666666666666665"))]
    custos = [c["custo"] for v in fifo["vendas"] for c in v["consumidos"]]
    assert arredondar(sum(custos, Decimal(0))) == 100.0
    assert fifo["realizado"] == Decimal("30.00000000000000000000000002")
    assert fifo["lotes"] == []


def test_venda_acima_das_unidades_em_carteira_so_conta_as_que_havia():
    """Compra 2 unidades por 200 €; vende 3 por 330 € (a API recusa, mas a
    função não rebenta: é o comportamento actual, fixado aqui).

    Só havia 2 unidades: a venda conta 2 e a parte do valor que lhes cabe:
      valor = 330 × 2 / 3 = 220
      realizado = 220 − 200 = 20
    """
    compra = _compra(date(2025, 1, 10), 2, -200.0)
    venda = _venda(date(2025, 2, 10), 3, 330.0)

    fifo = percorrer_fifo([compra, venda])

    v = fifo["vendas"][0]
    assert (v["quantidade"], v["valor"]) == (Decimal(2), Decimal(220))
    assert _pedacos(v) == [(compra, Decimal(2), Decimal(200))]
    assert fifo["realizado"] == Decimal(20)


def test_dividendo_entra_no_realizado_mas_nao_e_uma_venda():
    """Compra 10 por 1 000 €; dividendo de 15 €.

    O dividendo soma ao realizado (15) e não consome lotes nem aparece nas
    vendas: o lote fica com 10 unidades e custo 1 000.
    """
    compra = _compra(date(2025, 1, 10), 10, -1000.0)
    dividendo = _movimento(TipoMovimento.dividendo, date(2025, 6, 10), None, 15.0)

    fifo = percorrer_fifo([compra, dividendo])

    assert fifo["vendas"] == []
    assert fifo["realizado"] == Decimal(15)
    assert [(lote["quantidade"], lote["custo"]) for lote in fifo["lotes"]] == [
        (Decimal(10), Decimal(1000))
    ]

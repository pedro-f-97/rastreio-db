"""Testes do arredondamento ao cêntimo (`servicos/dinheiro.py`).

A regra é a metade para longe de zero, como o ARRED do Excel. Os valores
esperados são calculados à mão; os empates escolhidos são os que o `round` do
Python decide ao sabor do binário do float, para que a diferença se veja.
"""

from decimal import Decimal

import pytest

from servicos.dinheiro import arredondar, exato


@pytest.mark.parametrize(
    "entrada, esperado, nota",
    [
        (2.345, 2.35, "empate: 2,345 -> 2,35 (o round dava 2,35 por acaso do binário)"),
        (-2.345, -2.35, "empate negativo: a mesma magnitude que o positivo"),
        (1.005, 1.01, "empate: o binário de 1,005 é 1,00499..., e o round dava 1,0"),
        (0.125, 0.13, "empate exacto em binário: o round arredonda a par e dava 0,12"),
        (-79.845, -79.85, "a mediana real de Entretenimento em 2025: o round dava -79,84"),
        (2.344, 2.34, "abaixo do meio: arredonda para baixo"),
        (2.346, 2.35, "acima do meio: arredonda para cima"),
        (Decimal("5.005"), 5.01, "um Decimal entra sem passar pelo float"),
    ],
)
def test_arredondar_ao_centimo_com_metade_para_longe_de_zero(entrada, esperado, nota):
    assert arredondar(entrada) == esperado, nota


def test_exato_le_o_valor_escrito_e_nao_o_binario():
    """79,845 em float é 79,84499999999999886...; `exato` devolve o escrito.

    Cálculo à mão: `repr(79.845)` é "79.845", logo Decimal("79.845"). Um
    `Decimal` passa tal como está, sem passar pelo float: 2,3449999...
    com 20 noves tem mais casas do que um float guarda, e como float seria
    2,345, que arredonda para 2,35 em vez de 2,34.
    """
    assert exato(79.845) == Decimal("79.845")
    quase_empate = Decimal("2.34499999999999999999")
    assert exato(quase_empate) == quase_empate
    assert arredondar(quase_empate) == 2.34

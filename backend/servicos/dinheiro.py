from decimal import ROUND_HALF_UP, Decimal

CENTIMO = Decimal("0.01")


def exato(x) -> Decimal:
    """O número tal como foi escrito, e não o binário que o float guarda.

    `repr` dá a escrita mais curta que volta ao mesmo float: 79.845 vem como
    `Decimal("79.845")` e não como 79,84499999999999886... Um `Decimal` passa
    sem conversão.
    """
    if isinstance(x, Decimal):
        return x
    return Decimal(repr(float(x)))


def arredondar(x) -> float:
    """Arredonda ao cêntimo, com a metade para longe de zero, como o ARRED do
    Excel: 2,345 -> 2,35 e -2,345 -> -2,35 (D11)."""
    return float(exato(x).quantize(CENTIMO, rounding=ROUND_HALF_UP))

"""Verificação do saldo de uma conta contra os saldos do banco.

Os saldos esperados são os do campo `saldo` das transacções: os do extracto,
ou os que se escrevem à mão nas contas cujo extracto não os traz. O saldo de
referência da conta também é um ponto de controlo, com diferença 0 por
definição. Compara-se ao fim de cada dia, porque a BD não guarda a ordem das
transacções dentro do dia.
"""

from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import groupby, pairwise

from sqlalchemy.orm import Session

from database import Conta as ContaModel, Transacao as TransacaoModel
from servicos.dinheiro import CENTIMO, exato

# Um saldo mais antigo do que isto, contado da última transacção, sugere
# escrever um novo
DIAS_SALDO_ANTIGO = 31


def _cent(x) -> Decimal:
    """Ao cêntimo, com a metade para longe de zero, como `arredondar`."""
    return exato(x).quantize(CENTIMO, rounding=ROUND_HALF_UP)


def _saldo_fim_do_dia(transacoes, esperado: Decimal) -> tuple[Decimal, bool]:
    """O saldo do banco no fim do dia, e se a ordem ficou incerta.

    O saldo antes de cada transacção é o seu saldo menos o seu valor; a última
    do dia é aquela cujo saldo não é o «saldo antes» de nenhuma outra. Sem
    exactamente uma candidata (uma transacção de 0 €, um saldo repetido), fica
    o saldo mais próximo do esperado, e a ordem é incerta.
    """
    com_saldo = [t for t in transacoes if t.saldo is not None]
    saldos = [_cent(t.saldo) for t in com_saldo]
    antes = {_cent(t.saldo) - _cent(t.valor) for t in com_saldo}
    # Sem repetidos: o mesmo saldo do fim do dia escrito em duas transacções
    # é uma só candidata
    candidatos = {s for s in saldos if s not in antes}
    if len(candidatos) == 1:
        return candidatos.pop(), False
    return min(saldos, key=lambda s: abs(esperado - s)), True


def verificar_saldo(db: Session, conta: ContaModel) -> dict:
    """Compara o saldo calculado com o do banco em cada dia com saldo.

    Devolve a diferença (calculado − banco) no último ponto de controlo, os
    intervalos ]de, ate] em que a diferença mudou (sem `de`, a diferença do
    saldo de referência), os dias com a ordem incerta e se se deve sugerir
    escrever um saldo novo.
    """
    transacoes = (
        db.query(TransacaoModel.data, TransacaoModel.valor, TransacaoModel.saldo)
        .filter(TransacaoModel.conta_id == conta.id)
        .order_by(TransacaoModel.data, TransacaoModel.id)
        .all()
    )
    referencia = conta.data_referencia

    # O saldo ao fim de um dia é a referência mais as transacções em
    # ]referência, dia], ou menos as de ]dia, referência]: com as somas
    # acumuladas S, é referência + S(dia) − S(referência), como em
    # `saldo_conta_em`
    soma_ate_referencia = sum(
        (exato(t.valor) for t in transacoes if t.data <= referencia), Decimal(0)
    )
    base = exato(conta.saldo_referencia) - soma_ate_referencia

    pontos = []  # (data, diferença)
    dias_ordem_incerta = []
    acumulado = Decimal(0)
    for dia, do_dia in groupby(transacoes, key=lambda t: t.data):
        do_dia = list(do_dia)
        acumulado += sum((exato(t.valor) for t in do_dia), Decimal(0))
        if all(t.saldo is None for t in do_dia):
            continue
        calculado = _cent(base + acumulado)
        # O esperado é o saldo do banco no ponto anterior mais os movimentos
        # desde então: o calculado menos a diferença que já vinha de trás. Se a
        # referência ficar pelo meio (ou não houver ponto anterior), a
        # diferença conhecida é a dela, 0
        if not pontos or pontos[-1][0] < referencia <= dia:
            anterior = Decimal(0)
        else:
            anterior = pontos[-1][1]
        banco, incerta = _saldo_fim_do_dia(do_dia, calculado - anterior)
        pontos.append((dia, calculado - banco))
        if incerta:
            dias_ordem_incerta.append(dia)

    # O saldo de referência também foi dado pelo utilizador, com diferença 0.
    # Se o banco tiver saldo nesse dia, vale o do banco, e uma diferença aí é
    # do próprio saldo de referência: fica num intervalo sem início
    intervalos = []
    na_referencia = next((dif for dia, dif in pontos if dia == referencia), None)
    if na_referencia is None:
        pontos.append((referencia, Decimal(0)))
        pontos.sort(key=lambda p: p[0])
    elif na_referencia != 0:
        intervalos.append({"de": None, "ate": referencia, "variacao": float(na_referencia)})

    # Só entre pontos seguidos: antes do primeiro não se sabe qual era a
    # diferença, e para trás da referência mede-se a partir dela
    for (de, dif_de), (ate, dif_ate) in pairwise(pontos):
        if dif_ate != dif_de:
            intervalos.append({"de": de, "ate": ate, "variacao": float(dif_ate - dif_de)})
    intervalos.sort(key=lambda i: i["ate"])

    data_ultimo_saldo = pontos[-1][0]
    sugerir_saldo = bool(transacoes) and transacoes[-1].data - data_ultimo_saldo > timedelta(
        days=DIAS_SALDO_ANTIGO
    )

    return {
        "conta_id": conta.id,
        "diferenca_atual": float(pontos[-1][1]),
        "data_ultimo_saldo": data_ultimo_saldo,
        "intervalos": intervalos,
        "dias_ordem_incerta": dias_ordem_incerta,
        "sugerir_saldo": sugerir_saldo,
    }

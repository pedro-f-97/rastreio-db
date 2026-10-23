"""Verificação do saldo de uma conta contra os saldos do banco.

Os saldos esperados são os do campo `saldo` das transacções: os do extracto,
ou os que se escrevem à mão nas contas cujo extracto não os traz. O saldo de
referência da conta também é um ponto de controlo, com diferença 0 por
definição. Compara-se ao fim de cada dia, porque a BD não guarda a ordem das
transacções dentro do dia.
"""

from datetime import timedelta
from decimal import Decimal
from itertools import groupby

from sqlalchemy.orm import Session

from database import Conta as ContaModel, Transacao as TransacaoModel
from servicos.dinheiro import CENTIMO, exato

# Um saldo mais antigo do que isto, contado da última transacção, sugere
# escrever um novo
DIAS_SALDO_ANTIGO = 31


def _cent(x) -> Decimal:
    return exato(x).quantize(CENTIMO)


def _saldo_fim_do_dia(transacoes, calculado: Decimal) -> tuple[Decimal, bool]:
    """O saldo do banco no fim do dia, e se a ordem ficou incerta.

    O saldo antes de cada transacção é o seu saldo menos o seu valor; a última
    do dia é aquela cujo saldo não é o «saldo antes» de nenhuma outra. Sem
    exactamente uma candidata (uma transacção de 0 €, um saldo repetido), fica
    o saldo mais próximo do calculado, e a ordem é incerta.
    """
    com_saldo = [t for t in transacoes if t.saldo is not None]
    saldos = [_cent(t.saldo) for t in com_saldo]
    antes = {_cent(t.saldo) - _cent(t.valor) for t in com_saldo}
    candidatos = [s for s in saldos if s not in antes]
    if len(candidatos) == 1:
        return candidatos[0], False
    return min(saldos, key=lambda s: abs(calculado - s)), True


def verificar_saldo(db: Session, conta: ContaModel) -> dict:
    """Compara o saldo calculado com o do banco em cada dia com saldo.

    Devolve a diferença (calculado − banco) no último ponto de controlo, os
    intervalos ]de, ate] em que a diferença mudou, os dias com a ordem incerta
    e se se deve sugerir escrever um saldo novo.
    """
    transacoes = (
        db.query(TransacaoModel)
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
        banco, incerta = _saldo_fim_do_dia(do_dia, calculado)
        pontos.append((dia, calculado - banco))
        if incerta:
            dias_ordem_incerta.append(dia)

    # O saldo de referência também foi dado pelo utilizador, com diferença 0;
    # se o banco tiver saldo nesse dia, vale o do banco
    if referencia not in {d for d, _ in pontos}:
        pontos.append((referencia, Decimal(0)))
        pontos.sort(key=lambda p: p[0])

    intervalos = []
    anterior_data, anterior_dif = None, Decimal(0)
    for dia, dif in pontos:
        if dif != anterior_dif:
            intervalos.append(
                {"de": anterior_data, "ate": dia, "variacao": float(dif - anterior_dif)}
            )
        anterior_data, anterior_dif = dia, dif

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

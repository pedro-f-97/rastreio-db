from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import (
    Ativo as AtivoModel,
    Conta as ContaModel,
    MovimentoAtivo as MovimentoAtivoModel,
    PrecoAtivo as PrecoAtivoModel,
    Transacao as TransacaoModel,
)
from servicos.dinheiro import arredondar, exato

# Abaixo disto, um lote ou uma venda consideram-se esgotados
TOLERANCIA = Decimal("1e-9")


def _resumo_valor_ativo(ativo, movimentos, preco) -> dict:
    """Núcleo partilhado por resumo_ativo e pela evolução.

    Parâmetros
    ----------
    ativo : Ativo
        O ativo (tem_unidades determina o ramo de cálculo).
    movimentos : list[MovimentoAtivo]
        Movimentos já filtrados por data.
    preco : PrecoAtivo | None
        Preço mais recente (até data_alvo para a evolução).

    Retorna
    -------
    dict com: quantidade, custo_base, realizado, valor

    As contas são feitas em `Decimal`, a partir do valor escrito de cada
    campo, para que um empate no meio cêntimo seja visto como tal ao
    arredondar. O resultado volta em float.
    """
    if not ativo.tipo.tem_unidades:
        # --- RAMO SEM UNIDADES (casa, carro, bem) ---
        # O preço registado é o valor total do ativo, não um preço unitário.
        custo_base = Decimal(0)
        realizado = Decimal(0)
        vendido = False

        for m in movimentos:
            valor_m = abs(exato(m.valor_total or 0))

            if m.tipo_movimento.value == "compra":
                custo_base += valor_m
                vendido = False

            elif m.tipo_movimento.value == "venda":
                # Venda total de uma só vez. Ganho = encaixe menos custo.
                realizado += valor_m - custo_base
                custo_base = Decimal(0)
                vendido = True

            elif m.tipo_movimento.value == "dividendo":
                # Assumido positivo; confirmar com primeiro dividendo real
                realizado += valor_m

        if vendido or custo_base <= 0:
            valor = 0.0
        elif preco:
            valor = arredondar(preco.preco)
        else:
            # Sem avaliação registada, o bem vale o custo de aquisição
            valor = arredondar(custo_base)

        return {
            "quantidade": 0.0,
            "custo_base": float(custo_base),
            "realizado": float(realizado),
            "valor": valor,
        }

    # --- RAMO COM UNIDADES (FIFO) ---
    # Pressuposto: valor_total já inclui a comissão (confirmado nos dados:
    # valor_total ≈ preco_unitario × quantidade + comissao).
    # Cada lote guarda o custo total e não o unitário: a divisão só se faz ao
    # consumir, depois de multiplicar, para não perder exatidão.
    lotes = []
    realizado = Decimal(0)

    for m in movimentos:
        q = exato(m.quantidade or 0)
        valor_m = abs(exato(m.valor_total or 0))

        if m.tipo_movimento.value == "compra":
            if q > 0:
                lotes.append({"quantidade": q, "custo": valor_m})

        elif m.tipo_movimento.value == "venda":
            if q <= 0:
                continue

            por_consumir = q
            custo_vendido = Decimal(0)
            while por_consumir > TOLERANCIA and lotes:
                lote = lotes[0]
                consumida = min(por_consumir, lote["quantidade"])
                custo_consumido = lote["custo"] * consumida / lote["quantidade"]
                custo_vendido += custo_consumido
                lote["custo"] -= custo_consumido
                lote["quantidade"] -= consumida
                por_consumir -= consumida
                if lote["quantidade"] <= TOLERANCIA:
                    lotes.pop(0)

            q_efetiva = q - por_consumir
            valor_efetivo = valor_m * q_efetiva / q if q > 0 else Decimal(0)
            realizado += valor_efetivo - custo_vendido

        elif m.tipo_movimento.value == "dividendo":
            realizado += valor_m

    quantidade = sum((lote["quantidade"] for lote in lotes), Decimal(0))
    custo_base = sum((lote["custo"] for lote in lotes), Decimal(0))
    if quantidade <= 0:
        valor = 0.0
    elif preco:
        valor = arredondar(quantidade * exato(preco.preco))
    else:
        # Sem preço registado, vale o custo das unidades em carteira
        valor = arredondar(custo_base)

    return {
        "quantidade": float(quantidade),
        "custo_base": float(custo_base),
        "realizado": float(realizado),
        "valor": valor,
    }


def primeira_sobre_venda(movimentos):
    """Primeira venda que excede as unidades em carteira, pela ordem do FIFO.

    `movimentos` vem ordenado por (data, id), como em `_resumo_valor_ativo`.
    Devolve `(venda, quantidade_vendida, posicao_antes_da_venda)`, ou `None` se
    nenhuma exceder.
    Só faz sentido para ativos com unidades.
    """
    posicao = 0.0
    for m in movimentos:
        q = float(m.quantidade or 0)
        if q <= 0:
            continue
        if m.tipo_movimento.value == "compra":
            posicao += q
        elif m.tipo_movimento.value == "venda":
            if q - posicao > 1e-9:
                return m, q, posicao
            posicao -= q
    return None


def saldo_conta_em(db: Session, conta: ContaModel, data_alvo: date) -> float:
    """Saldo de uma conta no fim de `data_alvo`, arredondado ao cêntimo.

    É o único cálculo do saldo: serve o saldo de hoje (`/contas/{id}/saldo`) e
    a liquidez da evolução. O saldo de referência é o do fim desse dia. Para a
    frente, somam-se as transacções em ]referência, data_alvo]; para trás,
    tiram-se as de ]data_alvo, referência], que ainda não tinham acontecido.
    """
    if data_alvo >= conta.data_referencia:
        de, ate, sinal = conta.data_referencia, data_alvo, 1
    else:
        de, ate, sinal = data_alvo, conta.data_referencia, -1
    soma_transacoes = (
        db.query(func.sum(TransacaoModel.valor))
        .filter(
            TransacaoModel.conta_id == conta.id,
            TransacaoModel.data > de,
            TransacaoModel.data <= ate,
        )
        .scalar()
        or 0.0
    )
    return arredondar(conta.saldo_referencia + sinal * soma_transacoes)


def calcular_patrimonio_em(
    db: Session, data_alvo: date, precos_futuros: bool = False, com_valorizacao: bool = False
) -> dict:
    # --- Liquidez ---
    # Todas as contas, activas ou não: desactivar só esconde a conta das listas,
    # e o dinheiro que lá esteve continua a fazer parte do histórico. Soma os
    # saldos já arredondados, como o cartão Liquidez da página Património
    contas = db.query(ContaModel).all()
    liquidez = sum(saldo_conta_em(db, conta, data_alvo) for conta in contas)

    # --- Investimentos e Ativos físicos ---
    investimentos = 0.0
    ativos_fisicos = 0.0
    # Ganho acumulado dos ativos: o que valem acima do custo, mais o já
    # realizado em vendas e dividendos (que a venda passa para a liquidez)
    valorizacao = Decimal(0)
    # O tipo vem na mesma query: sem isto, cada ponto lia cada tipo à parte
    ativos = db.query(AtivoModel).options(joinedload(AtivoModel.tipo)).all()

    for ativo in ativos:
        movimentos = (
            db.query(MovimentoAtivoModel)
            .filter(
                MovimentoAtivoModel.ativo_id == ativo.id,
                MovimentoAtivoModel.data <= data_alvo,
            )
            .order_by(MovimentoAtivoModel.data, MovimentoAtivoModel.id)
            .all()
        )

        # Os pontos passados usam o preço dessa data; o de hoje usa o mais
        # recente, mesmo com data futura, como o resumo do ativo
        q_preco = db.query(PrecoAtivoModel).filter(PrecoAtivoModel.ativo_id == ativo.id)
        if not precos_futuros:
            q_preco = q_preco.filter(PrecoAtivoModel.data <= data_alvo)
        preco = q_preco.order_by(PrecoAtivoModel.data.desc()).first()

        # Partilha a mesma lógica FIFO / sem-unidades que resumo_ativo
        resultado = _resumo_valor_ativo(ativo, movimentos, preco)
        valor = resultado["valor"]
        valorizacao += exato(valor) - exato(resultado["custo_base"]) + exato(resultado["realizado"])

        if ativo.contabilizacao.value == "investimento":
            investimentos += valor
        else:
            ativos_fisicos += valor

    # O total soma os componentes já arredondados, para bater certo com eles
    liquidez = arredondar(liquidez)
    investimentos = arredondar(investimentos)
    ativos_fisicos = arredondar(ativos_fisicos)
    ponto = {
        "data": str(data_alvo),
        "liquidez": liquidez,
        "investimentos": investimentos,
        "ativos_fisicos": ativos_fisicos,
        "total": arredondar(liquidez + investimentos + ativos_fisicos),
    }
    if com_valorizacao:
        ponto["valorizacao"] = arredondar(valorizacao)
    return ponto


def gerar_evolucao(
    db: Session, data_inicio: date, data_fim: date, hoje: date, com_valorizacao: bool = False
) -> list[dict]:
    from calendar import monthrange

    pontos = []
    cursor = date(data_inicio.year, data_inicio.month, 1)
    while cursor <= data_fim:
        ultimo_dia = monthrange(cursor.year, cursor.month)[1]
        fim_mes = min(date(cursor.year, cursor.month, ultimo_dia), data_fim)
        pontos.append(
            calcular_patrimonio_em(
                db, fim_mes, precos_futuros=fim_mes >= hoje, com_valorizacao=com_valorizacao
            )
        )
        cursor = date(cursor.year + (cursor.month == 12), (cursor.month % 12) + 1, 1)

    return pontos


# Abaixo disto, a recta diz pouco e o crescimento não se mostra
MESES_MINIMOS = 3


def _inclinacao(valores: list[float]) -> float:
    """Inclinação da recta dos mínimos quadrados, por passo de `x` (um mês)."""
    n = len(valores)
    media_x = (n - 1) / 2
    media_y = sum(valores) / n
    numerador = sum((x - media_x) * (y - media_y) for x, y in enumerate(valores))
    denominador = sum((x - media_x) ** 2 for x in range(n))
    return numerador / denominador


def calcular_crescimento(db: Session, ano: int | None, hoje: date) -> dict:
    """Quanto o património cresce por mês, pela tendência dos fins de mês.

    O período vai do mês da primeira transação (ou de janeiro de `ano`) ao
    último mês completo antes de `hoje` (ou dezembro de `ano`): o mês em curso
    fica de fora. Separa-se o crescimento em valorização (o ganho acumulado dos
    ativos) e no que se poupa (o resto). A recta é linear nos valores, por isso
    as duas inclinações somam a do total; a poupança calcula-se como a
    diferença das já arredondadas, para somarem ao cêntimo.
    """
    fim = date(hoje.year, hoje.month, 1) - timedelta(days=1)
    primeira = db.query(func.min(TransacaoModel.data)).scalar()
    inicio = primeira
    if ano is not None and primeira is not None:
        inicio = max(primeira, date(ano, 1, 1))
        fim = min(fim, date(ano, 12, 31))

    pontos = []
    if inicio is not None and inicio <= fim:
        pontos = gerar_evolucao(db, inicio, fim, hoje, com_valorizacao=True)

    resultado = {
        "de": pontos[0]["data"] if pontos else None,
        "ate": pontos[-1]["data"] if pontos else None,
        "meses": len(pontos),
        "total": None,
        "poupanca": None,
        "valorizacao": None,
    }
    if len(pontos) < MESES_MINIMOS:
        return resultado

    total = arredondar(_inclinacao([p["total"] for p in pontos]))
    valorizacao = arredondar(_inclinacao([p["valorizacao"] for p in pontos]))
    resultado["total"] = total
    resultado["valorizacao"] = valorizacao
    resultado["poupanca"] = arredondar(exato(total) - exato(valorizacao))
    return resultado

from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import (
    Ativo as AtivoModel,
    MovimentoAtivo as MovimentoAtivoModel,
    PrecoAtivo as PrecoAtivoModel,
    Conta as ContaModel,
    Transacao as TransacaoModel,
)


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
    """
    if not ativo.tipo.tem_unidades:
        # --- RAMO SEM UNIDADES (casa, carro, bem) ---
        # O preço registado é o valor total do ativo, não um preço unitário.
        custo_base = 0.0
        realizado = 0.0
        vendido = False

        for m in movimentos:
            valor_m = abs(float(m.valor_total or 0))

            if m.tipo_movimento.value == "compra":
                custo_base += valor_m
                vendido = False

            elif m.tipo_movimento.value == "venda":
                # Venda total de uma só vez. Ganho = encaixe menos custo.
                realizado += valor_m - custo_base
                custo_base = 0.0
                vendido = True

            elif m.tipo_movimento.value == "dividendo":
                # Assumido positivo; confirmar com primeiro dividendo real
                realizado += valor_m

        if vendido or custo_base <= 0:
            valor = 0.0
        else:
            valor = round(float(preco.preco), 2) if preco else 0.0

        return {"quantidade": 0.0, "custo_base": custo_base, "realizado": realizado, "valor": valor}

    # --- RAMO COM UNIDADES (FIFO) ---
    # Pressuposto: valor_total já inclui a comissão (confirmado nos dados:
    # valor_total ≈ preco_unitario × quantidade + comissao).
    lotes = []
    realizado = 0.0

    for m in movimentos:
        q = float(m.quantidade or 0)
        valor_m = abs(float(m.valor_total or 0))

        if m.tipo_movimento.value == "compra":
            if q > 0:
                lotes.append({"quantidade": q, "custo_unitario": valor_m / q})

        elif m.tipo_movimento.value == "venda":
            if q <= 0:
                continue

            por_consumir = q
            custo_vendido = 0.0
            while por_consumir > 1e-9 and lotes:
                lote = lotes[0]
                consumida = min(por_consumir, lote["quantidade"])
                custo_vendido += consumida * lote["custo_unitario"]
                lote["quantidade"] -= consumida
                por_consumir -= consumida
                if lote["quantidade"] <= 1e-9:
                    lotes.pop(0)

            q_efetiva = q - por_consumir
            valor_efetivo = valor_m * (q_efetiva / q) if q > 0 else 0.0
            realizado += valor_efetivo - custo_vendido

        elif m.tipo_movimento.value == "dividendo":
            realizado += valor_m

    quantidade = sum(l["quantidade"] for l in lotes)
    custo_base = sum(l["quantidade"] * l["custo_unitario"] for l in lotes)
    valor = round(quantidade * float(preco.preco), 2) if (preco and quantidade > 0) else 0.0

    return {"quantidade": quantidade, "custo_base": custo_base, "realizado": realizado, "valor": valor}


def calcular_patrimonio_em(db: Session, data_alvo: date) -> dict:
    # --- Liquidez ---
    liquidez = 0.0
    contas = db.query(ContaModel).filter(ContaModel.ativa == True).all()
    for conta in contas:
        if conta.data_referencia > data_alvo:
            continue
        soma_transacoes = db.query(func.sum(TransacaoModel.valor)).filter(
            TransacaoModel.conta_id == conta.id,
            TransacaoModel.data > conta.data_referencia,
            TransacaoModel.data <= data_alvo,
        ).scalar() or 0.0
        liquidez += conta.saldo_referencia + soma_transacoes

    # --- Investimentos e Ativos físicos ---
    investimentos = 0.0
    ativos_fisicos = 0.0
    ativos = db.query(AtivoModel).all()

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

        preco = (
            db.query(PrecoAtivoModel)
            .filter(
                PrecoAtivoModel.ativo_id == ativo.id,
                PrecoAtivoModel.data <= data_alvo,
            )
            .order_by(PrecoAtivoModel.data.desc())
            .first()
        )

        # Partilha a mesma lógica FIFO / sem-unidades que resumo_ativo
        resultado = _resumo_valor_ativo(ativo, movimentos, preco)
        valor = resultado["valor"]

        if ativo.contabilizacao.value == "investimento":
            investimentos += valor
        else:
            ativos_fisicos += valor

    total = liquidez + investimentos + ativos_fisicos
    return {
        "data": str(data_alvo),
        "liquidez": round(liquidez, 2),
        "investimentos": round(investimentos, 2),
        "ativos_fisicos": round(ativos_fisicos, 2),
        "total": round(total, 2),
    }


def gerar_evolucao(db: Session, data_inicio: date, data_fim: date) -> list[dict]:
    from calendar import monthrange

    pontos = []
    cursor = date(data_inicio.year, data_inicio.month, 1)
    while cursor <= data_fim:
        ultimo_dia = monthrange(cursor.year, cursor.month)[1]
        fim_mes = min(date(cursor.year, cursor.month, ultimo_dia), data_fim)
        pontos.append(calcular_patrimonio_em(db, fim_mes))
        cursor = date(cursor.year + (cursor.month == 12), (cursor.month % 12) + 1, 1)

    return pontos
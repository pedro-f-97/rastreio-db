from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import Ativo as AtivoModel, MovimentoAtivo as MovimentoAtivoModel, PrecoAtivo as PrecoAtivoModel, Conta as ContaModel, Transacao as TransacaoModel


def calcular_patrimonio_em(db: Session, data_alvo: date) -> dict:
    # --- Liquidez ---
    liquidez = 0.0
    contas = db.query(ContaModel).filter(ContaModel.ativa == True).all()
    for conta in contas:
        if conta.data_referencia > data_alvo:
            continue  # conta ainda não existia nesta data
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
            .filter(MovimentoAtivoModel.ativo_id == ativo.id, MovimentoAtivoModel.data <= data_alvo)
            .all()
        )
        quantidade = 0.0
        for m in movimentos:
            if m.tipo_movimento.value == "compra":
                quantidade += float(m.quantidade or 0)
            elif m.tipo_movimento.value == "venda":
                quantidade -= float(m.quantidade or 0)

        if quantidade <= 0:
            continue

        preco = (
            db.query(PrecoAtivoModel)
            .filter(PrecoAtivoModel.ativo_id == ativo.id, PrecoAtivoModel.data <= data_alvo)
            .order_by(PrecoAtivoModel.data.desc())
            .first()
        )
        valor = quantidade * float(preco.preco) if preco else 0.0

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
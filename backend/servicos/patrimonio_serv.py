from datetime import date
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


def calcular_patrimonio_em(db: Session, data_alvo: date, precos_futuros: bool = False) -> dict:
    # --- Liquidez ---
    liquidez = 0.0
    contas = db.query(ContaModel).filter(ContaModel.ativa == True).all()
    for conta in contas:
        if conta.data_referencia > data_alvo:
            continue
        soma_transacoes = (
            db.query(func.sum(TransacaoModel.valor))
            .filter(
                TransacaoModel.conta_id == conta.id,
                TransacaoModel.data > conta.data_referencia,
                TransacaoModel.data <= data_alvo,
            )
            .scalar()
            or 0.0
        )
        liquidez += conta.saldo_referencia + soma_transacoes

    # --- Investimentos e Ativos físicos ---
    investimentos = 0.0
    ativos_fisicos = 0.0
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

        if ativo.contabilizacao.value == "investimento":
            investimentos += valor
        else:
            ativos_fisicos += valor

    # O total soma os componentes já arredondados, para bater certo com eles
    liquidez = arredondar(liquidez)
    investimentos = arredondar(investimentos)
    ativos_fisicos = arredondar(ativos_fisicos)
    return {
        "data": str(data_alvo),
        "liquidez": liquidez,
        "investimentos": investimentos,
        "ativos_fisicos": ativos_fisicos,
        "total": arredondar(liquidez + investimentos + ativos_fisicos),
    }


def gerar_evolucao(db: Session, data_inicio: date, data_fim: date, hoje: date) -> list[dict]:
    from calendar import monthrange

    pontos = []
    cursor = date(data_inicio.year, data_inicio.month, 1)
    while cursor <= data_fim:
        ultimo_dia = monthrange(cursor.year, cursor.month)[1]
        fim_mes = min(date(cursor.year, cursor.month, ultimo_dia), data_fim)
        pontos.append(calcular_patrimonio_em(db, fim_mes, precos_futuros=fim_mes >= hoje))
        cursor = date(cursor.year + (cursor.month == 12), (cursor.month % 12) + 1, 1)

    return pontos

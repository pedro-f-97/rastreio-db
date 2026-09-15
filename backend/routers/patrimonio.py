from datetime import date
from typing import List

import schemas
from database import Ativo as AtivoModel
from database import MovimentoAtivo as MovimentoAtivoModel
from database import PrecoAtivo as PrecoAtivoModel
from database import Transacao as TransacaoModel
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from servicos.patrimonio_serv import gerar_evolucao
from sqlalchemy import func, text
from sqlalchemy.orm import Session

router = APIRouter(prefix="/patrimonio", tags=["patrimonio"])

# --- PENDENTES ---

@router.get("/pendentes", response_model=List[schemas.TransacaoPendente])
def listar_pendentes(db: Session = Depends(get_db)):
    resultado = db.execute(text("""
        SELECT t.id, t.data, t.descricao, t.valor, t.subcategoria_id
        FROM transacoes t
        JOIN subcategorias s ON t.subcategoria_id = s.id
        LEFT JOIN movimentos_ativo m ON m.transacao_id = t.id
        WHERE s.trata_patrimonio = 1
        AND m.id IS NULL
        ORDER BY t.data DESC
    """)).mappings().all()
    return [dict(r) for r in resultado]


# --- ATIVOS ---

@router.get("/ativos", response_model=List[schemas.Ativo])
def listar_ativos(db: Session = Depends(get_db)):
    return db.query(AtivoModel).order_by(AtivoModel.tipo_id, AtivoModel.nome).all()


@router.post("/ativos", response_model=schemas.Ativo)
def criar_ativo(payload: schemas.AtivoCreate, db: Session = Depends(get_db)):
    # Verifica duplicado por símbolo
    if payload.simbolo:
        existente = db.query(AtivoModel).filter(AtivoModel.simbolo == payload.simbolo).first()
        if existente:
            raise HTTPException(status_code=409, detail="Já existe um ativo com este símbolo.")
    ativo = AtivoModel(**payload.model_dump())
    db.add(ativo)
    db.commit()
    db.refresh(ativo)
    return ativo

@router.put("/ativos/{ativo_id}", response_model=schemas.Ativo)
def editar_ativo(ativo_id: int, payload: schemas.AtivoUpdate, db: Session = Depends(get_db)):
    ativo = db.query(AtivoModel).filter(AtivoModel.id == ativo_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    if payload.simbolo:
        existente = (
            db.query(AtivoModel)
            .filter(AtivoModel.simbolo == payload.simbolo, AtivoModel.id != ativo_id)
            .first()
        )
        if existente:
            raise HTTPException(status_code=409, detail="Já existe um ativo com este símbolo.")
    if payload.nome is not None:
        ativo.nome = payload.nome
    if payload.simbolo is not None:
        ativo.simbolo = payload.simbolo
    db.commit()
    db.refresh(ativo)
    return ativo

@router.delete("/ativos/{ativo_id}", status_code=204)
def eliminar_ativo(ativo_id: int, db: Session = Depends(get_db)):
    ativo = db.query(AtivoModel).filter(AtivoModel.id == ativo_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    db.query(MovimentoAtivoModel).filter(MovimentoAtivoModel.ativo_id == ativo_id).delete()
    db.query(PrecoAtivoModel).filter(PrecoAtivoModel.ativo_id == ativo_id).delete()
    db.delete(ativo)
    db.commit()


# --- MOVIMENTOS ---

@router.post("/movimentos", response_model=schemas.MovimentoAtivo)
def criar_movimento(payload: schemas.MovimentoAtivoCreate, db: Session = Depends(get_db)):
    ativo = db.query(AtivoModel).filter(AtivoModel.id == payload.ativo_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    movimento = MovimentoAtivoModel(**payload.model_dump())
    db.add(movimento)
    db.commit()
    db.refresh(movimento)

    if payload.tipo_movimento.value == "compra" and payload.preco_unitario is not None:
        existente = (
            db.query(PrecoAtivoModel)
            .filter(PrecoAtivoModel.ativo_id == payload.ativo_id, PrecoAtivoModel.data == payload.data)
            .first()
        )
        if existente:
            existente.preco = payload.preco_unitario
        else:
            db.add(PrecoAtivoModel(ativo_id=payload.ativo_id, data=payload.data, preco=payload.preco_unitario))
        db.commit()

    return movimento

@router.delete("/movimentos/{movimento_id}", status_code=204)
def eliminar_movimento(movimento_id: int, db: Session = Depends(get_db)):
    movimento = db.query(MovimentoAtivoModel).filter(MovimentoAtivoModel.id == movimento_id).first()
    if not movimento:
        raise HTTPException(status_code=404, detail="Movimento não encontrado.")
    db.delete(movimento)
    db.commit()


@router.get("/ativos/{ativo_id}/movimentos", response_model=List[schemas.MovimentoAtivo])
def listar_movimentos(ativo_id: int, db: Session = Depends(get_db)):
    ativo = db.query(AtivoModel).filter(AtivoModel.id == ativo_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    return (
        db.query(MovimentoAtivoModel)
        .filter(MovimentoAtivoModel.ativo_id == ativo_id)
        .order_by(MovimentoAtivoModel.data)
        .all()
    )


# --- PREÇOS ---

@router.post("/precos", response_model=schemas.PrecoAtivo)
def registar_preco(payload: schemas.PrecoAtivoCreate, db: Session = Depends(get_db)):
    ativo = db.query(AtivoModel).filter(AtivoModel.id == payload.ativo_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")
    # Upsert: se já existe preço para esta data, actualiza
    existente = (
        db.query(PrecoAtivoModel)
        .filter(PrecoAtivoModel.ativo_id == payload.ativo_id, PrecoAtivoModel.data == payload.data)
        .first()
    )
    if existente:
        existente.preco = payload.preco
        db.commit()
        db.refresh(existente)
        return existente
    preco = PrecoAtivoModel(**payload.model_dump())
    db.add(preco)
    db.commit()
    db.refresh(preco)
    return preco

@router.get("/ativos/{ativo_id}/resumo")
def resumo_ativo(ativo_id: int, db: Session = Depends(get_db)):
    ativo = db.query(AtivoModel).filter(AtivoModel.id == ativo_id).first()
    if not ativo:
        raise HTTPException(status_code=404, detail="Ativo não encontrado.")

    # Ordem determinística — o custo médio ponderado depende dela
    # quando há vendas antes de compras suficientes (dados importados).
    movimentos = (
        db.query(MovimentoAtivoModel)
        .filter(MovimentoAtivoModel.ativo_id == ativo_id)
        .order_by(MovimentoAtivoModel.data, MovimentoAtivoModel.id)
        .all()
    )

    # Convenção de sinais (mantida):
    #   - valor_total de "compra" chega NEGATIVO (saída de dinheiro).
    #   - valor_total de "venda" chega POSITIVO (entrada de dinheiro).
    # Internamente usamos abs() para o custo; o campo 'custo_total' do
    # retorno volta a ficar NEGATIVO para não partir o frontend.
    quantidade = 0.0
    custo_base = 0.0      # positivo por dentro: custo das unidades detidas
    realizado = 0.0       # mais/menos-valia já concretizada (vendas)

    for m in movimentos:
        q = float(m.quantidade or 0)
        valor = abs(float(m.valor_total or 0))

        if m.tipo_movimento.value == "compra":
            quantidade += q
            custo_base += valor

        elif m.tipo_movimento.value == "venda":
            if quantidade <= 0:
                # Venda sem posição: dados inconsistentes. Ignorar é mais
                # seguro do que propagar quantidades negativas silenciosas.
                continue

            q_efetiva = min(q, quantidade)
            custo_medio = custo_base / quantidade
            custo_vendido = custo_medio * q_efetiva

            # Se q > quantidade, proporcionaliza o encaixe ao que foi
            # efetivamente vendido (evita realizado inflacionado).
            valor_efetivo = valor * (q_efetiva / q) if q > 0 else 0.0

            realizado += valor_efetivo - custo_vendido
            custo_base -= custo_vendido
            quantidade -= q_efetiva

    preco_atual = (
        db.query(PrecoAtivoModel)
        .filter(PrecoAtivoModel.ativo_id == ativo_id)
        .order_by(PrecoAtivoModel.data.desc())
        .first()
    )

    if preco_atual:
        valor_atual = round(quantidade * float(preco_atual.preco), 2)
        latente = round(valor_atual - custo_base, 2)
    else:
        valor_atual = None
        latente = None

    realizado = round(realizado, 2)

    # (= valor_atual + custo_total, com custo_total negativo); agora é
    # realizado + latente. É a correção pedida — sem isto, o número
    # continua errado sempre que exista uma venda.
    mais_menos_valia = round(realizado + (latente or 0.0), 2)

    return {
        "ativo_id": ativo_id,
        "quantidade": round(quantidade, 6),
        # Negativo, como antes — o frontend não precisa de mexer.
        "custo_total": round(-custo_base, 2),
        "preco_atual": float(preco_atual.preco) if preco_atual else None,
        "data_preco": str(preco_atual.data) if preco_atual else None,
        "valor_atual": valor_atual,
        "realizado": realizado,
        "latente": latente,
        "mais_menos_valia": mais_menos_valia,
    }

@router.get("/evolucao")
def evolucao_patrimonio(
    data_inicio: date | None = None,
    data_fim: date | None = None,
    db: Session = Depends(get_db),
):
    if data_fim is None:
        data_fim = date.today()

    if data_inicio is None:
        primeira = db.query(func.min(TransacaoModel.data)).scalar()
        data_inicio = primeira or data_fim

    assert data_inicio is not None
    assert data_fim is not None

    return gerar_evolucao(db, data_inicio, data_fim)
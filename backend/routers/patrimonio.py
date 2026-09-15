from datetime import date
from typing import List

import schemas
from database import Ativo as AtivoModel
from database import MovimentoAtivo as MovimentoAtivoModel
from database import PrecoAtivo as PrecoAtivoModel
from database import Transacao as TransacaoModel
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from servicos.patrimonio_serv import gerar_evolucao, _resumo_valor_ativo
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

    movimentos = (
        db.query(MovimentoAtivoModel)
        .filter(MovimentoAtivoModel.ativo_id == ativo_id)
        .order_by(MovimentoAtivoModel.data, MovimentoAtivoModel.id)
        .all()
    )

    preco_atual = (
        db.query(PrecoAtivoModel)
        .filter(PrecoAtivoModel.ativo_id == ativo_id)
        .order_by(PrecoAtivoModel.data.desc())
        .first()
    )

    # Chama a função partilhada — zero duplicação de FIFO
    resultado = _resumo_valor_ativo(ativo, movimentos, preco_atual)

    realizado = round(resultado["realizado"], 2)
    valor_atual = resultado["valor"]
    custo_base = resultado["custo_base"]

    if preco_atual and valor_atual is not None:
        latente = round(valor_atual - custo_base, 2)
    else:
        latente = None

    # mais_menos_valia = realizado + latente
    # (o antigo era valor_atual + custo_total, onde custo_total era negativo).
    # Esta fórmula mantém a invariante: valor total do ativo =
    #   realizado (vendas concretizadas) + latente (valorização não realizada).
    mais_menos_valia = round(realizado + (latente or 0.0), 2)

    return {
        "ativo_id": ativo_id,
        "quantidade": round(resultado["quantidade"], 6),
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
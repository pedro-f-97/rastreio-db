from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from database import SessionLocal, Ativo as AtivoModel, MovimentoAtivo as MovimentoAtivoModel, PrecoAtivo as PrecoAtivoModel
import schemas

router = APIRouter(prefix="/patrimonio", tags=["patrimonio"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    return db.query(AtivoModel).order_by(AtivoModel.tipo, AtivoModel.nome).all()


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
    return movimento


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
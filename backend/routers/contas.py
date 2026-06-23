from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from database import SessionLocal, Conta as ContaModel
import schemas

router = APIRouter(prefix="/contas", tags=["contas"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=List[schemas.Conta])
def listar_contas(db: Session = Depends(get_db)):
    return db.query(ContaModel).order_by(ContaModel.nome).all()


@router.post("/", response_model=schemas.Conta)
def criar_conta(payload: schemas.ContaCreate, db: Session = Depends(get_db)):
    existente = db.query(ContaModel).filter(ContaModel.nome == payload.nome).first()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este nome.")
    conta = ContaModel(**payload.model_dump())
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.put("/{conta_id}", response_model=schemas.Conta)
def actualizar_conta(conta_id: int, payload: schemas.ContaUpdate, db: Session = Depends(get_db)):
    conta = db.query(ContaModel).filter(ContaModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(conta, campo, valor)
    db.commit()
    db.refresh(conta)
    return conta


@router.delete("/{conta_id}")
def apagar_conta(conta_id: int, db: Session = Depends(get_db)):
    conta = db.query(ContaModel).filter(ContaModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    db.delete(conta)
    db.commit()
    return {"ok": True}


@router.get("/{conta_id}/saldo")
def saldo_conta(conta_id: int, db: Session = Depends(get_db)):
    conta = db.query(ContaModel).filter(ContaModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    resultado = db.execute(text("""
        SELECT COALESCE(SUM(valor), 0)
        FROM transacoes
        WHERE conta_id = :conta_id
        AND data >= :data_referencia
    """), {"conta_id": conta_id, "data_referencia": str(conta.data_referencia)}).scalar()
    saldo = round(float(conta.saldo_referencia) + float(resultado or 0), 2)
    return {
        "conta_id": conta_id,
        "nome": conta.nome,
        "saldo_referencia": float(conta.saldo_referencia),
        "data_referencia": str(conta.data_referencia),
        "saldo_atual": saldo,
    }
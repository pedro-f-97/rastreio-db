from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, TipoAtivo
from schemas import TipoAtivoCreate

router = APIRouter(prefix="/tipos-ativo", tags=["tipos-ativo"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def listar_tipos_ativo(db: Session = Depends(get_db)):
    return db.query(TipoAtivo).order_by(TipoAtivo.nome).all()

@router.post("/")
def criar_tipo_ativo(tipo: TipoAtivoCreate, db: Session = Depends(get_db)):
    existente = db.query(TipoAtivo).filter(TipoAtivo.nome == tipo.nome).first()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe um tipo de ativo com este nome.")
    novo = TipoAtivo(nome=tipo.nome, tem_unidades=tipo.tem_unidades)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@router.put("/{tipo_id}")
def renomear_tipo_ativo(tipo_id: int, tipo: TipoAtivoCreate, db: Session = Depends(get_db)):
    existente = db.query(TipoAtivo).filter(TipoAtivo.id == tipo_id).first()
    if not existente:
        raise HTTPException(status_code=404, detail="Tipo de ativo não encontrado.")
    existente.nome = tipo.nome
    existente.tem_unidades = tipo.tem_unidades
    db.commit()
    db.refresh(existente)
    return existente

@router.delete("/{tipo_id}")
def apagar_tipo_ativo(tipo_id: int, db: Session = Depends(get_db)):
    tipo = db.query(TipoAtivo).filter(TipoAtivo.id == tipo_id).first()
    if not tipo:
        raise HTTPException(status_code=404, detail="Tipo de ativo não encontrado.")
    if tipo.ativos:
        raise HTTPException(status_code=409, detail="Não é possível apagar um tipo com ativos associados.")
    db.delete(tipo)
    db.commit()
    return {"ok": True}
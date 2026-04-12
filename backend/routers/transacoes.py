from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, Transacao
from schemas import TransacaoUpdate

router = APIRouter(prefix="/transacoes", tags=["transacoes"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def listar_transacoes(db: Session = Depends(get_db)):
    return db.query(Transacao).all()

@router.put("/{transacao_id}")
def atualizar_transacao(transacao_id: int, dados: TransacaoUpdate, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == transacao_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transação não encontrada")
    if dados.categoria_id is not None:
        t.categoria_id = dados.categoria_id
    if dados.subcategoria_id is not None:
        t.subcategoria_id = dados.subcategoria_id
    if dados.reembolso is not None:
        t.reembolso = dados.reembolso
    if dados.notas is not None:
        t.notas = dados.notas
    db.commit()
    db.refresh(t)
    return t
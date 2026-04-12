from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, RegraCategorizacao, Transacao
from schemas import RegraCreate

router = APIRouter(prefix="/regras", tags=["regras"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def listar_regras(db: Session = Depends(get_db)):
    return db.query(RegraCategorizacao).all()

@router.post("/")
def criar_regra(regra: RegraCreate, db: Session = Depends(get_db)):
    # Verificar se já existe regra com esta palavra-chave
    existente = db.query(RegraCategorizacao).filter_by(palavra_chave=regra.palavra_chave).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe uma regra com esta palavra-chave")

    nova = RegraCategorizacao(
        palavra_chave=regra.palavra_chave,
        categoria_id=regra.categoria_id,
        subcategoria_id=regra.subcategoria_id,
    )
    db.add(nova)
    db.flush()

    # Aplicar regra às transações existentes sem categoria
    transacoes = db.query(Transacao).filter(
        Transacao.categoria_id == None,
        Transacao.descricao.ilike(f"%{regra.palavra_chave}%")
    ).all()

    for t in transacoes:
        t.categoria_id = nova.categoria_id
        t.subcategoria_id = nova.subcategoria_id

    db.commit()
    db.refresh(nova)
    return {"regra": nova, "transacoes_atualizadas": len(transacoes)}

@router.delete("/{regra_id}")
def apagar_regra(regra_id: int, db: Session = Depends(get_db)):
    regra = db.query(RegraCategorizacao).filter(RegraCategorizacao.id == regra_id).first()
    if not regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    db.delete(regra)
    db.commit()
    return {"ok": True}
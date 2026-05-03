from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, Categoria, Subcategoria
from popular_bd import CATEGORIAS

router = APIRouter(prefix="/configuracao", tags=["configuracao"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/estado")
def estado(db: Session = Depends(get_db)):
    tem_categorias = db.query(Categoria).count() > 0
    return {"inicializado": tem_categorias}

@router.post("/inicializar")
def inicializar(db: Session = Depends(get_db)):
    if db.query(Categoria).count() > 0:
        return {"ok": False, "mensagem": "Base de dados já inicializada"}

    for nome_cat, subcategorias in CATEGORIAS.items():
        cat = Categoria(nome=nome_cat)
        db.add(cat)
        db.flush()
        for nome_sub in subcategorias:
            sub = Subcategoria(nome=nome_sub, categoria_id=cat.id)
            db.add(sub)

    db.commit()
    return {"ok": True, "mensagem": "Categorias e subcategorias criadas com sucesso"}
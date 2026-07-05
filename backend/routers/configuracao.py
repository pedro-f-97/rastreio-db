from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, Categoria, Subcategoria, Configuracao, TipoCategoria
from popular_bd import CATEGORIAS, TIPOS

router = APIRouter(prefix="/configuracao", tags=["configuracao"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/estado")
def estado(db: Session = Depends(get_db)):
    config = db.query(Configuracao).first()
    inicializado = config.inicializado if config else False
    return {"inicializado": inicializado}

@router.post("/inicializar")
def inicializar(com_categorias: bool = True, db: Session = Depends(get_db)):
    config = db.query(Configuracao).first()
    if config and config.inicializado:
        return {"ok": False, "mensagem": "Base de dados já inicializada"}

    if com_categorias:
        for nome_cat, subcategorias in CATEGORIAS.items():
            cat = Categoria(nome=nome_cat, tipo=TIPOS.get(nome_cat, TipoCategoria.despesa))
            db.add(cat)
            db.flush()
            for nome_sub, trata_patrimonio in subcategorias:
                sub = Subcategoria(nome=nome_sub, categoria_id=cat.id, trata_patrimonio=trata_patrimonio)
                db.add(sub)

    if config:
        config.inicializado = True
    else:
        db.add(Configuracao(inicializado=True))

    db.commit()
    mensagem = "Categorias e subcategorias criadas com sucesso" if com_categorias else "Base de dados inicializada sem categorias"
    return {"ok": True, "mensagem": mensagem}
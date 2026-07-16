from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, Categoria, Subcategoria, Configuracao, TipoCategoria
from popular_bd import CATEGORIAS_MINIMALISTA, CATEGORIAS_COMPLETO, TIPOS, PerfilCategorias

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
    tour_visto = config.tour_visto if config else False
    return {"inicializado": inicializado, "tour_visto": tour_visto}

@router.post("/inicializar")
def inicializar(
    com_categorias: bool = True,
    perfil: PerfilCategorias = PerfilCategorias.completo,
    db: Session = Depends(get_db),
):
    config = db.query(Configuracao).first()
    if config and config.inicializado:
        return {"ok": False, "mensagem": "Base de dados já inicializada"}

    if com_categorias:
        categorias = (
            CATEGORIAS_MINIMALISTA if perfil == PerfilCategorias.minimalista else CATEGORIAS_COMPLETO
        )
        for nome_cat, subcategorias in categorias.items():
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

@router.post("/tour-visto")
def marcar_tour_visto(db: Session = Depends(get_db)):
    config = db.query(Configuracao).first()
    if config:
        config.tour_visto = True
    else:
        db.add(Configuracao(inicializado=True, tour_visto=True))
    db.commit()
    return {"ok": True}
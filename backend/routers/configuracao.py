from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, Configuracao
from dados_iniciais import PerfilCategorias, semear_dados_iniciais

router = APIRouter(prefix="/configuracao", tags=["configuracao"])

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

    semear_dados_iniciais(db, perfil, com_categorias)

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
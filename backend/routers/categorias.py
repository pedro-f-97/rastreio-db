from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, Categoria, Subcategoria
from schemas import CategoriaCreate, SubcategoriaCreate

router = APIRouter(prefix="/categorias", tags=["categorias"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/")
def listar_categorias(db: Session = Depends(get_db)):
    return db.query(Categoria).all()

@router.get("/{categoria_id}/subcategorias")
def listar_subcategorias(categoria_id: int, db: Session = Depends(get_db)):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return cat.subcategorias

@router.post("/")
def criar_categoria(categoria: CategoriaCreate, db: Session = Depends(get_db)):
    nova = Categoria(nome=categoria.nome)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova

@router.post("/{categoria_id}/subcategorias")
def criar_subcategoria(categoria_id: int, subcategoria: SubcategoriaCreate, db: Session = Depends(get_db)):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    nova = Subcategoria(nome=subcategoria.nome, categoria_id=categoria_id)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova

@router.delete("/{categoria_id}")
def apagar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    db.delete(cat)
    db.commit()
    return {"ok": True}

@router.put("/{categoria_id}")
def renomear_categoria(categoria_id: int, categoria: CategoriaCreate, db: Session = Depends(get_db)):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    cat.nome = categoria.nome
    db.commit()
    db.refresh(cat)
    return cat
import unicodedata

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import Categoria, RegraCategorizacao, Subcategoria, Transacao, get_db
from schemas import CategoriaCreate, SubcategoriaCreate

router = APIRouter(prefix="/categorias", tags=["categorias"])


def _nome_valido(nome: str) -> str:
    """O nome sem espaços à volta; um nome vazio é recusado (achado 1.3)."""
    nome = nome.strip()
    if not nome:
        raise HTTPException(status_code=400, detail="O nome não pode ficar vazio.")
    return nome


def _chave(nome: str) -> str:
    """A forma de comparar nomes: sem maiúsculas nem acentos, para «Salário»,
    «salário» e «salario» serem o mesmo nome."""
    sem_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c)
    )
    return sem_acentos.casefold()


def _repetido(nome: str, existentes, excepto_id: int | None = None) -> bool:
    """Se `nome` é igual, pela `_chave`, ao de algum dos `existentes` (menos `excepto_id`)."""
    chave = _chave(nome)
    return any(e.id != excepto_id and _chave(e.nome) == chave for e in existentes)


@router.get("/")
def listar_categorias(db: Session = Depends(get_db)):
    categorias = db.query(Categoria).all()
    return [
        {
            "id": cat.id,
            "nome": cat.nome,
            "tipo": cat.tipo.value,
            "subcategorias": [
                {"id": sub.id, "nome": sub.nome, "trata_patrimonio": sub.trata_patrimonio}
                for sub in cat.subcategorias
            ],
        }
        for cat in categorias
    ]


@router.get("/{categoria_id}/subcategorias")
def listar_subcategorias(categoria_id: int, db: Session = Depends(get_db)):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    return cat.subcategorias


@router.post("/")
def criar_categoria(categoria: CategoriaCreate, db: Session = Depends(get_db)):
    nome = _nome_valido(categoria.nome)
    if _repetido(nome, db.query(Categoria).all()):
        raise HTTPException(status_code=409, detail="Já existe uma categoria com este nome.")
    nova = Categoria(nome=nome, tipo=categoria.tipo)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova


@router.post("/{categoria_id}/subcategorias")
def criar_subcategoria(
    categoria_id: int, subcategoria: SubcategoriaCreate, db: Session = Depends(get_db)
):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    nome = _nome_valido(subcategoria.nome)
    if _repetido(nome, cat.subcategorias):
        raise HTTPException(
            status_code=409, detail="Já existe uma subcategoria com este nome nesta categoria."
        )
    nova = Subcategoria(
        nome=nome,
        categoria_id=categoria_id,
        trata_patrimonio=subcategoria.trata_patrimonio or False,
    )
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova


@router.delete("/{categoria_id}")
def apagar_categoria(categoria_id: int, db: Session = Depends(get_db)):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    # Com transações, recusa: sem elas, vão-se as subcategorias e as regras
    ids_sub = [s.id for s in cat.subcategorias]
    n = (
        db.query(Transacao)
        .filter((Transacao.categoria_id == categoria_id) | Transacao.subcategoria_id.in_(ids_sub))
        .count()
    )
    if n:
        raise HTTPException(
            status_code=409,
            detail=(
                f"A categoria tem {n} {'transação' if n == 1 else 'transações'}; "
                "muda-as de categoria antes de a apagar."
            ),
        )
    db.query(RegraCategorizacao).filter(
        (RegraCategorizacao.categoria_id == categoria_id)
        | RegraCategorizacao.subcategoria_id.in_(ids_sub)
    ).delete(synchronize_session=False)
    for sub in cat.subcategorias:
        db.delete(sub)
    db.delete(cat)
    db.commit()
    return {"ok": True}


@router.put("/{categoria_id}")
def renomear_categoria(
    categoria_id: int, categoria: CategoriaCreate, db: Session = Depends(get_db)
):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    nome = _nome_valido(categoria.nome)
    if _repetido(nome, db.query(Categoria).all(), excepto_id=categoria_id):
        raise HTTPException(status_code=409, detail="Já existe uma categoria com este nome.")
    cat.nome = nome
    cat.tipo = categoria.tipo
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{categoria_id}/subcategorias/{subcategoria_id}")
def renomear_subcategoria(
    categoria_id: int,
    subcategoria_id: int,
    subcategoria: SubcategoriaCreate,
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subcategoria)
        .filter(Subcategoria.id == subcategoria_id, Subcategoria.categoria_id == categoria_id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")
    nome = _nome_valido(subcategoria.nome)
    if _repetido(nome, sub.categoria.subcategorias, excepto_id=subcategoria_id):
        raise HTTPException(
            status_code=409, detail="Já existe uma subcategoria com este nome nesta categoria."
        )
    sub.nome = nome
    if subcategoria.trata_patrimonio is not None:
        sub.trata_patrimonio = subcategoria.trata_patrimonio
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{categoria_id}/subcategorias/{subcategoria_id}")
def apagar_subcategoria(categoria_id: int, subcategoria_id: int, db: Session = Depends(get_db)):
    sub = (
        db.query(Subcategoria)
        .filter(Subcategoria.id == subcategoria_id, Subcategoria.categoria_id == categoria_id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subcategoria não encontrada")
    # As transações ficam por categorizar na mesma categoria (pela relationship);
    # as regras perdem a subcategoria
    db.query(RegraCategorizacao).filter(
        RegraCategorizacao.subcategoria_id == subcategoria_id
    ).update({RegraCategorizacao.subcategoria_id: None}, synchronize_session=False)
    db.delete(sub)
    db.commit()
    return {"ok": True}

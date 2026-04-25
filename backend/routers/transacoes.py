from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract
from typing import Optional
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
def listar_transacoes(
    pagina: int = Query(1, ge=1),
    tamanho: int = Query(50, ge=1, le=200),
    mes: Optional[int] = Query(None, ge=1, le=12),
    ano: Optional[int] = Query(None, ge=2000),
    categoria_id: Optional[int] = Query(None),
    por_categorizar: bool = Query(False),
    db: Session = Depends(get_db)
):
    query = db.query(Transacao).order_by(Transacao.data.desc())

    if ano:
        query = query.filter(extract('year', Transacao.data) == ano)
    if mes:
        query = query.filter(extract('month', Transacao.data) == mes)
    if categoria_id:
        query = query.filter(Transacao.categoria_id == categoria_id)
    if por_categorizar:
        query = query.filter(
            (Transacao.categoria_id == None) | (Transacao.subcategoria_id == None)
        )

    total = query.count()
    items = query.offset((pagina - 1) * tamanho).limit(tamanho).all()

    return {
        "total": total,
        "pagina": pagina,
        "tamanho": tamanho,
        "items": [
            {
                "id": t.id,
                "data": t.data,
                "descricao": t.descricao,
                "valor": t.valor,
                "saldo": t.saldo,
                "reembolso": t.reembolso,
                "notas": t.notas,
                "categoria_id": t.categoria_id,
                "categoria_nome": t.categoria.nome if t.categoria else None,
                "subcategoria_id": t.subcategoria_id,
                "subcategoria_nome": t.subcategoria.nome if t.subcategoria else None,
            }
            for t in items
        ]
    }

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
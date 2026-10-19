import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract
from sqlalchemy.orm import Session

from database import Categoria, Subcategoria, Transacao, get_db
from schemas import TransacaoUpdate

router = APIRouter(prefix="/transacoes", tags=["transacoes"])


def _para_pesquisa(texto: str) -> str:
    """Sem acentos e sem maiúsculas, para a pesquisa por descrição (D28)."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()

@router.get("/por-categorizar/total")
def total_por_categorizar(db: Session = Depends(get_db)):
    total = db.query(Transacao).filter(
        (Transacao.categoria_id == None) | (Transacao.subcategoria_id == None)
    ).count()
    return {"total": total}

@router.get("/")
def listar_transacoes(
    pagina: int = Query(1, ge=1),
    tamanho: int = Query(50, ge=1, le=200),
    mes: Optional[int] = Query(None, ge=1, le=12),
    ano: Optional[int] = Query(None, ge=2000),
    categoria_id: Optional[int] = Query(None),
    subcategoria_id: Optional[int] = Query(None),
    conta_id: Optional[int] = Query(None),
    sinal: Optional[str] = Query(None),
    por_categorizar: bool = Query(False),
    descricao: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Transacao).order_by(Transacao.data.desc(), Transacao.id.desc())

    if ano:
        query = query.filter(extract('year', Transacao.data) == ano)
    if mes:
        query = query.filter(extract('month', Transacao.data) == mes)
    if categoria_id:
        query = query.filter(Transacao.categoria_id == categoria_id)
    if subcategoria_id:
        query = query.filter(Transacao.subcategoria_id == subcategoria_id)
    if sinal == "negativo":
        query = query.filter(Transacao.valor < 0)
    elif sinal == "positivo":
        query = query.filter(Transacao.valor > 0)
    if conta_id:
        query = query.filter(Transacao.conta_id == conta_id)
    if por_categorizar:
        query = query.filter(
            (Transacao.categoria_id == None) | (Transacao.subcategoria_id == None)
        )

    if descricao:
        # Filtrado em Python, antes de paginar, para ignorar os acentos (D28)
        procura = _para_pesquisa(descricao)
        todas = [t for t in query.all() if procura in _para_pesquisa(t.descricao)]
        total = len(todas)
        items = todas[(pagina - 1) * tamanho:pagina * tamanho]
    else:
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
                "conta_id": t.conta_id,
                "conta_nome": t.conta.nome if t.conta else None,
            }
            for t in items
        ]
    }

@router.put("/{transacao_id}")
def atualizar_transacao(
    transacao_id: int,
    dados: TransacaoUpdate,
    db: Session = Depends(get_db)
):
    t = db.query(Transacao).filter(Transacao.id == transacao_id).first()

    if not t:
        raise HTTPException(
            status_code=404,
            detail="Transação não encontrada"
        )

    # Calcular alvos (o que fica se não vier no payload)
    categoria_alvo = (
        dados.categoria_id
        if "categoria_id" in dados.model_fields_set
        else t.categoria_id
    )
    subcategoria_alvo = (
        dados.subcategoria_id
        if "subcategoria_id" in dados.model_fields_set
        else t.subcategoria_id
    )

    if dados.categoria_id is not None and db.get(Categoria, dados.categoria_id) is None:
        raise HTTPException(400, "Categoria não encontrada.")

    # Validar invariante: subcategoria pertence à categoria
    if subcategoria_alvo is not None:
        sub = db.query(Subcategoria).filter(
            Subcategoria.id == subcategoria_alvo
        ).first()
        if sub is None:
            raise HTTPException(400, "Subcategoria não encontrada.")
        if sub.categoria_id != categoria_alvo:
            raise HTTPException(
                400, "A subcategoria não pertence à categoria selecionada."
            )

    if "categoria_id" in dados.model_fields_set:
        t.categoria_id = dados.categoria_id

    if "subcategoria_id" in dados.model_fields_set:
        t.subcategoria_id = dados.subcategoria_id

    if dados.reembolso is not None:
        t.reembolso = dados.reembolso

    if dados.notas is not None:
        t.notas = dados.notas

    db.commit()
    db.refresh(t)

    return t
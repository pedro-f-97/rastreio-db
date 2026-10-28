import unicodedata
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract
from sqlalchemy.orm import Session

from database import (
    Categoria,
    Conta,
    MovimentoAtivo,
    PerfilImportacao,
    Subcategoria,
    Transacao,
    get_db,
)
from importador_transacoes import aplicar_regras, regras_por_precedencia
from schemas import TransacaoCreate, TransacaoUpdate
from servicos.dinheiro import arredondar, exato
from servicos.transferencias import DIAS_PAR, transferencias_sem_par

router = APIRouter(prefix="/transacoes", tags=["transacoes"])


def _para_pesquisa(texto: str) -> str:
    """Sem acentos e sem maiúsculas, para a pesquisa por descrição."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def _contas_com_saldo_no_extracto(db: Session) -> set[int]:
    """As contas com algum perfil de importação que traz o saldo: nessas, o
    saldo das transacções é do extracto e não se escreve à mão."""
    return {
        conta_id
        for (conta_id,) in db.query(PerfilImportacao.conta_id)
        .filter(PerfilImportacao.tem_saldo == True, PerfilImportacao.conta_id != None)
        .distinct()
    }


def _validar_subcategoria(db: Session, categoria_id: Optional[int], subcategoria_id: int):
    """Invariante: a subcategoria existe e pertence à categoria."""
    sub = db.query(Subcategoria).filter(Subcategoria.id == subcategoria_id).first()
    if sub is None:
        raise HTTPException(400, "Subcategoria não encontrada.")
    if sub.categoria_id != categoria_id:
        raise HTTPException(400, "A subcategoria não pertence à categoria selecionada.")


@router.get("/por-categorizar/total")
def total_por_categorizar(db: Session = Depends(get_db)):
    valores = [
        exato(valor)
        for (valor,) in db.query(Transacao.valor).filter(
            (Transacao.categoria_id == None) | (Transacao.subcategoria_id == None)
        )
    ]
    # O número é o do contador da barra lateral; as somas a entrar e a sair são
    # para o aviso da página Transações
    return {
        "total": len(valores),
        "entradas": arredondar(sum((v for v in valores if v > 0), Decimal(0))),
        "saidas": arredondar(sum((v for v in valores if v < 0), Decimal(0))),
    }


@router.get("/transferencias-sem-par")
def listar_transferencias_sem_par(db: Session = Depends(get_db)):
    sem_par = transferencias_sem_par(db)
    valores = [exato(t.valor) for t in sem_par]
    return {
        "dias_par": DIAS_PAR,
        "entradas": arredondar(sum((v for v in valores if v > 0), Decimal(0))),
        "saidas": arredondar(sum((v for v in valores if v < 0), Decimal(0))),
        "transacoes": [
            {
                "id": t.id,
                "data": t.data,
                "descricao": t.descricao,
                "valor": t.valor,
                "conta_nome": t.conta.nome if t.conta else None,
            }
            for t in sem_par
        ],
    }


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
    db: Session = Depends(get_db),
):
    query = db.query(Transacao).order_by(Transacao.data.desc(), Transacao.id.desc())

    if ano:
        query = query.filter(extract("year", Transacao.data) == ano)
    if mes:
        query = query.filter(extract("month", Transacao.data) == mes)
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
        query = query.filter((Transacao.categoria_id == None) | (Transacao.subcategoria_id == None))

    if descricao:
        # Filtrado em Python, antes de paginar, para ignorar os acentos
        procura = _para_pesquisa(descricao)
        todas = [t for t in query.all() if procura in _para_pesquisa(t.descricao)]
        total = len(todas)
        items = todas[(pagina - 1) * tamanho : pagina * tamanho]
    else:
        total = query.count()
        items = query.offset((pagina - 1) * tamanho).limit(tamanho).all()

    com_saldo_no_extracto = _contas_com_saldo_no_extracto(db)

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
                "notas": t.notas,
                "categoria_id": t.categoria_id,
                "categoria_nome": t.categoria.nome if t.categoria else None,
                "subcategoria_id": t.subcategoria_id,
                "subcategoria_nome": t.subcategoria.nome if t.subcategoria else None,
                "conta_id": t.conta_id,
                "conta_nome": t.conta.nome if t.conta else None,
                "manual": t.manual,
                "saldo_editavel": t.conta_id is not None
                and t.conta_id not in com_saldo_no_extracto,
            }
            for t in items
        ],
    }


@router.put("/{transacao_id}")
def atualizar_transacao(transacao_id: int, dados: TransacaoUpdate, db: Session = Depends(get_db)):
    t = db.query(Transacao).filter(Transacao.id == transacao_id).first()

    if not t:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    # Calcular alvos (o que fica se não vier no payload)
    categoria_alvo = (
        dados.categoria_id if "categoria_id" in dados.model_fields_set else t.categoria_id
    )
    subcategoria_alvo = (
        dados.subcategoria_id if "subcategoria_id" in dados.model_fields_set else t.subcategoria_id
    )

    if dados.categoria_id is not None and db.get(Categoria, dados.categoria_id) is None:
        raise HTTPException(400, "Categoria não encontrada.")

    # Validar invariante: subcategoria pertence à categoria
    if subcategoria_alvo is not None:
        _validar_subcategoria(db, categoria_alvo, subcategoria_alvo)

    if "saldo" in dados.model_fields_set:
        if t.conta_id is None:
            raise HTTPException(409, "A transação não tem conta: o saldo não se escreve.")
        if t.conta_id in _contas_com_saldo_no_extracto(db):
            raise HTTPException(409, "O saldo desta conta vem do extracto e não se edita.")

    if "categoria_id" in dados.model_fields_set:
        t.categoria_id = dados.categoria_id

    if "subcategoria_id" in dados.model_fields_set:
        t.subcategoria_id = dados.subcategoria_id

    if dados.notas is not None:
        t.notas = dados.notas

    if "saldo" in dados.model_fields_set:
        t.saldo = dados.saldo

    db.commit()
    db.refresh(t)

    return t


@router.post("/")
def criar_transacao(dados: TransacaoCreate, db: Session = Depends(get_db)):
    if db.get(Conta, dados.conta_id) is None:
        raise HTTPException(404, "Conta não encontrada.")
    if dados.categoria_id is not None and db.get(Categoria, dados.categoria_id) is None:
        raise HTTPException(400, "Categoria não encontrada.")
    if dados.subcategoria_id is not None:
        _validar_subcategoria(db, dados.categoria_id, dados.subcategoria_id)

    t = Transacao(**dados.model_dump(), manual=True)
    # Como na importação, as regras só categorizam o que não se escolheu à mão
    if dados.categoria_id is None and dados.subcategoria_id is None:
        aplicar_regras(t, regras_por_precedencia(db))
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{transacao_id}", status_code=204)
def apagar_transacao(transacao_id: int, db: Session = Depends(get_db)):
    t = db.get(Transacao, transacao_id)
    if t is None:
        raise HTTPException(404, "Transação não encontrada")
    # As importadas só saem ao desfazer a importação que as trouxe
    if not t.manual:
        raise HTTPException(409, "Só se podem apagar as transações criadas à mão.")
    if db.query(MovimentoAtivo).filter(MovimentoAtivo.transacao_id == transacao_id).count():
        raise HTTPException(
            409, "A transação está ligada a um movimento de ativo: apaga primeiro o movimento."
        )
    db.delete(t)
    db.commit()

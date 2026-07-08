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
    regras = db.query(RegraCategorizacao).all()
    return [
        {
            "id": r.id,
            "palavra_chave": r.palavra_chave,
            "categoria_id": r.categoria_id,
            "categoria_nome": r.categoria.nome if r.categoria else None,
            "subcategoria_id": r.subcategoria_id,
            "subcategoria_nome": r.subcategoria.nome if r.subcategoria else None,
        }
        for r in regras
    ]

@router.post("/")
def criar_regra(regra: RegraCreate, db: Session = Depends(get_db)):
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

    sem_categoria = []
    com_categoria = []

    if nova.categoria_id is not None:
        # Transações sem categoria
        sem_categoria = db.query(Transacao).filter(
            Transacao.categoria_id == None,
            Transacao.descricao.ilike(f"%{regra.palavra_chave}%"),
        ).all()
        for t in sem_categoria:
            t.categoria_id = nova.categoria_id
            t.subcategoria_id = nova.subcategoria_id

        # Transações com categoria coincidente mas sem subcategoria
        com_categoria = db.query(Transacao).filter(
            Transacao.categoria_id == nova.categoria_id,
            Transacao.subcategoria_id == None,
            Transacao.descricao.ilike(f"%{regra.palavra_chave}%"),
        ).all()
        for t in com_categoria:
            t.subcategoria_id = nova.subcategoria_id

    db.commit()
    db.refresh(nova)

    atualizadas = len(sem_categoria) + len(com_categoria)
    return {"regra": nova, "transacoes_atualizadas": atualizadas}

@router.delete("/{regra_id}")
def apagar_regra(regra_id: int, db: Session = Depends(get_db)):
    regra = db.query(RegraCategorizacao).filter(RegraCategorizacao.id == regra_id).first()
    if not regra:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    db.delete(regra)
    db.commit()
    return {"ok": True}

@router.post("/pre-visualizar")
def pre_visualizar_regras(db: Session = Depends(get_db)):
    regras = db.query(RegraCategorizacao).all()
    transacoes = db.query(Transacao).filter(
        Transacao.subcategoria_id.is_(None),
    ).all()

    sem_conflito = []
    com_conflito = []

    for t in transacoes:
        for regra in regras:
            if regra.categoria_id is None:
                continue
            if regra.palavra_chave.upper() in t.descricao.upper():
                if t.categoria_id is None or t.categoria_id == regra.categoria_id:
                    sem_conflito.append({
                        "id": t.id,
                        "descricao": t.descricao,
                        "categoria_id": regra.categoria_id,
                        "categoria_nome": regra.categoria.nome if regra.categoria else None,
                        "subcategoria_actual_id": t.subcategoria_id,
                        "subcategoria_actual_nome": t.subcategoria.nome if t.subcategoria else None,
                        "subcategoria_sugerida_id": regra.subcategoria_id,
                        "subcategoria_sugerida_nome": regra.subcategoria.nome if regra.subcategoria else None,
                    })
                else:
                    com_conflito.append({
                        "id": t.id,
                        "descricao": t.descricao,
                        "categoria_atual_id": t.categoria_id,
                        "categoria_atual_nome": t.categoria.nome if t.categoria else None,
                        "categoria_sugerida_id": regra.categoria_id,
                        "categoria_sugerida_nome": regra.categoria.nome if regra.categoria else None,
                        "subcategoria_actual_id": t.subcategoria_id,
                        "subcategoria_actual_nome": t.subcategoria.nome if t.subcategoria else None,
                        "subcategoria_sugerida_id": regra.subcategoria_id,
                        "subcategoria_sugerida_nome": regra.subcategoria.nome if regra.subcategoria else None,
                    })
                break

    return {"sem_conflito": sem_conflito, "com_conflito": com_conflito}


@router.post("/aplicar-em-massa")
def aplicar_em_massa(dados: dict, db: Session = Depends(get_db)):
    items = dados.get("ids", [])
    aplicadas = 0

    for item in items:
        t = db.query(Transacao).filter(Transacao.id == item["id"]).first()
        if not t:
            continue
        t.categoria_id = item["categoria_id"]
        t.subcategoria_id = item["subcategoria_id"]
        aplicadas += 1

    db.commit()
    return {"aplicadas": aplicadas}
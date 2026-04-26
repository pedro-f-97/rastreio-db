from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from database import SessionLocal, Transacao, Categoria
from statistics import median

router = APIRouter(prefix="/estatisticas", tags=["estatisticas"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/resumo-mensal")
def resumo_mensal(db: Session = Depends(get_db)):
    # Busca todos os meses com transações
    meses = db.query(
        extract('year', Transacao.data).label('ano'),
        extract('month', Transacao.data).label('mes'),
        func.sum(Transacao.valor).label('total'),
        func.sum(func.iif(Transacao.valor < 0, Transacao.valor, 0)).label('despesas'),
        func.sum(func.iif(Transacao.valor > 0, Transacao.valor, 0)).label('receitas'),
    ).group_by('ano', 'mes').order_by('ano', 'mes').all()

    resultados = []
    totais_mes = []

    for m in meses:
        total_despesas = abs(m.despesas or 0)
        total_receitas = m.receitas or 0
        saldo = m.total or 0
        totais_mes.append(total_despesas)

        resultados.append({
            "ano": int(m.ano),
            "mes": int(m.mes),
            "receitas": round(total_receitas, 2),
            "despesas": round(total_despesas, 2),
            "saldo": round(saldo, 2),
        })

    media = round(sum(totais_mes) / len(totais_mes), 2) if totais_mes else 0
    mediana = round(median(totais_mes), 2) if totais_mes else 0

    return {
        "meses": resultados,
        "media_mensal": media,
        "mediana_mensal": mediana,
    }

@router.get("/por-categoria")
def por_categoria(db: Session = Depends(get_db)):
    # Gastos por categoria por mês
    resultados = db.query(
        extract('year', Transacao.data).label('ano'),
        extract('month', Transacao.data).label('mes'),
        Transacao.categoria_id,
        Categoria.nome.label('categoria_nome'),
        func.sum(Transacao.valor).label('total'),
    ).join(Categoria, Transacao.categoria_id == Categoria.id)\
     .filter(Transacao.valor < 0)\
     .group_by('ano', 'mes', Transacao.categoria_id)\
     .order_by('ano', 'mes')\
     .all()

    # Agrupa por categoria para calcular mediana
    por_cat = {}
    for r in resultados:
        cat_id = r.categoria_id
        if cat_id not in por_cat:
            por_cat[cat_id] = {
                "categoria_id": cat_id,
                "categoria_nome": r.categoria_nome,
                "meses": [],
                "totais": [],
            }
        total = round(abs(r.total or 0), 2)
        por_cat[cat_id]["meses"].append({
            "ano": int(r.ano),
            "mes": int(r.mes),
            "total": total,
        })
        por_cat[cat_id]["totais"].append(total)

    for cat in por_cat.values():
        cat["mediana"] = round(median(cat["totais"]), 2) if cat["totais"] else 0
        cat["media"] = round(sum(cat["totais"]) / len(cat["totais"]), 2) if cat["totais"] else 0
        del cat["totais"]

    return list(por_cat.values())
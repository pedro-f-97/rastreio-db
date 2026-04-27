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
    from statistics import median

    transacoes = db.query(Transacao).join(Categoria, Transacao.categoria_id == Categoria.id).all()

    # Agrupa por mês
    meses = {}
    for t in transacoes:
        if not t.categoria:
            continue
        
        chave = (t.data.year, t.data.month)
        if chave not in meses:
            meses[chave] = {"receitas": 0, "despesas": 0, "investimento": 0}

        if t.categoria.nome == "Receita" and not t.reembolso and t.valor > 0:
            meses[chave]["receitas"] += t.valor
        elif t.categoria.nome == "Investimento":
            meses[chave]["investimento"] += abs(t.valor)
        elif t.valor < 0 and t.categoria.nome != "Receita":
            meses[chave]["despesas"] += abs(t.valor)
        elif t.valor > 0 and t.reembolso:
            meses[chave]["despesas"] -= t.valor

    resultados = []
    totais_despesas = []

    for (ano, mes), v in sorted(meses.items()):
        despesas = round(max(v["despesas"], 0), 2)
        receitas = round(v["receitas"], 2)
        investimento = round(v["investimento"], 2)
        saldo = round(receitas - despesas, 2)
        totais_despesas.append(despesas)

        resultados.append({
            "ano": ano,
            "mes": mes,
            "receitas": receitas,
            "despesas": despesas,
            "investimento": investimento,
            "saldo": saldo,
        })

    media = round(sum(totais_despesas) / len(totais_despesas), 2) if totais_despesas else 0
    mediana = round(median(totais_despesas), 2) if totais_despesas else 0

    return {
        "meses": resultados,
        "media_mensal": media,
        "mediana_mensal": mediana,
    }

@router.get("/por-categoria")
def por_categoria(db: Session = Depends(get_db)):
    # Total de meses distintos com transações
    meses_distintos = db.query(
        extract('year', Transacao.data).label('ano'),
        extract('month', Transacao.data).label('mes'),
    ).distinct().count()

    resultados = db.query(
        extract('year', Transacao.data).label('ano'),
        extract('month', Transacao.data).label('mes'),
        Transacao.categoria_id,
        Categoria.nome.label('categoria_nome'),
        func.sum(Transacao.valor).label('total'),
    ).join(Categoria, Transacao.categoria_id == Categoria.id)\
     .filter(
         Transacao.valor < 0,
         Categoria.nome != 'Investimento',
         Categoria.nome != 'Receita',
     )\
     .group_by('ano', 'mes', Transacao.categoria_id)\
     .order_by('ano', 'mes')\
     .all()

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
        # Média real: divide pelo total de meses, não só pelos meses com despesa
        cat["media"] = round(sum(cat["totais"]) / meses_distintos, 2) if meses_distintos else 0
        del cat["totais"]

    return list(por_cat.values())
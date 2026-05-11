from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from database import SessionLocal, Transacao, Categoria, Subcategoria, TipoCategoria
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

        if t.categoria.tipo == TipoCategoria.receita and not t.reembolso and t.valor > 0:
            meses[chave]["receitas"] += t.valor
        elif t.categoria.tipo == TipoCategoria.investimento:
            meses[chave]["investimento"] += abs(t.valor)
        elif t.valor < 0 and t.categoria.tipo != TipoCategoria.receita:
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
    meses_distintos = db.query(
        extract('year', Transacao.data).label('ano'),
        extract('month', Transacao.data).label('mes'),
    ).distinct().count()

    resultados = db.query(
        extract('year', Transacao.data).label('ano'),
        extract('month', Transacao.data).label('mes'),
        Transacao.categoria_id,
        Categoria.nome.label('categoria_nome'),
        Transacao.subcategoria_id,
        Subcategoria.nome.label('subcategoria_nome'),
        func.sum(Transacao.valor).label('total'),
    ).join(Categoria, Transacao.categoria_id == Categoria.id)\
     .outerjoin(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)\
     .filter(
         Transacao.valor < 0,
         Categoria.tipo != TipoCategoria.investimento,
         Categoria.tipo != TipoCategoria.receita,
         Categoria.tipo != TipoCategoria.transferencia,
     )\
     .group_by('ano', 'mes', Transacao.categoria_id, Transacao.subcategoria_id)\
     .order_by('ano', 'mes')\
     .all()

    por_cat = {}
    for r in resultados:
        cat_id = r.categoria_id
        if cat_id not in por_cat:
            por_cat[cat_id] = {
                "categoria_id": cat_id,
                "categoria_nome": r.categoria_nome,
                "totais": [],
                "subcategorias": {},
            }

        total = round(abs(r.total or 0), 2)
        por_cat[cat_id]["totais"].append(total)

        sub_id = r.subcategoria_id or 0
        if sub_id not in por_cat[cat_id]["subcategorias"]:
            por_cat[cat_id]["subcategorias"][sub_id] = {
                "subcategoria_nome": r.subcategoria_nome or "Sem subcategoria",
                "totais": [],
            }
        por_cat[cat_id]["subcategorias"][sub_id]["totais"].append(total)

    for cat in por_cat.values():
        totais_completos = cat["totais"] + [0] * (meses_distintos - len(cat["totais"]))
        cat["mediana"] = round(median(cat["totais"]), 2) if cat["totais"] else 0
        cat["media"] = round(sum(totais_completos) / meses_distintos, 2) if meses_distintos else 0
        del cat["totais"]

        for sub in cat["subcategorias"].values():
            totais_completos = sub["totais"] + [0] * (meses_distintos - len(sub["totais"]))
            sub["mediana"] = round(median(sub["totais"]), 2) if sub["totais"] else 0
            sub["media"] = round(sum(totais_completos) / meses_distintos, 2) if meses_distintos else 0
            del sub["totais"]

        cat["subcategorias"] = list(cat["subcategorias"].values())

    return list(por_cat.values())

@router.get("/por-subcategoria")
def por_subcategoria(db: Session = Depends(get_db)):
    from database import Subcategoria

    resultados = db.query(
        Transacao.categoria_id,
        Categoria.nome.label('categoria_nome'),
        Transacao.subcategoria_id,
        Subcategoria.nome.label('subcategoria_nome'),
        func.sum(Transacao.valor).label('total'),
    ).join(Categoria, Transacao.categoria_id == Categoria.id)\
     .outerjoin(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)\
        .filter(
            Transacao.valor < 0,
            Categoria.tipo != TipoCategoria.investimento,
            Categoria.tipo != TipoCategoria.receita,
            Categoria.tipo != TipoCategoria.transferencia,
            Transacao.categoria_id != None,
        )\
     .group_by(Transacao.categoria_id, Transacao.subcategoria_id)\
     .all()

    # Agrupa por categoria
    por_cat = {}
    for r in resultados:
        cat_id = r.categoria_id
        if cat_id not in por_cat:
            por_cat[cat_id] = {
                "categoria_id": cat_id,
                "categoria_nome": r.categoria_nome,
                "total": 0,
                "subcategorias": [],
            }
        total = round(abs(r.total or 0), 2)
        por_cat[cat_id]["total"] = round(por_cat[cat_id]["total"] + total, 2)
        por_cat[cat_id]["subcategorias"].append({
            "subcategoria_id": r.subcategoria_id,
            "subcategoria_nome": r.subcategoria_nome or "Sem subcategoria",
            "total": total,
        })

    return list(por_cat.values())

def _query_transacoes_mes(db: Session, inicio, fim):
    return db.query(
        Transacao.categoria_id,
        Categoria.nome.label('categoria_nome'),
        Categoria.tipo.label('categoria_tipo'),
        Transacao.subcategoria_id,
        Subcategoria.nome.label('subcategoria_nome'),
        Transacao.valor,
        Transacao.reembolso,
    ).join(Categoria, Transacao.categoria_id == Categoria.id)\
     .outerjoin(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)\
     .filter(
         Transacao.data >= inicio,
         Transacao.data <= fim,
         Transacao.categoria_id != None,
     )\
     .all()


def _agregar_por_categoria(rows):
    por_cat = {}

    for r in rows:
        cat_id = r.categoria_id
        if cat_id not in por_cat:
            por_cat[cat_id] = {
                "categoria_id": cat_id,
                "categoria_nome": r.categoria_nome,
                "categoria_tipo": r.categoria_tipo,
                "total_centimos": 0,
                "subcategorias": {},
            }

        sub_key = r.subcategoria_id or 0
        if sub_key not in por_cat[cat_id]["subcategorias"]:
            por_cat[cat_id]["subcategorias"][sub_key] = {
                "subcategoria_nome": r.subcategoria_nome or "Sem subcategoria",
                "total_centimos": 0,
            }

        contribuicao = round(r.valor * 100)
        por_cat[cat_id]["total_centimos"] += contribuicao
        por_cat[cat_id]["subcategorias"][sub_key]["total_centimos"] += contribuicao

    return por_cat


@router.get("/detalhe-mensal")
def detalhe_mensal(ano: int, mes: int, db: Session = Depends(get_db)):
    import calendar
    from datetime import date

    inicio = date(ano, mes, 1)
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1])

    rows = _query_transacoes_mes(db, inicio, fim)
    por_cat = _agregar_por_categoria(rows)


    resultado_final = []
    for cat in por_cat.values():
        tipo = cat["categoria_tipo"].value

        if tipo == "investimento":
            total_cat = abs(cat["total_centimos"]) / 100
            subcategorias_valores = [(s, abs(s["total_centimos"]) / 100) for s in cat["subcategorias"].values()]
        else:
            total_cat = cat["total_centimos"] / 100
            subcategorias_valores = [(s, s["total_centimos"] / 100) for s in cat["subcategorias"].values()]

        subcategorias = sorted(
            [
                {
                    "subcategoria_nome": s["subcategoria_nome"],
                    "total": total,
                }
                for s, total in subcategorias_valores
            ],
            key=lambda s: s["total"],
            reverse=True,
        )

        resultado_final.append({
            "categoria_id": cat["categoria_id"],
            "categoria_nome": cat["categoria_nome"],
            "tipo": tipo,
            "total": total_cat,
            "subcategorias": subcategorias,
        })

    return sorted(resultado_final, key=lambda c: c["total"], reverse=True)
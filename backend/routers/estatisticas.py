import calendar
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from database import Categoria, Subcategoria, TipoCategoria, Transacao, get_db
from servicos.dinheiro import arredondar, exato

router = APIRouter(prefix="/estatisticas", tags=["estatisticas"])


@router.get("/resumo-mensal")
def resumo_mensal(db: Session = Depends(get_db)):
    transacoes = db.query(Transacao).join(Categoria, Transacao.categoria_id == Categoria.id).all()

    todos_meses = (
        db.query(
            extract("year", Transacao.data).label("ano"),
            extract("month", Transacao.data).label("mes"),
        )
        .distinct()
        .all()
    )

    meses = _calculate_totals(transacoes)

    for m in todos_meses:
        chave = (int(m.ano), int(m.mes))
        if chave not in meses:
            meses[chave] = {"receitas": 0, "despesas": 0, "investimento": 0}

    resultados = []
    totais_despesas = []

    for (ano, mes), v in sorted(meses.items()):
        despesas = arredondar(v["despesas"])
        receitas = arredondar(v["receitas"])
        investimento = arredondar(v["investimento"])
        poupanca = arredondar(receitas + despesas)
        totais_despesas.append(exato(despesas))

        resultados.append(
            {
                "ano": ano,
                "mes": mes,
                "receitas": receitas,
                "despesas": despesas,
                "investimento": investimento,
                "poupanca": poupanca,
            }
        )

    # Média e mediana em Decimal: um empate no meio cêntimo arredonda sempre
    # para longe de zero, e não ao sabor do binário do float
    media = arredondar(sum(totais_despesas) / len(totais_despesas)) if totais_despesas else 0
    mediana = arredondar(median(totais_despesas)) if totais_despesas else 0

    return {
        "meses": resultados,
        "media_mensal": media,
        "mediana_mensal": mediana,
    }


def _mediana_mensal(totais, meses_distintos):
    """Mediana dos totais mensais, com os meses sem movimentos a contar como zero."""
    if not meses_distintos:
        return 0
    totais = [exato(t) for t in totais]
    return arredondar(median(totais + [Decimal(0)] * (meses_distintos - len(totais))))


@router.get("/por-categoria")
def por_categoria(ano: Optional[int] = None, db: Session = Depends(get_db)):
    q_meses = db.query(
        extract("year", Transacao.data).label("ano"),
        extract("month", Transacao.data).label("mes"),
    ).distinct()
    if ano:
        q_meses = q_meses.filter(extract("year", Transacao.data) == ano)
    meses_distintos = q_meses.count()

    q = (
        db.query(
            extract("year", Transacao.data).label("ano"),
            extract("month", Transacao.data).label("mes"),
            Transacao.categoria_id,
            Categoria.nome.label("categoria_nome"),
            Transacao.subcategoria_id,
            Subcategoria.nome.label("subcategoria_nome"),
            func.sum(Transacao.valor).label("total"),
        )
        .join(Categoria, Transacao.categoria_id == Categoria.id)
        .outerjoin(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)
        .filter(Categoria.tipo != TipoCategoria.transferencia)
    )

    if ano:
        q = q.filter(extract("year", Transacao.data) == ano)

    resultados = (
        q.group_by("ano", "mes", Transacao.categoria_id, Transacao.subcategoria_id)
        .order_by("ano", "mes")
        .all()
    )

    por_cat = {}
    for r in resultados:
        cat_id = r.categoria_id
        if cat_id not in por_cat:
            por_cat[cat_id] = {
                "categoria_id": cat_id,
                "categoria_nome": r.categoria_nome,
                "por_mes": {},
                "subcategorias": {},
            }

        total = arredondar(r.total or 0)
        # Uma linha por (mês, subcategoria): a categoria soma-as por mês
        mes = (r.ano, r.mes)
        por_mes = por_cat[cat_id]["por_mes"]
        por_mes[mes] = arredondar(por_mes.get(mes, 0) + total)

        sub_id = r.subcategoria_id or 0
        if sub_id not in por_cat[cat_id]["subcategorias"]:
            por_cat[cat_id]["subcategorias"][sub_id] = {
                "subcategoria_nome": r.subcategoria_nome or "Sem subcategoria",
                "totais": [],
            }
        por_cat[cat_id]["subcategorias"][sub_id]["totais"].append(total)

    # Média e mediana sobre os mesmos meses: os `meses_distintos` do período, e
    # os meses sem movimentos na categoria contam como zero
    for cat in por_cat.values():
        totais = list(cat.pop("por_mes").values())
        cat["mediana"] = _mediana_mensal(totais, meses_distintos)
        cat["media"] = (
            arredondar(sum(map(exato, totais)) / meses_distintos) if meses_distintos else 0
        )

        for sub in cat["subcategorias"].values():
            sub["mediana"] = _mediana_mensal(sub["totais"], meses_distintos)
            sub["media"] = (
                arredondar(sum(map(exato, sub["totais"])) / meses_distintos)
                if meses_distintos
                else 0
            )
            del sub["totais"]

        cat["subcategorias"] = list(cat["subcategorias"].values())

    return list(por_cat.values())


@router.get("/por-subcategoria")
def por_subcategoria(ano: Optional[int] = None, db: Session = Depends(get_db)):
    q = (
        db.query(
            Transacao.categoria_id,
            Categoria.nome.label("categoria_nome"),
            Transacao.subcategoria_id,
            Subcategoria.nome.label("subcategoria_nome"),
            Transacao.valor,
        )
        .join(Categoria, Transacao.categoria_id == Categoria.id)
        .outerjoin(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)
        .filter(
            Categoria.tipo != TipoCategoria.transferencia,
            Transacao.categoria_id != None,
        )
    )

    if ano:
        q = q.filter(extract("year", Transacao.data) == ano)

    resultados = q.all()

    por_cat = {}
    for r in resultados:
        cat_id = r.categoria_id
        if cat_id not in por_cat:
            por_cat[cat_id] = {
                "categoria_id": cat_id,
                "categoria_nome": r.categoria_nome,
                "total_centimos": 0,
                "subcategorias": {},
            }

        sub_key = r.subcategoria_id or 0
        if sub_key not in por_cat[cat_id]["subcategorias"]:
            por_cat[cat_id]["subcategorias"][sub_key] = {
                "subcategoria_nome": r.subcategoria_nome or "Sem subcategoria",
                "total_centimos": 0,
            }

        contribuicao = round(arredondar(r.valor) * 100)
        por_cat[cat_id]["total_centimos"] += contribuicao
        por_cat[cat_id]["subcategorias"][sub_key]["total_centimos"] += contribuicao

    resultado = []
    for cat in por_cat.values():
        total_cat = cat["total_centimos"] / 100
        subcategorias = []
        for sub in cat["subcategorias"].values():
            total_sub = sub["total_centimos"] / 100
            if abs(total_sub) > 0:
                subcategorias.append(
                    {
                        "subcategoria_nome": sub["subcategoria_nome"],
                        "total": total_sub,
                    }
                )
        if abs(total_cat) > 0:
            resultado.append(
                {
                    "categoria_id": cat["categoria_id"],
                    "categoria_nome": cat["categoria_nome"],
                    "total": total_cat,
                    "subcategorias": subcategorias,
                }
            )
    return sorted(resultado, key=lambda c: c["total"], reverse=True)


def _query_transacoes_mes(db: Session, inicio, fim):
    return (
        db.query(
            Transacao.categoria_id,
            Categoria.nome.label("categoria_nome"),
            Categoria.tipo.label("categoria_tipo"),
            Transacao.subcategoria_id,
            Subcategoria.nome.label("subcategoria_nome"),
            Transacao.valor,
        )
        .join(Categoria, Transacao.categoria_id == Categoria.id)
        .outerjoin(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)
        .filter(
            Transacao.data >= inicio,
            Transacao.data <= fim,
            Transacao.categoria_id != None,
            Categoria.tipo != TipoCategoria.transferencia,
        )
        .all()
    )


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

        contribuicao = round(arredondar(r.valor) * 100)
        por_cat[cat_id]["total_centimos"] += contribuicao
        por_cat[cat_id]["subcategorias"][sub_key]["total_centimos"] += contribuicao

    return por_cat


@router.get("/detalhe-mensal")
def detalhe_mensal(
    ano: int = Query(ge=2000, le=9999),
    mes: int = Query(ge=1, le=12),
    db: Session = Depends(get_db),
):
    inicio = date(ano, mes, 1)
    fim = date(ano, mes, calendar.monthrange(ano, mes)[1])

    rows = _query_transacoes_mes(db, inicio, fim)
    por_cat = _agregar_por_categoria(rows)

    resultado_final = []
    for cat in por_cat.values():
        tipo = cat["categoria_tipo"].value
        total_cat = cat["total_centimos"] / 100
        subcategorias_valores = [
            (s, s["total_centimos"] / 100) for s in cat["subcategorias"].values()
        ]

        subcategorias = sorted(
            [
                {"subcategoria_nome": s["subcategoria_nome"], "total": total}
                for s, total in subcategorias_valores
            ],
            key=lambda s: s["total"],
            reverse=True,
        )

        resultado_final.append(
            {
                "categoria_id": cat["categoria_id"],
                "categoria_nome": cat["categoria_nome"],
                "tipo": tipo,
                "total": total_cat,
                "subcategorias": subcategorias,
            }
        )

    return sorted(resultado_final, key=lambda c: c["total"], reverse=True)


def _calculate_totals(transacoes):
    meses = {}
    for t in transacoes:
        if not t.categoria:
            continue
        if t.categoria.tipo == TipoCategoria.transferencia:
            continue

        chave = (t.data.year, t.data.month)
        if chave not in meses:
            meses[chave] = {"receitas": 0, "despesas": 0, "investimento": 0}

        if t.categoria.tipo == TipoCategoria.receita:
            # Com o sinal que tem: um estorno de receita reduz as receitas
            meses[chave]["receitas"] += t.valor
        elif t.categoria.tipo == TipoCategoria.investimento:
            meses[chave]["investimento"] += t.valor
        else:
            # Despesa, com o sinal que tem: um reembolso (positivo) reduz a despesa
            meses[chave]["despesas"] += t.valor

    return meses

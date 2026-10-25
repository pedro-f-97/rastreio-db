from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from database import Categoria, ClasseDespesa, Subcategoria, TipoCategoria, Transacao
from servicos.dinheiro import arredondar, exato
from servicos.patrimonio_serv import crescimento_dos_pontos, gerar_evolucao

# O panfleto descreve os hábitos dos últimos 12 meses completos
MESES_PANFLETO = 12
# As subcategorias da despesa que se mostram uma a uma; as outras somam-se
TOP_SUBCATEGORIAS = 7
# A projecção: só a poupança (0 %) e dois cenários de rendimento anual dos
# investimentos, até 10 anos
TAXAS_PROJECAO = (0, 4, 7)
MESES_PROJECAO = 120

CHAVES_CLASSE = {
    ClasseDespesa.essencial: "essencial",
    ClasseDespesa.evitavel: "evitavel",
    None: "sem_classe",
}


def _recuar_meses(dia: date, meses: int) -> date:
    """O primeiro dia do mês `meses` antes do de `dia`."""
    indice = dia.year * 12 + dia.month - 1 - meses
    return date(indice // 12, indice % 12 + 1, 1)


def _projecao(atual, investimentos, poupanca, aporte) -> list[dict]:
    """O património mês a mês, até `MESES_PROJECAO`, para cada taxa.

    Cada mês soma a poupança (`poupanca`, o crescimento sem a valorização).
    Nos cenários com rendimento, os investimentos rendem a taxa anual,
    composta todos os meses: o rendimento do mês conta sobre os investimentos
    do início do mês, e só depois entra o que se investe nesse mês (`aporte`).
    O rendimento soma-se ao património; o aporte não, porque passa da conta
    para os investimentos e já está na poupança.
    """
    cenarios = []
    for taxa in TAXAS_PROJECAO:
        mensal = (1 + taxa / 100) ** (1 / 12) - 1
        investido = investimentos
        total = atual
        valores = [arredondar(total)]
        for _ in range(MESES_PROJECAO):
            rendimento = investido * mensal
            investido += rendimento + aporte
            total += poupanca + rendimento
            valores.append(arredondar(total))
        cenarios.append({"taxa": taxa, "valores": valores})
    return cenarios


def calcular_panfleto(db: Session, hoje: date) -> dict | None:
    """Os números do panfleto: os hábitos dos últimos `MESES_PANFLETO` meses
    completos antes de `hoje`, e o património no fim do último.

    Sem nenhum mês completo com transacções, devolve `None`. Com menos
    histórico, o período começa no mês da primeira transacção. As médias
    dividem pelos meses do período que têm transacções, como as das
    Estatísticas. A despesa normal deixa de fora as subcategorias
    extraordinárias, que se somam à parte.
    """
    fim = date(hoje.year, hoje.month, 1) - timedelta(days=1)
    primeira = db.query(func.min(Transacao.data)).scalar()
    if primeira is None or primeira > fim:
        return None
    inicio = max(_recuar_meses(fim, MESES_PANFLETO - 1), date(primeira.year, primeira.month, 1))
    no_periodo = Transacao.data.between(inicio, fim)

    meses = (
        db.query(extract("year", Transacao.data), extract("month", Transacao.data))
        .filter(no_periodo)
        .distinct()
        .count()
    )

    linhas = (
        db.query(
            Transacao.valor,
            Transacao.categoria_id,
            Categoria.nome.label("categoria_nome"),
            Categoria.tipo,
            Transacao.subcategoria_id,
            Subcategoria.nome.label("subcategoria_nome"),
            Subcategoria.classe_despesa,
        )
        .join(Categoria, Transacao.categoria_id == Categoria.id)
        .outerjoin(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)
        .filter(no_periodo, Categoria.tipo != TipoCategoria.transferencia)
        .all()
    )

    # As somas do período, com o sinal de cada transacção: um reembolso reduz
    # a despesa, e um estorno a receita
    receitas = Decimal(0)
    investido = Decimal(0)
    extraordinarias = Decimal(0)
    por_classe = dict.fromkeys(CHAVES_CLASSE.values(), Decimal(0))
    por_subcategoria = {}
    for linha in linhas:
        valor = exato(linha.valor)
        if linha.tipo == TipoCategoria.receita:
            receitas += valor
        elif linha.tipo == TipoCategoria.investimento:
            investido += valor
        elif linha.classe_despesa == ClasseDespesa.extraordinaria:
            extraordinarias += valor
        else:
            por_classe[CHAVES_CLASSE[linha.classe_despesa]] += valor
            chave = (linha.categoria_id, linha.subcategoria_id)
            if chave not in por_subcategoria:
                por_subcategoria[chave] = {
                    "categoria": linha.categoria_nome,
                    "subcategoria": linha.subcategoria_nome or "Sem subcategoria",
                    "classe": linha.classe_despesa.value if linha.classe_despesa else None,
                    "total": Decimal(0),
                }
            por_subcategoria[chave]["total"] += valor

    # A despesa e o investimento saem em positivo, como se lêem no panfleto
    def por_mes(total):
        return arredondar(-total / meses)

    despesa = sum(por_classe.values(), Decimal(0))
    subcategorias = sorted(por_subcategoria.values(), key=lambda s: s["total"])
    top = [
        {
            "categoria": s["categoria"],
            "subcategoria": s["subcategoria"],
            "classe": s["classe"],
            "mensal": por_mes(s["total"]),
        }
        for s in subcategorias[:TOP_SUBCATEGORIAS]
    ]
    outras = subcategorias[TOP_SUBCATEGORIAS:]

    pontos = gerar_evolucao(db, inicio, fim, hoje, com_valorizacao=True)
    crescimento = crescimento_dos_pontos(pontos)
    ultimo = pontos[-1]

    projecao = None
    if crescimento["poupanca"] is not None:
        projecao = _projecao(
            ultimo["total"],
            ultimo["investimentos"],
            crescimento["poupanca"],
            float(-investido / meses),
        )

    return {
        "gerado_em": hoje.isoformat(),
        "periodo": {
            "de": {"ano": inicio.year, "mes": inicio.month},
            "ate": {"ano": fim.year, "mes": fim.month},
            "meses": meses,
        },
        "mes": {
            "receita": arredondar(receitas / meses),
            "despesa": por_mes(despesa),
            **{chave: por_mes(total) for chave, total in por_classe.items()},
            # O total do período, não por mês
            "extraordinarias": arredondar(-extraordinarias),
        },
        "despesas": {
            "top": top,
            "outras": {
                "quantas": len(outras),
                "mensal": por_mes(sum((s["total"] for s in outras), Decimal(0))),
            },
        },
        "patrimonio": {
            "atual": ultimo["total"],
            "liquidez": ultimo["liquidez"],
            "investimentos": ultimo["investimentos"],
            "bens": ultimo["ativos_fisicos"],
            "crescimento": crescimento["total"],
            "poupanca": crescimento["poupanca"],
            "valorizacao": crescimento["valorizacao"],
            "investido": arredondar(-investido),
        },
        "projecao": projecao,
    }

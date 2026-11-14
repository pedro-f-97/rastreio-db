"""O relatório anual do IRS: as vendas, os dividendos e os juros de um ano.

Não calcula o imposto: mostra os valores a declarar, agrupados pelo anexo e
pelo quadro onde se escrevem, para copiar linha a linha para o Portal das
Finanças (`docs/plano-irs.md`, decisões 9 e 19).

- **Vendas.** Cada venda dá uma linha por lote consumido pelo FIFO
  (`percorrer_fifo`), juntando os lotes comprados no mesmo dia. Os valores de
  realização e de aquisição são brutos, e as comissões vão para as despesas,
  na parte que cabe às unidades da linha. Só entram os ativos com unidades de
  um tipo classificado para o IRS.
- **Anexo e quadro.** Valores mobiliários numa corretora portuguesa: anexo G,
  quadro 9; numa estrangeira: anexo J, quadro 9.2A. Criptoativos detidos menos
  de 365 dias: anexo G, quadro 18A; 365 dias ou mais: anexo G1, quadro 7.
- **Países.** O da fonte é o do emitente (o da corretora, se o ativo não o
  tiver); o da contraparte é o da corretora.
- **Dividendos e juros.** O valor recebido, sem o imposto retido. Os de uma
  corretora ou conta portuguesa ficam à parte; os outros agrupam-se pelo país.
"""

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import extract
from sqlalchemy.orm import Session, joinedload

from database import (
    Ativo,
    ClassificacaoFiscal,
    MovimentoAtivo,
    Subcategoria,
    TipoAtivo,
    Transacao,
)
from servicos.dinheiro import arredondar, exato
from servicos.patrimonio_serv import percorrer_fifo

# O código de cada classificação de valores mobiliários no quadro das vendas
CODIGOS = {
    ClassificacaoFiscal.acoes: "G01",
    ClassificacaoFiscal.fundos: "G20",
    ClassificacaoFiscal.obrigacoes: "G10",
    ClassificacaoFiscal.outros_mobiliarios: "G90",
}

# Abaixo disto, os ganhos dos criptoativos são tributados; a partir daqui, ficam
# excluídos, mas declaram-se no anexo G1
DIAS_CRIPTO = 365

# Os códigos numéricos da ISO 3166 dos países mais comuns nas corretoras e nos
# emitentes. A Tabela X das instruções do Modelo 3 parece usar estes números (a
# confirmar no modelo do ano); um país fora da lista fica sem número
PAISES_NUMERICOS = {
    "AT": "040",
    "AU": "036",
    "BE": "056",
    "BR": "076",
    "CA": "124",
    "CH": "756",
    "CY": "196",
    "CZ": "203",
    "DE": "276",
    "DK": "208",
    "EE": "233",
    "ES": "724",
    "FI": "246",
    "FR": "250",
    "GB": "826",
    "GR": "300",
    "HK": "344",
    "IE": "372",
    "IT": "380",
    "JP": "392",
    "KY": "136",
    "LT": "440",
    "LU": "442",
    "LV": "428",
    "MT": "470",
    "NL": "528",
    "NO": "578",
    "PL": "616",
    "PT": "620",
    "SE": "752",
    "SG": "702",
    "US": "840",
}


def _pais(alfa2: str) -> dict:
    return {"codigo": alfa2, "numero": PAISES_NUMERICOS.get(alfa2)}


def _ativos_do_irs(db: Session) -> list[Ativo]:
    """Os ativos de tipos classificados para o IRS."""
    return (
        db.query(Ativo)
        .join(TipoAtivo, Ativo.tipo_id == TipoAtivo.id)
        .filter(TipoAtivo.classificacao_fiscal != ClassificacaoFiscal.fora)
        .options(joinedload(Ativo.tipo))
        .order_by(Ativo.nome, Ativo.id)
        .all()
    )


def _movimentos(db: Session, ativo: Ativo) -> list[MovimentoAtivo]:
    return (
        db.query(MovimentoAtivo)
        .filter(MovimentoAtivo.ativo_id == ativo.id)
        .order_by(MovimentoAtivo.data, MovimentoAtivo.id)
        .all()
    )


def _grupo_da_venda(ativo: Ativo, dias: int) -> tuple[str, str]:
    """O (anexo, quadro) onde se escreve uma linha de venda."""
    classificacao = ativo.tipo.classificacao_fiscal
    if classificacao == ClassificacaoFiscal.criptoativos:
        return ("G", "18A") if dias < DIAS_CRIPTO else ("G1", "7")
    return ("G", "9") if ativo.pais == "PT" else ("J", "9.2A")


def _linhas_de_venda(ativo: Ativo, movimentos: list[MovimentoAtivo], ano: int) -> list[dict]:
    """As linhas das vendas do ativo em `ano`, uma por dia de compra consumido.

    A venda reparte-se pelas unidades: cada linha leva a parte do valor bruto
    da venda (o total mais a comissão) e da sua comissão que cabe às suas
    unidades. Cada pedaço de lote leva a parte do valor bruto da compra (o
    total menos a comissão) e da sua comissão que cabe às unidades vendidas.
    As contas fazem-se em `Decimal` e só a linha arredonda ao cêntimo.
    """
    linhas = []
    for venda in percorrer_fifo(movimentos)["vendas"]:
        v = venda["venda"]
        if v.data.year != ano:
            continue
        q_venda = exato(v.quantidade)
        comissao_venda = abs(exato(v.comissao or 0))
        bruto_venda = abs(exato(v.valor_total)) + comissao_venda

        # Os pedaços comprados no mesmo dia somam-se numa só linha
        por_dia = defaultdict(lambda: dict.fromkeys(("q", "aq", "desp", "real"), Decimal(0)))
        for pedaco in venda["consumidos"]:
            compra = pedaco["compra"]
            q = pedaco["quantidade"]
            comissao_compra = abs(exato(compra.comissao or 0))
            bruto_compra = abs(exato(compra.valor_total)) - comissao_compra
            parte_compra = q / exato(compra.quantidade)
            parte_venda = q / q_venda
            soma = por_dia[compra.data]
            soma["q"] += q
            soma["aq"] += bruto_compra * parte_compra
            soma["desp"] += comissao_compra * parte_compra + comissao_venda * parte_venda
            soma["real"] += bruto_venda * parte_venda

        for data_compra, soma in sorted(por_dia.items()):
            realizacao = arredondar(soma["real"])
            aquisicao = arredondar(soma["aq"])
            despesas = arredondar(soma["desp"])
            dias = (v.data - data_compra).days
            anexo, quadro = _grupo_da_venda(ativo, dias)
            linhas.append(
                {
                    "anexo": anexo,
                    "quadro": quadro,
                    "ativo": ativo.nome,
                    "codigo": CODIGOS.get(ativo.tipo.classificacao_fiscal),
                    "pais_fonte": _pais(ativo.pais_emitente or ativo.pais),
                    "pais_contraparte": _pais(ativo.pais),
                    "quantidade": float(soma["q"]),
                    "data_realizacao": v.data,
                    "valor_realizacao": realizacao,
                    "data_aquisicao": data_compra,
                    "valor_aquisicao": aquisicao,
                    "despesas": despesas,
                    "dias": dias,
                    "ganho": arredondar(exato(realizacao) - exato(aquisicao) - exato(despesas)),
                }
            )
    return linhas


def _soma(valores) -> float:
    return arredondar(sum((exato(v) for v in valores), Decimal(0)))


# A ordem em que os grupos de vendas se mostram
ORDEM_QUADROS = [("G", "9"), ("J", "9.2A"), ("G", "18A"), ("G1", "7")]


def _agrupar_vendas(linhas: list[dict]) -> list[dict]:
    grupos = defaultdict(list)
    for linha in linhas:
        grupos[(linha["anexo"], linha["quadro"])].append(linha)
    resultado = []
    for anexo, quadro in ORDEM_QUADROS:
        do_grupo = grupos.get((anexo, quadro))
        if not do_grupo:
            continue
        do_grupo.sort(key=lambda li: (li["data_realizacao"], li["ativo"], li["data_aquisicao"]))
        resultado.append(
            {
                "anexo": anexo,
                "quadro": quadro,
                "linhas": do_grupo,
                "totais": {
                    "realizacao": _soma(li["valor_realizacao"] for li in do_grupo),
                    "aquisicao": _soma(li["valor_aquisicao"] for li in do_grupo),
                    "despesas": _soma(li["despesas"] for li in do_grupo),
                    "saldo": _soma(li["ganho"] for li in do_grupo),
                },
            }
        )
    return resultado


def _agrupar_por_origem(linhas: list[dict]) -> list[dict]:
    """Os dividendos ou os juros: os portugueses à parte, primeiro, e os do
    estrangeiro por país. Cada linha traz `portugues` e `pais`."""
    grupos = defaultdict(list)
    for linha in linhas:
        chave = "PT" if linha["portugues"] else linha["pais"]["codigo"]
        grupos[chave].append(linha)
    chaves = sorted(grupos, key=lambda c: (c != "PT", c))
    return [
        {
            "portugues": chave == "PT",
            "pais": None if chave == "PT" else _pais(chave),
            "linhas": sorted(grupos[chave], key=lambda li: (li["data"], li["descricao"])),
            "total": _soma(li["valor"] for li in grupos[chave]),
        }
        for chave in chaves
    ]


def _dividendos(db: Session, ativos: list[Ativo], ano: int) -> list[dict]:
    linhas = []
    for ativo in ativos:
        for m in _movimentos(db, ativo):
            if m.tipo_movimento.value != "dividendo" or m.data.year != ano:
                continue
            linhas.append(
                {
                    "data": m.data,
                    "descricao": ativo.nome,
                    "valor": arredondar(abs(exato(m.valor_total))),
                    "pais": _pais(ativo.pais_emitente or ativo.pais),
                    # Pago por uma corretora portuguesa, já com a retenção na fonte
                    "portugues": ativo.pais == "PT",
                }
            )
    return _agrupar_por_origem(linhas)


def _juros(db: Session, ano: int) -> list[dict]:
    transacoes = (
        db.query(Transacao)
        .join(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)
        .filter(Subcategoria.juros_irs == True, extract("year", Transacao.data) == ano)
        .options(joinedload(Transacao.conta))
        .all()
    )
    linhas = []
    for t in transacoes:
        # Uma transação sem conta conta como portuguesa, o país por omissão
        pais = t.conta.pais if t.conta else "PT"
        linhas.append(
            {
                "data": t.data,
                "descricao": t.descricao,
                "conta": t.conta.nome if t.conta else None,
                "valor": arredondar(t.valor),
                "pais": _pais(pais),
                "portugues": pais == "PT",
            }
        )
    return _agrupar_por_origem(linhas)


def _pendentes(db: Session, ano: int) -> int:
    """As transações do ano por tratar como ativo: vendas ou dividendos que
    ainda não estão no relatório (a mesma condição de `/patrimonio/pendentes`)."""
    tratadas = db.query(MovimentoAtivo.transacao_id).filter(MovimentoAtivo.transacao_id != None)
    return (
        db.query(Transacao)
        .join(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)
        .filter(
            Subcategoria.trata_patrimonio == True,
            extract("year", Transacao.data) == ano,
            Transacao.id.not_in(tratadas),
        )
        .count()
    )


def relatorio_do_ano(db: Session, ano: int) -> dict:
    ativos = _ativos_do_irs(db)
    linhas = []
    for ativo in ativos:
        # Sem unidades não há lotes: um bem vende-se por inteiro e não entra aqui
        if ativo.tipo.tem_unidades:
            linhas += _linhas_de_venda(ativo, _movimentos(db, ativo), ano)
    return {
        "ano": ano,
        "vendas": _agrupar_vendas(linhas),
        "dividendos": _dividendos(db, ativos, ano),
        "juros": _juros(db, ano),
        "pendentes": _pendentes(db, ano),
    }


def anos_disponiveis(db: Session) -> list[int]:
    """Os anos com vendas, dividendos ou juros, do mais recente para o mais antigo."""
    anos = set()
    for ativo in _ativos_do_irs(db):
        for m in _movimentos(db, ativo):
            venda = m.tipo_movimento.value == "venda" and ativo.tipo.tem_unidades
            if venda or m.tipo_movimento.value == "dividendo":
                anos.add(m.data.year)
    datas_juros = (
        db.query(Transacao.data)
        .join(Subcategoria, Transacao.subcategoria_id == Subcategoria.id)
        .filter(Subcategoria.juros_irs == True)
    )
    anos |= {data.year for (data,) in datas_juros}
    return sorted(anos, reverse=True)

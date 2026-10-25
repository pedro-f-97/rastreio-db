"""Testes de API de `GET /api/estatisticas/detalhe-mensal`.

O que fica fixado
-----------------
O ponto é a falta de validação dos parâmetros `ano` e `mes` de
`detalhe_mensal`. A função constrói `inicio = date(ano, mes, 1)` e
`fim = date(ano, mes, calendar.monthrange(ano, mes)[1])` sem limites, e o
`date()` levanta `ValueError` tanto para o mês fora de 1..12 como para o ano
fora de 1..9999 — nunca o `calendar.monthrange` chega a ser avaliado:

* `ano=2024, mes=13` → `ValueError: month must be in 1..12, not 13`;
* `ano=2024, mes=0`  → `ValueError: month must be in 1..12, not 0`;
* `ano=0, mes=6`     → `ValueError: year must be in 1..9999, not 0`;
* `ano=2024, mes=12` → válido, devolve 200 (confirmado com BD vazia antes de
  escrever o teste).

A correcção alinha com o resto do projecto: `listar_transacoes` já usa
`Query(None, ge=1, le=12)` para o mês e `Query(None, ge=2000)` para o ano. Na
rota passa a ser `ano: int = Query(ge=2000, le=9999)` e `mes: int =
Query(ge=1, le=12)` — `Query` sem `default` mantém os dois parâmetros
**obrigatórios**, pelo que pedir sem `?ano=` continua a dar 422. O `le=9999` é
o teto do `date()` (ano máximo suportado) e o `ge=2000` alinha com o mesmo
limite de `listar_transacoes`.

Nos três primeiros testes o `TestClient` do `conftest.py` tem
`raise_server_exceptions=True`, por isso a excepção original (`ValueError`) é
re-levanada no `client.get(...)` e rebenta no corpo do teste: a corrida
vermelha mostra as três como **FAILED** com `ValueError` no rastreio (não são
falhas de asserção, e não são `ERROR` do pytest, que reserva esse rótulo para
excepções em fixtures) — em produção, sem a correcção, o FastAPI devolveria
500.

Rota real: `GET /api/estatisticas/detalhe-mensal?ano=&mes=` (prefixo `api` do
`main.py` + prefixo `/estatisticas` do router de estatísticas).

Valores esperados
-----------------
Escritos à mão, como constantes: 422 para os três valores inválidos e 200
para o válido, com o corpo `[]` (a base de dados de teste está vazia, e
`_query_transacoes_mes` devolve uma lista vazia de linhas). Nenhum teste
assenta na data de hoje nem toca na base de dados real.
"""

from datetime import date

import pytest

from database import Categoria, ClasseDespesa, Subcategoria, TipoCategoria, Transacao


def test_detalhe_mensal_mes_13_da_422(client):
    """`mes=13` é rejeitado pelo `Query(ge=1, le=12)`, com 422.

    Antes da correcção o `date(2024, 13, 1)` do `inicio` de `detalhe_mensal`
    levantava `ValueError` e o `TestClient` re-levantava a excepção em vez de
    responder;
    em produção era 500. O Pydantic roda agora a validação de `Query` antes da
    rota e devolve 422.

    Não pede `session`: com o parâmetro inválido nada é lido da base de
    dados, e semeá-la só esconderia que a validação acontece antes de tudo.
    """
    r = client.get("/api/estatisticas/detalhe-mensal?ano=2024&mes=13")

    assert r.status_code == 422


def test_detalhe_mensal_mes_0_da_422(client):
    """`mes=0` é rejeitado da mesma forma: `ge=1` corta mesmo antes de 1.

    Cálculo à mão: `0 < 1`, logo o `Query(ge=1, le=12)` falha logo no limite
    de baixo. Antes da correcção `date(2024, 0, 1)` levantava `ValueError`
    (mês fora de 1..12), o mesmo de `mes=13`.

    Não pede `session`, pela mesma razão do teste anterior.
    """
    r = client.get("/api/estatisticas/detalhe-mensal?ano=2024&mes=0")

    assert r.status_code == 422


def test_detalhe_mensal_ano_0_da_422(client):
    """`ano=0` é rejeitado pelo `ge=2000`.

    Cálculo à mão: `0 < 2000`, logo o `Query(ge=2000, le=9999)` falha no
    limite de baixo. Antes da correcção `date(0, 6, 1)` levantava
    `ValueError: year must be in 1..9999` — é o valor que o utilizador mediu na
    sonda e que estoura o 500.

    Não pede `session`, pela mesma razão dos anteriores.
    """
    r = client.get("/api/estatisticas/detalhe-mensal?ano=0&mes=6")

    assert r.status_code == 422


def test_detalhe_mensal_mes_12_com_bd_vazia_da_200(client):
    """O controlo: `mes=12` válido responde 200 com o corpo vazio.

    Confirmado antes de escrever este teste (sonda em `/tmp`, BD vazia): o
    endpoint responde 200 com `[]`, porque `_query_transacoes_mes` devolve
    uma lista vazia e `_agregar_por_categoria([])` devolve `{}`. Este teste já
    passava antes da correcção; serve de controlo para os anteriores não
    falharem por uma razão alheia à validação (por exemplo um 500 de
    serialização).

    Não pede `session`: o corpo vazio também não depende de dados semeados.
    """
    r = client.get("/api/estatisticas/detalhe-mensal?ano=2024&mes=12")

    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# Auxiliares dos testes novos (por-categoria, por-subcategoria, resumo-mensal)
# ---------------------------------------------------------------------------


def semear_categoria(session, nome, tipo):
    categoria = Categoria(nome=nome, tipo=tipo)
    session.add(categoria)
    session.commit()
    return categoria


def semear_subcategoria(session, nome, categoria):
    subcategoria = Subcategoria(nome=nome, categoria_id=categoria.id)
    session.add(subcategoria)
    session.commit()
    return subcategoria


def semear_transacao(session, data, descricao, valor, categoria, subcategoria=None):
    transacao = Transacao(
        data=data,
        descricao=descricao,
        valor=valor,
        categoria_id=categoria.id,
        subcategoria_id=subcategoria.id if subcategoria else None,
    )
    session.add(transacao)
    session.commit()
    return transacao


# ---------------------------------------------------------------------------
# A1/A2 — GET /api/estatisticas/resumo-mensal
# ---------------------------------------------------------------------------


def test_resumo_mensal_agrega_por_mes_e_calcula_poupanca_media_e_mediana(client, session):
    """O resumo-mensal agrega por mês e calcula poupança, média e mediana.

    Cenário semeado:
      2025-03-05  Receita       +1000,00  (ramo A de _calculate_totals)
      2025-03-10  Casa           -300,00  (ramo C)
      2025-03-18  Casa            +50,00  reembolso (ramo C, com sinal +)
      2025-04-02  Transferência  -500,00  (mês só com transferência)
      2025-06-25  Investimento  -1000,00  (mês só com investimento)

    Cálculo à mão, mês a mês:
      março: receitas = 1000,0; despesas = -300,0 + 50,0 = -250,0;
        poupança = round(1000,0 + (-250,0), 2) = 750,0 (o `poupanca` de
        `resumo_mensal`) e o investimento não entra na poupança
      abril: só transferência: _calculate_totals ignora-a (o seu ramo de
        transferências), mas `todos_meses` não filtra transferências e o ciclo
        seguinte acrescenta o mês a zeros -> aparece no output a zeros. É a
        mesma convenção do denominador das médias no `/por-categoria` (ver
        `docs/decisoes.md`).
      junho: só investimento: a chave do mês é criada com investimento
        -1000,0 e receitas/despesas a zero.
      fevereiro (sem transacções) não está em `todos_meses`, por isso não
      aparece em lado nenhum.

    A despesa de cada mês vem também separada por classe; aqui nenhuma
    transacção tem subcategoria, por isso a de março (-250,0) fica toda em
    `despesa_sem_classe` e as outras classes a zero.

    A resposta tem só os meses: a média e a mediana calculam-se na página.

    Estado final da BD: as 5 transacções continuam (o GET não escreve).
    """
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    transferencia = semear_categoria(session, "Transferência", TipoCategoria.transferencia)
    investimento = semear_categoria(session, "Investimento", TipoCategoria.investimento)

    semear_transacao(session, date(2025, 3, 5), "Ordenado", 1000.00, receita)
    semear_transacao(session, date(2025, 3, 10), "Renda", -300.00, casa)
    semear_transacao(session, date(2025, 3, 18), "Reembolso seguros", 50.00, casa)
    semear_transacao(session, date(2025, 4, 2), "Para poupança", -500.00, transferencia)
    semear_transacao(session, date(2025, 6, 25), "Comprar ETF", -1000.00, investimento)

    r = client.get("/api/estatisticas/resumo-mensal")

    assert r.status_code == 200
    assert r.json() == {
        "meses": [
            {
                "ano": 2025,
                "mes": 3,
                "receitas": 1000.0,
                "despesas": -250.0,
                "investimento": 0.0,
                "poupanca": 750.0,
                "em_curso": False,
                "despesa_essencial": 0.0,
                "despesa_evitavel": 0.0,
                "despesa_extraordinaria": 0.0,
                "despesa_sem_classe": -250.0,
            },
            {
                "ano": 2025,
                "mes": 4,
                "receitas": 0.0,
                "despesas": 0.0,
                "investimento": 0.0,
                "poupanca": 0.0,
                "em_curso": False,
                "despesa_essencial": 0.0,
                "despesa_evitavel": 0.0,
                "despesa_extraordinaria": 0.0,
                "despesa_sem_classe": 0.0,
            },
            {
                "ano": 2025,
                "mes": 6,
                "receitas": 0.0,
                "despesas": 0.0,
                "investimento": -1000.0,
                "poupanca": 0.0,
                "em_curso": False,
                "despesa_essencial": 0.0,
                "despesa_evitavel": 0.0,
                "despesa_extraordinaria": 0.0,
                "despesa_sem_classe": 0.0,
            },
        ],
    }
    assert session.query(Transacao).count() == 5


def test_resumo_mensal_com_bd_vazia_devolve_meses_vazio(client, session):
    """BD vazia: `meses` vazio.

    Cálculo à mão: sem transacções, `meses` (de _calculate_totals) e
    `todos_meses` estão vazios, e o ciclo sobre os meses não corre. Sem
    dependência da data actual.
    """
    r = client.get("/api/estatisticas/resumo-mensal")

    assert r.status_code == 200
    assert r.json() == {"meses": []}
    assert session.query(Transacao).count() == 0


# ---------------------------------------------------------------------------
# A3/A4 — GET /api/estatisticas/por-categoria
# ---------------------------------------------------------------------------


def test_por_categoria_media_e_mediana_mensais_com_zeros(client, session):
    """A média e a mediana usam os mesmos meses, e os meses vazios contam zero.

    Cenário semeado:
      2025-03-10  Casa/Renda       -100,00
      2025-03-20  Casa (sem sub)    -30,00
      2025-04-02  Transferência    -500,00  (mês só com transferência)
      2025-05-05  Casa/Renda        -40,00
      2025-06-02  Casa (sem sub)    -30,00

    Cálculo à mão:
      meses_distintos = 4 (mar, abr, mai, jun): a query `q_meses` de
      `por_categoria` conta os meses de TODAS as transacções, sem excluir
      transferências, e a query de totais exclui-as (o seu `filter` de
      transferências) -> o mês 04 só com transferências entra
      no denominador sem entrar no numerador. É a convenção registada em
      `docs/decisoes.md`.

      A query agrupa por (ano, mes, categoria, subcategoria); a categoria
      soma as linhas de cada mês: o mês 03 é Renda -100 + "Sem subcategoria"
      -30 = -130. Os meses sem movimentos contam como zero, na média e na
      mediana (antes, a mediana era por linha e sem os zeros).

      Casa, totais mensais [mar -130, abr 0, mai -40, jun -30]:
        media   = round(-200 / 4, 2) = -50,0 (sem o mês 04 no denominador
                seria round(-200/3, 2) = -66.67)
        mediana = median([-130, -40, -30, 0]) = (-40 + -30) / 2 = -35,0
                (coincide com a mediana antiga por linha; o teste
                `test_por_categoria_mediana_por_mes_e_nao_por_subcategoria`
                separa os dois cálculos)
      Renda, [mar -100, abr 0, mai -40, jun 0]:
        media   = round(-140 / 4, 2) = -35,0
        mediana = median([-100, -40, 0, 0]) = (-40 + 0) / 2 = -20,0
      Sem subcategoria, [mar -30, abr 0, mai 0, jun -30]:
        media   = round(-60 / 4, 2) = -15,0
        mediana = median([-30, -30, 0, 0]) = (-30 + 0) / 2 = -15,0

      Transferência não aparece (o `filter` de transferências da query).

    A query só ordena por (ano, mes) no `order_by` e não por subcategoria:
    a ordem das subs dentro de cada categoria segue a ordem das linhas do
    SQLite no GROUP BY, por isso as subcategorias são assertidas por
    conteúdo, não por ordem (como no por-subcategoria; ao contrário do
    detalhe-mensal, que ordena as subs com `sorted(..., reverse=True)`).

    Estado final da BD: as 5 transacções continuam.
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    renda = semear_subcategoria(session, "Renda", casa)
    transferencia = semear_categoria(session, "Transferência", TipoCategoria.transferencia)

    semear_transacao(session, date(2025, 3, 10), "Renda", -100.00, casa, renda)
    semear_transacao(session, date(2025, 3, 20), "Água", -30.00, casa)
    semear_transacao(session, date(2025, 4, 2), "Para poupança", -500.00, transferencia)
    semear_transacao(session, date(2025, 5, 5), "Renda", -40.00, casa, renda)
    semear_transacao(session, date(2025, 6, 2), "Luz", -30.00, casa)

    r = client.get("/api/estatisticas/por-categoria")

    assert r.status_code == 200
    assert len(r.json()) == 1
    casa_r = r.json()[0]
    assert casa_r["categoria_id"] == casa.id
    assert casa_r["categoria_nome"] == "Casa"
    assert casa_r["mediana"] == -35.0
    assert casa_r["media"] == -50.0
    assert {
        s["subcategoria_nome"]: (s["mediana"], s["media"]) for s in casa_r["subcategorias"]
    } == {
        "Renda": (-20.0, -35.0),
        "Sem subcategoria": (-15.0, -15.0),
    }
    assert session.query(Transacao).count() == 5


def test_por_categoria_com_ano_filtra_meses_e_transacoes(client, session):
    """O parâmetro `ano` corta meses_distintos e as linhas de totais.

    Mesmos seeds do teste anterior, mais transacções de 2026. Com ano=2025,
    os dois filtros de `ano` de `por_categoria` (o de `q_meses` e o da query de
    totais) deixam de fora 2026: a resposta é
    idêntica à do teste anterior (meses_distintos = 4 e os mesmos valores).
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    renda = semear_subcategoria(session, "Renda", casa)
    transferencia = semear_categoria(session, "Transferência", TipoCategoria.transferencia)

    semear_transacao(session, date(2025, 3, 10), "Renda", -100.00, casa, renda)
    semear_transacao(session, date(2025, 3, 20), "Água", -30.00, casa)
    semear_transacao(session, date(2025, 4, 2), "Para poupança", -500.00, transferencia)
    semear_transacao(session, date(2025, 5, 5), "Renda", -40.00, casa, renda)
    semear_transacao(session, date(2025, 6, 2), "Luz", -30.00, casa)
    semear_transacao(session, date(2026, 2, 10), "Renda", -5.00, casa, renda)
    semear_transacao(session, date(2026, 3, 20), "Para poupança", -100.00, transferencia)

    r = client.get("/api/estatisticas/por-categoria", params={"ano": 2025})

    assert r.status_code == 200
    assert len(r.json()) == 1
    casa_r = r.json()[0]
    assert casa_r["categoria_id"] == casa.id
    assert casa_r["categoria_nome"] == "Casa"
    assert casa_r["mediana"] == -35.0
    assert casa_r["media"] == -50.0
    assert {
        s["subcategoria_nome"]: (s["mediana"], s["media"]) for s in casa_r["subcategorias"]
    } == {
        "Renda": (-20.0, -35.0),
        "Sem subcategoria": (-15.0, -15.0),
    }
    assert session.query(Transacao).count() == 7


def test_por_categoria_mediana_por_mes_e_nao_por_subcategoria(client, session):
    """A mediana da categoria é a dos totais mensais, com os meses vazios a zero.

    Antes da correcção a mediana era por linha. O cenário foi escolhido para
    que as quatro maneiras de calcular dêem quatro valores diferentes.

    Cenário semeado (meses_distintos = 4: jan, fev, mar, abr):
      2025-01-05  Casa/A   -100,00
      2025-01-06  Casa/B    -60,00
      2025-02-07  Casa/A    -20,00
      2025-03-08  Lazer      -5,00   (o único movimento de março)
      2025-04-09  Casa/B    -10,00

    Casa, totais mensais [jan -160, fev -20, mar 0, abr -10]:
      mediana = median([-160, -20, -10, 0]) = (-20 + -10) / 2 = -15,0
      media   = -190 / 4 = -47,5
      Os cálculos rejeitados davam: por linha sem zeros
      median([-100, -60, -20, -10]) = -40,0; por mês sem zeros
      median([-160, -20, -10]) = -20,0.
    Casa/A, [-100, -20, 0, 0]: mediana (-20 + 0) / 2 = -10,0; media -120/4 = -30,0
    Casa/B, [-60, 0, 0, -10]:  mediana (-10 + 0) / 2 = -5,0;  media -70/4 = -17,5
    Lazer (esporádica), [0, 0, -5, 0]: mediana 0,0; media -5/4 = -1,25
      Sem os zeros, a «mediana mensal» do Lazer seria -5,0, um gasto que só
      houve num mês em quatro.
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    sub_a = semear_subcategoria(session, "A", casa)
    sub_b = semear_subcategoria(session, "B", casa)
    lazer = semear_categoria(session, "Lazer", TipoCategoria.despesa)

    semear_transacao(session, date(2025, 1, 5), "A1", -100.00, casa, sub_a)
    semear_transacao(session, date(2025, 1, 6), "B1", -60.00, casa, sub_b)
    semear_transacao(session, date(2025, 2, 7), "A2", -20.00, casa, sub_a)
    semear_transacao(session, date(2025, 3, 8), "Cinema", -5.00, lazer)
    semear_transacao(session, date(2025, 4, 9), "B2", -10.00, casa, sub_b)

    r = client.get("/api/estatisticas/por-categoria")

    assert r.status_code == 200
    por_nome = {c["categoria_nome"]: c for c in r.json()}
    assert set(por_nome) == {"Casa", "Lazer"}

    assert por_nome["Casa"]["mediana"] == -15.0
    assert por_nome["Casa"]["media"] == -47.5
    assert {
        s["subcategoria_nome"]: (s["mediana"], s["media"])
        for s in por_nome["Casa"]["subcategorias"]
    } == {
        "A": (-10.0, -30.0),
        "B": (-5.0, -17.5),
    }

    assert por_nome["Lazer"]["mediana"] == 0.0
    assert por_nome["Lazer"]["media"] == -1.25
    assert [
        (s["subcategoria_nome"], s["mediana"], s["media"])
        for s in por_nome["Lazer"]["subcategorias"]
    ] == [
        ("Sem subcategoria", 0.0, -1.25),
    ]


def test_por_categoria_devolve_o_tipo_de_cada_categoria(client, session):
    """Cada categoria traz o seu tipo, para a página agrupar a tabela.

    Cenário semeado (um só mês, 2025-03):
      Casa         despesa        -50,00
      Receita      receita      +1000,00
      Investimento investimento  -200,00

    Cálculo à mão: com um só mês, a média e a mediana de cada categoria são o
    próprio total. O tipo é o da categoria, escrito no seu `tipo`.
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    investimento = semear_categoria(session, "Investimento", TipoCategoria.investimento)

    semear_transacao(session, date(2025, 3, 2), "Água", -50.00, casa)
    semear_transacao(session, date(2025, 3, 5), "Vencimento", 1000.00, receita)
    semear_transacao(session, date(2025, 3, 9), "ETF", -200.00, investimento)

    r = client.get("/api/estatisticas/por-categoria")

    assert r.status_code == 200
    assert {c["categoria_nome"]: (c["tipo"], c["media"], c["mediana"]) for c in r.json()} == {
        "Casa": (TipoCategoria.despesa.value, -50.0, -50.0),
        "Receita": (TipoCategoria.receita.value, 1000.0, 1000.0),
        "Investimento": (TipoCategoria.investimento.value, -200.0, -200.0),
    }


# ---------------------------------------------------------------------------
# A5/A6 — GET /api/estatisticas/por-subcategoria
# ---------------------------------------------------------------------------


def test_por_subcategoria_soma_em_centimos_ordena_categorias_e_esconde_zero(client, session):
    """Somatório em cêntimos, categorias por total desc, subs por conteúdo.

    Cenário semeado:
      2025-03-02  Casa/Renda       -100,00
      2025-03-09  Casa (sem sub)    -30,00
      2025-03-20  Receita/Salário  +1500,00
      2025-04-03  Transferência    -500,00   (filtrada pela query de
                                                 `por_subcategoria`)
      2025-06-05  Lazer/Convívio     +5,00
      2025-06-06  Lazer/Convívio     -5,00    (net 0 -> escondida)

    Cálculo à mão, em cêntimos inteiros (round(valor*100) na soma de
    `por_subcategoria`):
      Casa      = -10000 - 3000 = -13000 -> total -130,0
        Renda   = -10000                  -> -100,0
        sem sub = -3000                   -> -30,0
      Receita   = 150000                  -> 1500,0
        Salário = 150000                  -> 1500,0
      Lazer     = +500 - 500 = 0 -> abs(0) > 0 é falso no
        `if abs(total_cat) > 0`, a categoria e a subcategoria desaparecem do
        output

    Ordenação das categorias: key = c["total"], reverse=True (no `sorted`
    final) -> descendente -> Receita (1500,0) antes de Casa (-130,0).

    As subcategorias NÃO são ordenadas neste endpoint (o ciclo que as acumula
    passa-as tal e qual) e a query nem tem ORDER BY (o `q.all()` da consulta):
    por isso são assertidas por conteúdo, não por ordem — ao contrário do
    detalhe-mensal, que ordena as subs com `sorted(..., reverse=True)` e as
    categorias no `sorted` final de `resultado_final`.

    Estado final da BD: as 6 transacções continuam.
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    renda = semear_subcategoria(session, "Renda", casa)
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    salario = semear_subcategoria(session, "Salário", receita)
    lazer = semear_categoria(session, "Lazer", TipoCategoria.despesa)
    convivio = semear_subcategoria(session, "Convívio", lazer)
    transferencia = semear_categoria(session, "Transferência", TipoCategoria.transferencia)

    semear_transacao(session, date(2025, 3, 2), "Renda", -100.00, casa, renda)
    semear_transacao(session, date(2025, 3, 9), "Água", -30.00, casa)
    semear_transacao(session, date(2025, 3, 20), "Vencimento", 1500.00, receita, salario)
    semear_transacao(session, date(2025, 4, 3), "Para poupança", -500.00, transferencia)
    semear_transacao(session, date(2025, 6, 5), "Jantar", 5.00, lazer, convivio)
    semear_transacao(session, date(2025, 6, 6), "Devolução jantar", -5.00, lazer, convivio)

    r = client.get("/api/estatisticas/por-subcategoria")

    assert r.status_code == 200
    resposta = r.json()

    assert [c["categoria_nome"] for c in resposta] == ["Receita", "Casa"]

    por_nome = {c["categoria_nome"]: c for c in resposta}
    assert por_nome["Casa"]["categoria_id"] == casa.id
    # O tipo da categoria vai na resposta, para a página filtrar as despesas
    assert por_nome["Casa"]["tipo"] == TipoCategoria.despesa.value
    assert por_nome["Casa"]["total"] == -130.0
    assert {s["subcategoria_nome"]: s["total"] for s in por_nome["Casa"]["subcategorias"]} == {
        "Renda": -100.0,
        "Sem subcategoria": -30.0,
    }
    assert por_nome["Receita"]["categoria_id"] == receita.id
    assert por_nome["Receita"]["tipo"] == TipoCategoria.receita.value
    assert por_nome["Receita"]["total"] == 1500.0
    assert {s["subcategoria_nome"]: s["total"] for s in por_nome["Receita"]["subcategorias"]} == {
        "Salário": 1500.0,
    }
    assert len(resposta) == 2
    assert session.query(Transacao).count() == 6


def test_por_subcategoria_com_ano_ignora_outros_anos(client, session):
    """O filtro `ano` corta as linhas de outros anos (o `filter` de `ano` da
    query de `por_subcategoria`).

    Cenário semeado:
      2025-03-10  Casa/Renda  -100,00
      2026-02-01  Casa (sem)   -1,00

    Cálculo à mão:
      com ano=2025: Casa = -100,00 -> -10000 cêntimos -> total -100,0
      sem ano:      Casa = -100,00 + (-1,00) = -101,00 -> -10100 -> -101,0
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    renda = semear_subcategoria(session, "Renda", casa)

    semear_transacao(session, date(2025, 3, 10), "Renda", -100.00, casa, renda)
    semear_transacao(session, date(2026, 2, 1), "Água", -1.00, casa)

    r = client.get("/api/estatisticas/por-subcategoria", params={"ano": 2025})

    assert r.status_code == 200
    assert r.json() == [
        {
            "categoria_id": casa.id,
            "categoria_nome": "Casa",
            "tipo": TipoCategoria.despesa.value,
            "total": -100.0,
            "subcategorias": [{"subcategoria_nome": "Renda", "total": -100.0}],
        }
    ]

    r_sem_ano = client.get("/api/estatisticas/por-subcategoria")
    assert r_sem_ano.status_code == 200
    assert r_sem_ano.json()[0]["total"] == -101.0


# ---------------------------------------------------------------------------
# A7 — GET /api/estatisticas/detalhe-mensal com dados
# ---------------------------------------------------------------------------


def test_detalhe_mensal_agrega_subcategorias_e_ordena_por_total(client, session):
    """Agregação por categoria/subcategoria, ordenada por total desc.

    Cenário semeado em 2025-03 (mais uma transacção em abril):
      03-01  Casa/Renda           -800,00
      03-05  Casa/Renda           -200,00
      03-10  Casa/Supermercado    -150,25
      03-15  Casa (sem sub)        -50,00
      03-20  Receita/Salário     +1500,00
      03-25  Investimento/Ações  -1000,00
      03-30  Transferência        -500,00   (excluída pelo ramo das
                                               transferências de
                                               `_query_transacoes_mes`)
      04-01  Casa/Renda            -10,00   (fora do intervalo, nos filtros de
                                               `data` de `_query_transacoes_mes`)

    Cálculo à mão, em cêntimos (round(valor*100) em `_agregar_por_categoria`):
      Casa  = -80000 - 20000 - 15025 - 5000 = -120025 -> total -1200,25
        Renda        = -80000 - 20000     = -100000 -> -1000,0
        Supermercado = -15025                      -> -150,25
        Sem sub      = -5000                       -> -50,0
      Receita      = 150000 -> 1500,0
        Salário    = 150000 -> 1500,0
      Investimento = -100000 -> -1000,0
        Ações      = -100000 -> -1000,0

    Ordenações (ambas descendentes por total -> a mais negativa vai última):
      subcategorias: key = s["total"], reverse=True (o `sorted` de
        `detalhe_mensal`) ->
        Sem subcategoria (-50,0), Supermercado (-150,25), Renda (-1000,0)
      categorias: key = c["total"], reverse=True (o `sorted` final de
        `resultado_final`) ->
        Receita (1500,0), Investimento (-1000,0), Casa (-1200,25)

      `tipo` = categoria_tipo.value (o `cat["categoria_tipo"].value` de
        `detalhe_mensal`): "receita", "investimento" e "despesa"
        respectivamente.

    Estado final da BD: as 8 transacções continuam.
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    renda = semear_subcategoria(session, "Renda", casa)
    supermercado = semear_subcategoria(session, "Supermercado", casa)
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    salario = semear_subcategoria(session, "Salário", receita)
    investimento = semear_categoria(session, "Investimento", TipoCategoria.investimento)
    acoes = semear_subcategoria(session, "Ações", investimento)
    transferencia = semear_categoria(session, "Transferência", TipoCategoria.transferencia)

    semear_transacao(session, date(2025, 3, 1), "Renda", -800.00, casa, renda)
    semear_transacao(session, date(2025, 3, 5), "Renda", -200.00, casa, renda)
    semear_transacao(session, date(2025, 3, 10), "Feira", -150.25, casa, supermercado)
    semear_transacao(session, date(2025, 3, 15), "Combustível", -50.00, casa)
    semear_transacao(session, date(2025, 3, 20), "Vencimento", 1500.00, receita, salario)
    semear_transacao(session, date(2025, 3, 25), "Comprar ETF", -1000.00, investimento, acoes)
    semear_transacao(session, date(2025, 3, 30), "Para poupança", -500.00, transferencia)
    semear_transacao(session, date(2025, 4, 1), "Renda", -10.00, casa, renda)

    r = client.get("/api/estatisticas/detalhe-mensal?ano=2025&mes=3")

    assert r.status_code == 200
    assert r.json() == [
        {
            "categoria_id": receita.id,
            "categoria_nome": "Receita",
            "tipo": "receita",
            "total": 1500.0,
            "subcategorias": [{"subcategoria_nome": "Salário", "total": 1500.0}],
        },
        {
            "categoria_id": investimento.id,
            "categoria_nome": "Investimento",
            "tipo": "investimento",
            "total": -1000.0,
            "subcategorias": [{"subcategoria_nome": "Ações", "total": -1000.0}],
        },
        {
            "categoria_id": casa.id,
            "categoria_nome": "Casa",
            "tipo": "despesa",
            "total": -1200.25,
            "subcategorias": [
                {"subcategoria_nome": "Sem subcategoria", "total": -50.0},
                {"subcategoria_nome": "Supermercado", "total": -150.25},
                {"subcategoria_nome": "Renda", "total": -1000.0},
            ],
        },
    ]
    assert session.query(Transacao).count() == 8


# ---------------------------------------------------------------------------
# Empates no meio cêntimo arredondam para longe de zero
# ---------------------------------------------------------------------------


def test_por_categoria_media_e_mediana_no_meio_centimo(client, session):
    """Os números da categoria Entretenimento em 2025, nos dados reais.

    Cenário semeado: dois meses, um com -96,70 e outro com -62,99.

    Cálculo à mão:
      meses_distintos = 2, totais mensais [-96,70, -62,99]
      mediana = (-96,70 + -62,99) / 2 = -159,69 / 2 = -79,845
      media   = -159,69 / 2 = -79,845
      empate no meio cêntimo, metade para longe de zero -> -79,85
      mes_tipico = media, porque não há extraordinárias -> -79,85

    Antes da correcção ambas davam -79,84: em float, -79,845 é -79,84499999...
    """
    lazer = semear_categoria(session, "Entretenimento", TipoCategoria.despesa)
    semear_transacao(session, date(2025, 3, 10), "Cinema", -96.70, lazer)
    semear_transacao(session, date(2025, 4, 10), "Concerto", -62.99, lazer)

    r = client.get("/api/estatisticas/por-categoria")

    assert r.status_code == 200
    assert r.json()[0]["mediana"] == -79.85
    assert r.json()[0]["media"] == -79.85
    assert r.json()[0]["subcategorias"] == [
        {
            "subcategoria_nome": "Sem subcategoria",
            "mediana": -79.85,
            "media": -79.85,
            "mes_tipico": -79.85,
        },
    ]


def test_por_categoria_mediana_sem_ruido_da_soma_em_float(client, session):
    """A mediana é calculada em Decimal, e não sobre o ruído da soma em float.

    Cenário semeado: dois meses, um com -200,00 e outro com -197,79.

    Cálculo à mão:
      mediana = (-200,00 + -197,79) / 2 = -397,79 / 2 = -198,895
      empate no meio cêntimo, metade para longe de zero -> -198,90
      media   = -397,79 / 2 = -198,895 -> -198,90

    A mediana sobre os floats daria -198,89499999999998, que nem o
    arredondamento pelo valor escrito salva: ficaria -198,89.
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    semear_transacao(session, date(2025, 3, 10), "Renda", -200.00, casa)
    semear_transacao(session, date(2025, 4, 10), "Renda", -197.79, casa)

    r = client.get("/api/estatisticas/por-categoria")

    assert r.status_code == 200
    assert r.json()[0]["mediana"] == -198.90
    assert r.json()[0]["media"] == -198.90


# ---------------------------------------------------------------------------
# Classificação das subcategorias de despesa: mês típico e extraordinárias
# ---------------------------------------------------------------------------


def semear_classificadas(session):
    """Casa com uma subcategoria de cada classe, uma sem classe e transacções
    sem subcategoria; uma receita e uma transferência.

      2025-01-05  Receita/Ordenado      +1000,00
      2025-01-08  Casa/Renda             -300,00  essencial
      2025-01-12  Casa/Restaurantes       -40,00  evitável
      2025-01-15  Casa/Carro            -5000,00  extraordinária
      2025-01-20  Casa/Outros             -10,00  sem classificação
      2025-01-22  Casa (sem sub)           -5,00
      2025-01-25  Transferência          -200,00  fora das contas
      2025-02-03  Casa/Renda             -300,00  essencial
      2025-02-10  Casa/Seguro            -360,00  essencial, anual
      2025-02-14  Casa/Carro             +500,00  reembolso, extraordinária
      2025-02-20  Casa/Restaurantes       -60,00  evitável
      2026-03-01  Casa/Carro             -100,00  extraordinária
    """
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    transferencia = semear_categoria(session, "Transferência", TipoCategoria.transferencia)
    ordenado = semear_subcategoria(session, "Ordenado", receita)
    subs = {}
    for nome, classe in (
        ("Renda", ClasseDespesa.essencial),
        ("Seguro", ClasseDespesa.essencial),
        ("Restaurantes", ClasseDespesa.evitavel),
        ("Carro", ClasseDespesa.extraordinaria),
        ("Outros", None),
    ):
        subs[nome] = semear_subcategoria(session, nome, casa)
        subs[nome].classe_despesa = classe
    session.commit()

    semear_transacao(session, date(2025, 1, 5), "Ordenado", 1000.00, receita, ordenado)
    semear_transacao(session, date(2025, 1, 8), "Renda", -300.00, casa, subs["Renda"])
    semear_transacao(session, date(2025, 1, 12), "Jantar", -40.00, casa, subs["Restaurantes"])
    semear_transacao(session, date(2025, 1, 15), "Twingo", -5000.00, casa, subs["Carro"])
    semear_transacao(session, date(2025, 1, 20), "Pilhas", -10.00, casa, subs["Outros"])
    semear_transacao(session, date(2025, 1, 22), "Selos", -5.00, casa)
    semear_transacao(session, date(2025, 1, 25), "Para poupança", -200.00, transferencia)
    semear_transacao(session, date(2025, 2, 3), "Renda", -300.00, casa, subs["Renda"])
    semear_transacao(session, date(2025, 2, 10), "Seguro", -360.00, casa, subs["Seguro"])
    semear_transacao(session, date(2025, 2, 14), "Devolução", 500.00, casa, subs["Carro"])
    semear_transacao(session, date(2025, 2, 20), "Almoço", -60.00, casa, subs["Restaurantes"])
    semear_transacao(session, date(2026, 3, 1), "Tapetes", -100.00, casa, subs["Carro"])


def test_resumo_mensal_separa_a_despesa_por_classe(client, session):
    """A despesa de cada mês vem também separada por classe.

    Cálculo à mão (a transferência fica de fora, como sempre):
      jan 2025: essencial -300; evitável -40; extraordinária -5000;
        sem classe -10 (Outros) + -5 (sem sub) = -15;
        despesas = -300 - 40 - 5000 - 15 = -5355; receitas 1000;
        poupança = 1000 - 5355 = -4355
      fev 2025: essencial -300 - 360 = -660; evitável -60;
        extraordinária +500 (o reembolso reduz a extraordinária); sem classe 0;
        despesas = -660 - 60 + 500 = -220; poupança -220
      mar 2026: extraordinária -100; despesas -100; poupança -100
    Em cada mês, as quatro classes somam a despesa.
    """
    semear_classificadas(session)

    r = client.get("/api/estatisticas/resumo-mensal")

    assert r.status_code == 200
    assert [
        (
            m["ano"],
            m["mes"],
            m["despesas"],
            m["despesa_essencial"],
            m["despesa_evitavel"],
            m["despesa_extraordinaria"],
            m["despesa_sem_classe"],
            m["receitas"],
            m["poupanca"],
        )
        for m in r.json()["meses"]
    ] == [
        (2025, 1, -5355.0, -300.0, -40.0, -5000.0, -15.0, 1000.0, -4355.0),
        (2025, 2, -220.0, -660.0, -60.0, 500.0, 0.0, 0.0, -220.0),
        (2026, 3, -100.0, 0.0, 0.0, -100.0, 0.0, 0.0, -100.0),
    ]


def test_por_categoria_mes_tipico_sem_as_extraordinarias(client, session):
    """`mes_tipico` é a média mensal sem as subcategorias extraordinárias.

    Cálculo à mão, com ano=2025: meses_distintos = 2 (jan e fev).
      Casa, totais [jan -5355, fev -220]: media = -5575 / 2 = -2787,5
        sem o Carro: [jan -355, fev -720]: mes_tipico = -1075 / 2 = -537,5
      Subcategorias (media, mes_tipico):
        Renda  -600 / 2 = -300; Seguro -360 / 2 = -180 (o anual reparte-se
        pelos meses); Restaurantes -100 / 2 = -50; Outros -10 / 2 = -5;
        Sem subcategoria -5 / 2 = -2,5; todas com mes_tipico = media
        Carro (-5000 + 500) / 2 = -2250, mes_tipico 0
        A soma dos mes_tipico, -300 - 180 - 50 - 5 - 2,5 + 0 = -537,5, é o
        da categoria.
      Receita: media = mes_tipico = 1000 / 2 = 500
    """
    semear_classificadas(session)

    r = client.get("/api/estatisticas/por-categoria", params={"ano": 2025})

    assert r.status_code == 200
    por_nome = {c["categoria_nome"]: c for c in r.json()}
    assert set(por_nome) == {"Casa", "Receita"}
    assert (por_nome["Casa"]["media"], por_nome["Casa"]["mes_tipico"]) == (-2787.5, -537.5)
    assert (por_nome["Receita"]["media"], por_nome["Receita"]["mes_tipico"]) == (500.0, 500.0)
    assert {
        s["subcategoria_nome"]: (s["media"], s["mes_tipico"])
        for s in por_nome["Casa"]["subcategorias"]
    } == {
        "Renda": (-300.0, -300.0),
        "Seguro": (-180.0, -180.0),
        "Restaurantes": (-50.0, -50.0),
        "Outros": (-5.0, -5.0),
        "Sem subcategoria": (-2.5, -2.5),
        "Carro": (-2250.0, 0),
    }


def test_extraordinarias_lista_as_transaccoes_e_o_total(client, session):
    """A lista das extraordinárias, por data, com o total; o ano filtra.

    Cálculo à mão:
      sem ano: Twingo -5000 (15/01/2025), Devolução +500 (14/02/2025),
        Tapetes -100 (01/03/2026); total = -5000 + 500 - 100 = -4600
      ano=2025: as duas primeiras; total -4500
      ano=2026: Tapetes; total -100
      ano=2024: nenhuma; total 0
    """
    semear_classificadas(session)

    r = client.get("/api/estatisticas/extraordinarias")

    assert r.status_code == 200
    assert [
        (t["data"], t["descricao"], t["categoria_nome"], t["subcategoria_nome"], t["valor"])
        for t in r.json()["transacoes"]
    ] == [
        ("2025-01-15", "Twingo", "Casa", "Carro", -5000.0),
        ("2025-02-14", "Devolução", "Casa", "Carro", 500.0),
        ("2026-03-01", "Tapetes", "Casa", "Carro", -100.0),
    ]
    assert r.json()["total"] == -4600.0

    por_ano = {
        ano: client.get("/api/estatisticas/extraordinarias", params={"ano": ano}).json()
        for ano in (2024, 2025, 2026)
    }
    assert [t["descricao"] for t in por_ano[2025]["transacoes"]] == ["Twingo", "Devolução"]
    assert por_ano[2025]["total"] == -4500.0
    assert [t["descricao"] for t in por_ano[2026]["transacoes"]] == ["Tapetes"]
    assert por_ano[2026]["total"] == -100.0
    assert por_ano[2024] == {"transacoes": [], "total": 0.0}


def test_extraordinarias_em_centimos(client, session):
    """O total soma-se em cêntimos, sem o ruído do float.

    Cálculo à mão: -0,10 - 0,20 = -0,30 (em float daria -0,30000000000000004).
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    pc = semear_subcategoria(session, "PC", casa)
    pc.classe_despesa = ClasseDespesa.extraordinaria
    session.commit()
    semear_transacao(session, date(2025, 1, 1), "Cabo", -0.10, casa, pc)
    semear_transacao(session, date(2025, 1, 2), "Ficha", -0.20, casa, pc)

    assert client.get("/api/estatisticas/extraordinarias").json()["total"] == -0.3


def test_classe_numa_categoria_que_nao_e_despesa_e_ignorada(client, session):
    """Uma classificação que ficou numa subcategoria de receita não conta.

    A API não deixa classificar fora das despesas, mas a BD pode ter uma
    (escrita à mão, ou de antes de a regra existir). As estatísticas tratam-na
    como se não estivesse lá.

    Cálculo à mão, uma receita «Prémio» de +200 em 2025-01, marcada
    extraordinária: resumo com receitas 200 e as quatro classes a zero;
    por-categoria com media = mes_tipico = 200 (um só mês), na categoria e na
    subcategoria; e a lista das extraordinárias vazia.
    """
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    premio = semear_subcategoria(session, "Prémio", receita)
    premio.classe_despesa = ClasseDespesa.extraordinaria
    session.commit()
    semear_transacao(session, date(2025, 1, 10), "Prémio", 200.00, receita, premio)

    mes = client.get("/api/estatisticas/resumo-mensal").json()["meses"][0]
    assert (mes["receitas"], mes["despesas"], mes["despesa_extraordinaria"]) == (200.0, 0.0, 0.0)
    assert mes["despesa_sem_classe"] == 0.0

    cat = client.get("/api/estatisticas/por-categoria").json()[0]
    assert (cat["media"], cat["mes_tipico"]) == (200.0, 200.0)
    assert (cat["subcategorias"][0]["media"], cat["subcategorias"][0]["mes_tipico"]) == (
        200.0,
        200.0,
    )

    assert client.get("/api/estatisticas/extraordinarias").json() == {
        "transacoes": [],
        "total": 0.0,
    }


def test_resumo_mensal_arredonda_a_despesa_de_cada_classe(client, session):
    """A despesa de cada classe arredonda-se ao cêntimo, como a despesa total.

    Cálculo à mão: -0,10 - 0,20 = -0,30 na despesa e na essencial (em float a
    soma é -0,30000000000000004).
    """
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    agua = semear_subcategoria(session, "Água", casa)
    agua.classe_despesa = ClasseDespesa.essencial
    session.commit()
    semear_transacao(session, date(2025, 1, 1), "Água", -0.10, casa, agua)
    semear_transacao(session, date(2025, 1, 2), "Água", -0.20, casa, agua)

    mes = client.get("/api/estatisticas/resumo-mensal").json()["meses"][0]

    assert (mes["despesas"], mes["despesa_essencial"]) == (-0.3, -0.3)


# ---------------------------------------------------------------------------
# O mês em curso fica de fora das médias (resumo-mensal marca-o, por-categoria
# tira-o)
# ---------------------------------------------------------------------------


@pytest.fixture
def hoje_15_abril_2025(monkeypatch):
    """Fixa o `date.today()` do router em 15/04/2025: abril é o mês em curso."""
    from datetime import date as Date

    from routers import estatisticas as estatisticas_router

    class HojeFixo(Date):
        @classmethod
        def today(cls):
            return cls(2025, 4, 15)

    monkeypatch.setattr(estatisticas_router, "date", HojeFixo)


def test_resumo_mensal_marca_so_o_mes_em_curso(client, session, hoje_15_abril_2025):
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    semear_transacao(session, date(2025, 3, 10), "Renda", -300.0, casa)
    semear_transacao(session, date(2025, 4, 2), "Renda", -300.0, casa)

    r = client.get("/api/estatisticas/resumo-mensal")

    assert [(m["mes"], m["em_curso"]) for m in r.json()["meses"]] == [(3, False), (4, True)]


@pytest.mark.parametrize("ano", [None, 2025])
def test_por_categoria_sem_o_mes_em_curso(client, session, hoje_15_abril_2025, ano):
    """Casa/Renda: -100 em fevereiro, -200 em março e -10 em abril (em curso).
    Sem abril: média (-100 - 200) / 2 = -150, mediana -150, mês típico -150. Com
    abril seria (-100 - 200 - 10) / 3 = -103,33. A Receita, só com abril, não
    tem nenhum mês completo e não aparece."""
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    renda = semear_subcategoria(session, "Renda", casa)
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    semear_transacao(session, date(2025, 2, 10), "Renda", -100.0, casa, renda)
    semear_transacao(session, date(2025, 3, 10), "Renda", -200.0, casa, renda)
    semear_transacao(session, date(2025, 4, 10), "Renda", -10.0, casa, renda)
    semear_transacao(session, date(2025, 4, 5), "Ordenado", 1000.0, receita)

    r = client.get("/api/estatisticas/por-categoria", params={"ano": ano} if ano else {})

    assert r.status_code == 200
    [cat] = r.json()
    assert cat["categoria_nome"] == "Casa"
    assert (cat["media"], cat["mediana"], cat["mes_tipico"]) == (-150.0, -150.0, -150.0)
    [sub] = cat["subcategorias"]
    assert (sub["media"], sub["mediana"], sub["mes_tipico"]) == (-150.0, -150.0, -150.0)


def test_por_categoria_de_um_ano_passado_nao_muda(client, session, hoje_15_abril_2025):
    """2024: -100 em novembro e -300 em dezembro, média -200; os -10 de abril de
    2025 (o mês em curso) são de outro ano e não entram de qualquer forma."""
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    semear_transacao(session, date(2024, 11, 10), "Renda", -100.0, casa)
    semear_transacao(session, date(2024, 12, 10), "Renda", -300.0, casa)
    semear_transacao(session, date(2025, 4, 10), "Renda", -10.0, casa)

    [cat] = client.get("/api/estatisticas/por-categoria", params={"ano": 2024}).json()

    assert (cat["media"], cat["mediana"]) == (-200.0, -200.0)


def test_por_categoria_so_com_o_mes_em_curso_fica_vazio(client, session, hoje_15_abril_2025):
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    semear_transacao(session, date(2025, 4, 10), "Renda", -10.0, casa)

    r = client.get("/api/estatisticas/por-categoria", params={"ano": 2025})

    assert r.status_code == 200
    assert r.json() == []

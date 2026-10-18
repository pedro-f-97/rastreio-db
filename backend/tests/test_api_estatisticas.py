"""Testes de API de `GET /api/estatisticas/detalhe-mensal` (D9).

O que fica fixado
-----------------
A D9 é a falta de validação dos parâmetros `ano` e `mes` de
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

from database import Categoria, Subcategoria, Transacao, TipoCategoria


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


def semear_transacao(session, data, descricao, valor, categoria,
                     subcategoria=None, reembolso=False):
    transacao = Transacao(
        data=data,
        descricao=descricao,
        valor=valor,
        reembolso=reembolso,
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
      2025-03-18  Casa            +50,00  reembolso=True (ramo D)
      2025-04-02  Transferência  -500,00  (mês só com transferência)
      2025-06-25  Investimento  -1000,00  (mês só com investimento)

    Cálculo à mão, mês a mês:
      março: receitas = 1000,0; despesas = -300,0 + 50,0 = -250,0;
        poupança = round(1000,0 + (-250,0), 2) = 750,0 (o `poupanca` de
        `resumo_mensal`) e o investimento não entra na poupança
      abril: só transferência: _calculate_totals ignora-a (o seu ramo de
        transferências), mas `todos_meses` não filtra transferências e o ciclo
        seguinte acrescenta o mês a zeros -> aparece no output a zeros. É a
        mesma raiz da D5 a entrar no denominador das médias noutro endpoint
        (DEVIDA-TECNICA: D5).
      junho: só investimento: a chave do mês é criada com investimento
        -1000,0 e receitas/despesas a zero.
      fevereiro (sem transacções) não está em `todos_meses`, por isso não
      aparece em lado nenhum.

    Média e mediana sobre totais_despesas = [-250,0, 0,0, 0,0]:
      media_mensal   = round((-250,0 + 0,0 + 0,0) / 3, 2)
                     = round(-83,333…, 2) = -83.33
      mediana_mensal = median([-250,0, 0,0, 0,0]) = 0,0 (ordenado, o central)

    Estado final da BD: as 5 transacções continuam (o GET não escreve).
    """
    receita = semear_categoria(session, "Receita", TipoCategoria.receita)
    casa = semear_categoria(session, "Casa", TipoCategoria.despesa)
    transferencia = semear_categoria(session, "Transferência", TipoCategoria.transferencia)
    investimento = semear_categoria(session, "Investimento", TipoCategoria.investimento)

    semear_transacao(session, date(2025, 3, 5), "Ordenado", 1000.00, receita)
    semear_transacao(session, date(2025, 3, 10), "Renda", -300.00, casa)
    semear_transacao(session, date(2025, 3, 18), "Reembolso seguros", 50.00, casa,
                     reembolso=True)
    semear_transacao(session, date(2025, 4, 2), "Para poupança", -500.00, transferencia)
    semear_transacao(session, date(2025, 6, 25), "Comprar ETF", -1000.00, investimento)

    r = client.get("/api/estatisticas/resumo-mensal")

    assert r.status_code == 200
    assert r.json() == {
        "meses": [
            {"ano": 2025, "mes": 3, "receitas": 1000.0, "despesas": -250.0,
             "investimento": 0.0, "poupanca": 750.0},
            {"ano": 2025, "mes": 4, "receitas": 0.0, "despesas": 0.0,
             "investimento": 0.0, "poupanca": 0.0},
            {"ano": 2025, "mes": 6, "receitas": 0.0, "despesas": 0.0,
             "investimento": -1000.0, "poupanca": 0.0},
        ],
        "media_mensal": -83.33,
        "mediana_mensal": 0.0,
    }
    assert session.query(Transacao).count() == 5


def test_resumo_mensal_com_bd_vazia_devolve_media_e_mediana_zero(client, session):
    """BD vazia: meses vazio e média/mediana em 0.

    Cálculo à mão: sem transacções, `meses` (de _calculate_totals) e
    `todos_meses` estão vazios, o ciclo sobre os meses não corre, e o cálculo
    de `media` e `mediana` cai no `else`: media = 0 e mediana = 0. Sem
    dependência da data actual.
    """
    r = client.get("/api/estatisticas/resumo-mensal")

    assert r.status_code == 200
    assert r.json() == {"meses": [], "media_mensal": 0, "mediana_mensal": 0}
    assert session.query(Transacao).count() == 0


# ---------------------------------------------------------------------------
# A3/A4 — GET /api/estatisticas/por-categoria
# ---------------------------------------------------------------------------

def test_por_categoria_media_com_zeros_e_mediana_sem_preenchimento(client, session):
    """A média usa o denominador com meses de transferências; a mediana não.

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
      no denominador sem entrar no numerador (DEVIDA-TECNICA: D5).

      Casa.totais é construído por LINHA da query (o ciclo de `resultados`),
      que agrupa por (ano, mes, categoria, subcategoria) no `group_by`: o mês
      03 dá duas linhas (Renda -100 e "Sem subcategoria" -30), não a soma
      mensal -130.
      totais = [-100, -30, -40, -30].

      A mediana da categoria é calculada sobre estes totais por (mês,
      subcategoria); se fosse mensal seria [-130, -40, -30] -> mediana -40,0
      (DEVIDA-TECNICA: D23 — decisão pendente).

      Casa:
        media   = round((-100 - 30 - 40 - 30) / 4, 2) = round(-200/4, 2)
                = -50,0. Com a D5 corrigida (meses_distintos = 3), seria
                round(-200/3, 2) = -66.67.
        mediana = median([-100, -30, -40, -30]) = median([-100, -40, -30, -30])
                = (-40,0 + -30,0) / 2 = -35,0
      Renda: totais [-100, -40]; os 2 meses sem Renda contam como zero só
        pelo denominador (meses_distintos = 4)
        media   = round((-100 - 40) / 4, 2) = round(-140/4, 2) = -35,0
        mediana = (-100,0 + -40,0) / 2 = -70,0
      Sem subcategoria: totais [-30, -30], idem
        media   = round((-30 - 30) / 4, 2) = round(-60/4, 2) = -15,0
        mediana = (-30,0 + -30,0) / 2 = -30,0

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
    assert {s["subcategoria_nome"]: (s["mediana"], s["media"])
            for s in casa_r["subcategorias"]} == {
        "Renda": (-70.0, -35.0),
        "Sem subcategoria": (-30.0, -15.0),
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
    assert {s["subcategoria_nome"]: (s["mediana"], s["media"])
            for s in casa_r["subcategorias"]} == {
        "Renda": (-70.0, -35.0),
        "Sem subcategoria": (-30.0, -15.0),
    }
    assert session.query(Transacao).count() == 7


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
    assert por_nome["Casa"]["total"] == -130.0
    assert {s["subcategoria_nome"]: s["total"] for s in por_nome["Casa"]["subcategorias"]} == {
        "Renda": -100.0,
        "Sem subcategoria": -30.0,
    }
    assert por_nome["Receita"]["categoria_id"] == receita.id
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

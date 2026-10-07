"""Testes de API de `GET /api/estatisticas/detalhe-mensal` (D9).

O que fica fixado
-----------------
A D9 é a falta de validação dos parâmetros `ano` e `mes` de
`detalhe_mensal` (`backend/routers/estatisticas.py:235`). A função constrói
`date(ano, mes, 1)` na linha 236 e `date(ano, mes, calendar.monthrange(ano,
mes)[1])` na linha 237 sem limites, e o `date()` levanta `ValueError` tanto
para o mês fora de 1..12 como para o ano fora de 1..9999 — nunca o
`calendar` da linha 237 chega a ser avaliado:

* `ano=2024, mes=13` → `ValueError: month must be in 1..12, not 13`;
* `ano=2024, mes=0`  → `ValueError: month must be in 1..12, not 0`;
* `ano=0, mes=6`     → `ValueError: year must be in 1..9999, not 0`;
* `ano=2024, mes=12` → válido, devolve 200 (confirmado com BD vazia antes de
  escrever o teste).

A correcção alinha com o resto do projecto: `backend/routers/transacoes.py:21`
já usa `Query(None, ge=1, le=12)` para o mês, e a linha 22 usa `Query(None,
ge=2000)` para o ano. Na rota passa a ser `ano: int = Query(ge=2000, le=9999)`
e `mes: int = Query(ge=1, le=12)` — `Query` sem `default` mantém os dois
parâmetros **obrigatórios**, pelo que pedir sem `?ano=` continua a dar 422. O
`le=9999` é o teto do `date()` (ano máximo suportado) e o `ge=2000` alinha com
`transacoes.py:22`.

Nos três primeiros testes o `TestClient` do `conftest.py` tem
`raise_server_exceptions=True`, por isso a excepção original (`ValueError`) é
re-levanada no `client.get(...)` e rebenta no corpo do teste: a corrida
vermelha mostra as três como **FAILED** com `ValueError` no rastreio (não são
falhas de asserção, e não são `ERROR` do pytest, que reserva esse rótulo para
excepções em fixtures) — em produção, sem a correcção, o FastAPI devolveria
500.

Rota real: `GET /api/estatisticas/detalhe-mensal?ano=&mes=` (prefixo `api` do
`main.py` + prefixo `/estatisticas` de `estatisticas.py:10`).

Valores esperados
-----------------
Escritos à mão, como constantes: 422 para os três valores inválidos e 200
para o válido, com o corpo `[]` (a base de dados de teste está vazia, e
`_query_transacoes_mes` devolve uma lista vazia de linhas). Nenhum teste
assenta na data de hoje nem toca na base de dados real.
"""


def test_detalhe_mensal_mes_13_da_422(client):
    """`mes=13` é rejeitado pelo `Query(ge=1, le=12)`, com 422.

    Antes da correcção o `date(2024, 13, 1)` da linha 236 levantava
    `ValueError` e o `TestClient` re-levantava a excepção em vez de responder;
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
    `ValueError: year must be in 1..9999` — é o valor que Pedro mediu na
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

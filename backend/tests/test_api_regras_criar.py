"""Testes de API de `POST /api/regras/` — validação da `palavra_chave` (D21).

O que fica fixado
-----------------
A correcção da D21 fica **só no schema da entrada**: `RegraCreate.palavra_chave`
(`backend/schemas.py`, linha 62) passa a ser `Annotated[str,
StringConstraints(strip_whitespace=True, min_length=1)]`. Ou seja:

* `""` é rejeitado com 422;
* `"   "` é rejeitado com 422 (o `strip_whitespace` ocorre antes do
  `min_length`);
* `"  PINGO  "` é aceite e a palavra-chave fica guardada **sem** os espaços;
* uma palavra-chave válida sem espaços não muda (é o controlo).

`RegraBase` e `Regra` ficam como estão: `RegraBase.palavra_chave: str` (linha
57) sem restrições. A intenção é que uma regra **antiga**, escrita na base de
dados antes da correcção e com palavra-chave vazia, continue a poder ser lida
pela listagem — por isso o último teste semeia essa regra directamente na
sessão e confirma que `GET /api/regras/` continua a dar 200.

Não há rota de actualização: `backend/routers/regras.py` só tem `GET /`, `POST
/`, `DELETE /{id}`, `pre-visualizar` e `aplicar-em-massa`, por isso não há
teste de PUT. Os campos obrigatórios de `RegraCreate`, lidos do schema, são só
a `palavra_chave`: `categoria_id` e `subcategoria_id` são `Optional` com
`None` por omissão, e os payloads dos testes trazem apenas a palavra-chave
(assim o backfill das linhas 50-67 de `routers/regras.py` é saltado).

A rota real é `POST /api/regras/` (prefixo `api` do `main.py` + prefixo
`/regras` de `routers/regras.py:16`). Sem `status_code` na rota, o FastAPI
responde 200 ao caminho feliz, e o corpo é
`{"regra": {...}, "transacoes_atualizadas": 0}`.

Valores esperados
-----------------
Escritos à mão, como constantes: 422 para as duas entradas vazias, 200 para
os dois caminhos felizes, e a string exacta `"PINGO"` para o que fica
devolvido e gravado. Nenhum teste assenta na data de hoje nem toca na base de
dados real.
"""

from database import RegraCategorizacao


def test_palavra_chave_vazia_rejeitada(client):
    """`""` já não cria uma regra: o schema devolve 422.

    Antes da correcção da D21 o `POST` aceitava `""` e criava a regra, com
    200. O Pydantic rejeita a entrada com `string_too_short` antes de a rota
    ser chamada.

    Não pede `session`: com o payload inválido nada é lido nem escrito na
    base de dados, e semeá-la só esconderia que a validação acontece antes
    de tudo.
    """
    r = client.post("/api/regras/", json={"palavra_chave": ""})

    assert r.status_code == 422


def test_palavra_chave_somente_com_espacos_rejeitada(client):
    """`"   "` também: o `strip_whitespace` corre antes do `min_length`.

    O `StringConstraints(strip_whitespace=True, min_length=1)` corta os
    espaços e fica com uma string vazia, que falha o `min_length=1`. Antes da
    correcção o `"   "` era gravado tal e qual com 200.

    Não pede `session`, pela mesma razão do teste anterior.
    """
    r = client.post("/api/regras/", json={"palavra_chave": "   "})

    assert r.status_code == 422


def test_palavra_chave_com_espacos_a_volta_e_guardada_sem_eles(client, session):
    """`"  PINGO  "` é aceite e fica gravado `"PINGO"`, sem os espaços.

    A rota (`routers/regras.py:35`, 40-43) grava o valor tal como vem do
    schema, e o schema já vem desbastado. Antes da correcção o valor gravado
    era `"  PINGO  "`, com 200; é essa a parte que este teste apanha.

    Valores esperados, à mão:
      o schema devolve   "PINGO"   (strict do `strip_whitespace`)
      a resposta traz    "PINGO"   (o `jsonable_encoder` do objeto ORM)
      a sessão confirma   "PINGO"  guardado tal e qual
    """
    r = client.post("/api/regras/", json={"palavra_chave": "  PINGO  "})

    assert r.status_code == 200
    assert r.json()["regra"]["palavra_chave"] == "PINGO"

    regra = session.query(RegraCategorizacao).one()
    assert regra.palavra_chave == "PINGO"


def test_palavra_chave_valida_e_guardada(client, session):
    """O controlo: uma palavra-chave sem espaços não é alterada.

    Cálculo à mão: `"PINGO"` in `"  PINGO  "`... não, o inverso — o schema
    recebe já `"PINGO"`, o `strip` não tem nada que cortar, e fica `"PINGO"`.
    É o caso que já passava antes da correcção; serve de controlo para os
    três anteriores não falharem por uma razão alheia à validação (por
    exemplo um 500 ao serializar a resposta).
    """
    r = client.post("/api/regras/", json={"palavra_chave": "PINGO"})

    assert r.status_code == 200
    assert r.json()["regra"]["palavra_chave"] == "PINGO"

    regra = session.query(RegraCategorizacao).one()
    assert regra.palavra_chave == "PINGO"


def test_listagem_continua_a_ler_regra_antiga_com_palavra_chave_vazia(client, session):
    """Guarda de regressão: uma regra antiga com `""` não parte a listagem.

    A restrição da D21 vive **só** em `RegraCreate` — `RegraBase` e `Regra`
    ficam sem ela de propósito. Se um dia a restrição for parar a esses
    schemas, uma regra gravada antes da correcção (palavra-chave vazia na
    base de dados) poderia partir uma validação de resposta. Este teste
    semeia essa regra directamente na sessão e confirma que `GET /api/regras/`
    continua a responder 200 com ela na lista.

    Nota: hoje `listar_regras` não declara `response_model=Regra`
    (`routers/regras.py:18`), pelo que a listagem não é validada contra o
    schema — este teste não falha antes da correcção. É uma guarda de
    regressão para o futuro, não a prova do defeito.
    """
    session.add(RegraCategorizacao(palavra_chave=""))
    session.commit()

    r = client.get("/api/regras/")

    assert r.status_code == 200
    assert [g["palavra_chave"] for g in r.json()] == [""]

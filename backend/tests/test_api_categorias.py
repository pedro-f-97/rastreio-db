"""Testes da API de categorias (`/api/categorias`).

Cobre os oito endpoints de `backend/routers/categorias.py`:

* `GET /` (`listar_categorias`) — lista as categorias com as subcategorias
  aninhadas;
* `GET /{id}/subcategorias` (`listar_subcategorias`);
* `POST /` (`criar_categoria`) e `PUT /{id}` (`renomear_categoria`) — criação e
  renomeação;
* `POST /{id}/subcategorias` (`criar_subcategoria`) e
  `PUT /{id}/subcategorias/{sub_id}` (`renomear_subcategoria`);
* `DELETE /{id}` (`apagar_categoria`) e `DELETE /{id}/subcategorias/{sub_id}`
  (`apagar_subcategoria`).

Os valores esperados são calculados à mão e escritos como constantes, com o
cálculo exposto no docstring de cada teste. Nenhum teste toca na base de dados
real (ver `conftest.py`).

A fixture `client` e a fixture `session` partilham a mesma sessão SQLAlchemy;
o estado final da BD lê-se depois de `session.expire_all()`. Nenhum pedido
chega a rebentar com `IntegrityError`: o nome duplicado e o apagar de uma
categoria com transações são pré-checados e respondem **409**.
"""

from datetime import date

from database import (
    Categoria,
    ClasseDespesa,
    RegraCategorizacao,
    Subcategoria,
    TipoCategoria,
    Transacao,
)

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _semear(session):
    """Semeia três categorias, duas subcategorias e três transacções.

    Estrutura, por criação (e por isso por `id`):
      categoria 1 Casa (despesa)   -> subcategoria 1 Alimentação (trata False)
      categoria 2 Receita (receita) -> subcategoria 2 Salário (trata True)
      categoria 3 Saúde (despesa)  -> sem subcategorias
      transação 1: Casa/Alimentação
      transação 2: Saúde, sem subcategoria  (transacção "directa")
      transação 3: sem categoria nem subcategoria

    `Saúde` existe para o cenário de apagar uma categoria que só tem
    transacções directas; `Alimentação` existe para o cenário de apagar uma
    subcategoria com transacções. Devolve tudo num dicionário.
    """
    cat_casa = Categoria(nome="Casa", tipo=TipoCategoria.despesa)
    cat_receita = Categoria(nome="Receita", tipo=TipoCategoria.receita)
    cat_saude = Categoria(nome="Saúde", tipo=TipoCategoria.despesa)
    session.add_all([cat_casa, cat_receita, cat_saude])
    session.commit()
    session.refresh(cat_casa)
    session.refresh(cat_receita)
    session.refresh(cat_saude)

    sub_alim = Subcategoria(nome="Alimentação", categoria_id=cat_casa.id, trata_patrimonio=False)
    sub_salario = Subcategoria(nome="Salário", categoria_id=cat_receita.id, trata_patrimonio=True)
    session.add_all([sub_alim, sub_salario])
    session.commit()
    session.refresh(sub_alim)
    session.refresh(sub_salario)

    t1 = Transacao(
        data=date(2025, 1, 1),
        descricao="Pingo Doce",
        valor=-10.0,
        categoria_id=cat_casa.id,
        subcategoria_id=sub_alim.id,
    )
    t2 = Transacao(
        data=date(2025, 1, 2), descricao="Consulta", valor=-20.0, categoria_id=cat_saude.id
    )
    t3 = Transacao(data=date(2025, 1, 3), descricao="Sopa", valor=-5.0)
    session.add_all([t1, t2, t3])
    session.commit()
    for t in (t1, t2, t3):
        session.refresh(t)

    return {
        "cat_casa": cat_casa,
        "cat_receita": cat_receita,
        "cat_saude": cat_saude,
        "sub_alim": sub_alim,
        "sub_salario": sub_salario,
        "t1": t1,
        "t2": t2,
        "t3": t3,
    }


# ---------------------------------------------------------------------------
# GET /api/categorias/ e GET /api/categorias/{id}/subcategorias
# ---------------------------------------------------------------------------


def test_listar_categorias_devolve_subcategorias(client, session):
    """`GET /` devolve cada categoria com as subcategorias aninhadas.

    Cálculo à mão (o `return` de `listar_categorias` monta o dicionário à mão,
    `cat.tipo.value` é a string do enum):
      Casa    -> despesa, subcategorias [Alimentação (trata_patrimonio False)]
      Receita -> receita, subcategorias [Salário (trata_patrimonio True)]
      Saúde   -> despesa, subcategorias []

    A query `db.query(Categoria).all()` de `listar_categorias` não tem
    `order_by`, por isso o teste indexa por `id` e não fixa a ordem (que o
    SQLite não garante).

    Estado final da BD: 3 categorias, 2 subcategorias, 3 transacções.
    """
    d = _semear(session)

    r = client.get("/api/categorias/")

    assert r.status_code == 200
    por_id = {c["id"]: c for c in r.json()}
    assert por_id == {
        d["cat_casa"].id: {
            "id": d["cat_casa"].id,
            "nome": "Casa",
            "tipo": "despesa",
            "subcategorias": [
                {
                    "id": d["sub_alim"].id,
                    "nome": "Alimentação",
                    "trata_patrimonio": False,
                    "classe_despesa": None,
                }
            ],
        },
        d["cat_receita"].id: {
            "id": d["cat_receita"].id,
            "nome": "Receita",
            "tipo": "receita",
            "subcategorias": [
                {
                    "id": d["sub_salario"].id,
                    "nome": "Salário",
                    "trata_patrimonio": True,
                    "classe_despesa": None,
                }
            ],
        },
        d["cat_saude"].id: {
            "id": d["cat_saude"].id,
            "nome": "Saúde",
            "tipo": "despesa",
            "subcategorias": [],
        },
    }
    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2
    assert session.query(Transacao).count() == 3


def test_listar_subcategorias_de_categoria_e_404(client, session):
    """`GET /{id}/subcategorias` devolve a lista ORM; id inexistente dá 404.

    Cálculo à mão (o corpo de `listar_subcategorias`):
      categoria Casa    -> [Alimentação], serializada como
        {trata_patrimonio: False, nome: "Alimentação", id, categoria_id,
         classe_despesa: None}
      categoria Receita -> [Salário], com trata_patrimonio True
      categoria 9999    -> a `first()` devolve None -> 404
        {"detail": "Categoria não encontrada"}

    Estado final da BD: 3 categorias, 2 subcategorias, 3 transacções.
    """
    d = _semear(session)

    r_casa = client.get(f"/api/categorias/{d['cat_casa'].id}/subcategorias")
    assert r_casa.status_code == 200
    assert r_casa.json() == [
        {
            "trata_patrimonio": False,
            "nome": "Alimentação",
            "id": d["sub_alim"].id,
            "categoria_id": d["cat_casa"].id,
            "classe_despesa": None,
        }
    ]

    r_receita = client.get(f"/api/categorias/{d['cat_receita'].id}/subcategorias")
    assert r_receita.status_code == 200
    assert r_receita.json() == [
        {
            "trata_patrimonio": True,
            "nome": "Salário",
            "id": d["sub_salario"].id,
            "categoria_id": d["cat_receita"].id,
            "classe_despesa": None,
        }
    ]

    r_404 = client.get("/api/categorias/9999/subcategorias")
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Categoria não encontrada"}
    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2


# ---------------------------------------------------------------------------
# POST e PUT de categorias — nome duplicado (409 antes de escrever)
# ---------------------------------------------------------------------------


def test_criar_categoria_e_nome_duplicado_da_409(client, session):
    """Criar uma categoria funciona; um nome repetido é recusado com 409.

    O POST pré-checa `Categoria.nome` antes de
    escrever (a pré-checagem de `criar_categoria`), pelo que um nome repetido
    já não chega a `commit()` — em produção deixou de ser um 500 por
    `IntegrityError`.

    Cálculo à mão:
      POST {"nome": "Lazer", "tipo": "despesa"} -> cria, grava e refresca; o
        `id` é 4 (três já existem) e a resposta ecoa {nome, tipo, id} — sem
        `subcategorias`
      POST com o nome "Casa" (já existente): a pré-checagem encontra a linha e
        responde 409 {"detail": "Já existe uma categoria com este nome."} — a
        mesma forma de `criar_conta` (contas) e do POST de tipos de ativo

    Estado final da BD: a tentativa rejeitada não escreve nada — ficam 4
    categorias (as 3 da semente + "Lazer"), e "Casa" mantém o tipo `despesa`.
    """
    _semear(session)

    r = client.post("/api/categorias/", json={"nome": "Lazer", "tipo": "despesa"})

    assert r.status_code == 200
    assert r.json() == {"nome": "Lazer", "tipo": "despesa", "id": 4}
    assert session.query(Categoria).count() == 4

    r_dup = client.post("/api/categorias/", json={"nome": "Casa", "tipo": "despesa"})

    assert r_dup.status_code == 409
    assert r_dup.json() == {"detail": "Já existe uma categoria com este nome."}

    session.expire_all()
    assert session.query(Categoria).count() == 4
    casa = session.query(Categoria).filter_by(nome="Casa").one()
    assert casa.tipo is TipoCategoria.despesa


def test_renomear_categoria_duplicado_da_409_e_404(client, session):
    """Renomear funciona; renomear para um nome existente dá 409; id errado 404.

    O PUT pré-checa o nome contra as **outras**
    categorias (`Categoria.id != categoria_id` na pré-checagem de
    `renomear_categoria`), pelo que a colisão é recusada antes
    de escrever — em produção deixou de ser um 500 por `IntegrityError`.

    Cálculo à mão:
      PUT {"nome": "Lar", "tipo": "receita"} em Casa -> escreve nome e tipo,
        grava e devolve {nome, tipo, id}
      segundo PUT em Casa com o nome "Receita" (já existente noutra linha) ->
        409 {"detail": "Já existe uma categoria com este nome."}, sem escrita
      PUT em 9999 -> a `first()` devolve None -> 404
        {"detail": "Categoria não encontrada"}

    Estado final da BD: a tentativa rejeitada não mexe em nada, por isso Casa
    fica "Lar"/receita e contam-se 3 categorias.
    """
    d = _semear(session)

    r = client.put(f"/api/categorias/{d['cat_casa'].id}", json={"nome": "Lar", "tipo": "receita"})
    assert r.status_code == 200
    assert r.json() == {
        "nome": "Lar",
        "tipo": "receita",
        "id": d["cat_casa"].id,
    }

    r_dup = client.put(
        f"/api/categorias/{d['cat_casa'].id}", json={"nome": "Receita", "tipo": "despesa"}
    )

    assert r_dup.status_code == 409
    assert r_dup.json() == {"detail": "Já existe uma categoria com este nome."}

    session.expire_all()
    casa = session.get(Categoria, d["cat_casa"].id)
    assert casa.nome == "Lar"
    assert casa.tipo is TipoCategoria.receita
    assert session.query(Categoria).count() == 3

    r_404 = client.put("/api/categorias/9999", json={"nome": "X", "tipo": "despesa"})
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Categoria não encontrada"}


def test_renomear_categoria_mantendo_o_proprio_nome_e_200(client, session):
    """Guardar uma categoria sem mudar o nome não é duplicado: 200.

    A pré-checagem do PUT exclui o próprio
    `id`, por isso o nome de uma categoria continua a poder ser re-submetido
    tal e qual.

    Cálculo à mão:
      PUT em Casa {"nome": "Casa", "tipo": "despesa"} -> a query não encontra
        OUTRA linha com esse nome -> escreve os mesmos valores de antes e
        responde 200 {"nome": "Casa", "tipo": "despesa", "id": 1}

    Estado final da BD: nada muda — 3 categorias, 2 subcategorias e 3
    transacções.
    """
    d = _semear(session)

    r = client.put(f"/api/categorias/{d['cat_casa'].id}", json={"nome": "Casa", "tipo": "despesa"})

    assert r.status_code == 200
    assert r.json() == {
        "nome": "Casa",
        "tipo": "despesa",
        "id": d["cat_casa"].id,
    }

    session.expire_all()
    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2
    assert session.query(Transacao).count() == 3


# ---------------------------------------------------------------------------
# POST e PUT de subcategorias — `trata_patrimonio` opcional
# ---------------------------------------------------------------------------


def test_criar_subcategoria_default_trata_e_404(client, session):
    """`trata_patrimonio` omitido grava `False` (o `... or False` de
    `criar_subcategoria`).

    Cálculo à mão:
      POST {"nome": "Casa de banho"} em Casa -> `None or False` = False,
        resposta {trata_patrimonio: False, nome, id: 3, categoria_id: 1,
        classe_despesa: None}
        (as ids de subcategoria seguem a criação: Alimentação=1, Salário=2)
      POST {"nome": "Prémio", "trata_patrimonio": True} em Receita ->
        `True or False` = True, id 4, categoria_id 2
      POST em 9999 -> 404 {"detail": "Categoria não encontrada"}

    Estado final da BD: 4 subcategorias (2 da semente + 2 criadas).
    """
    d = _semear(session)

    r = client.post(
        f"/api/categorias/{d['cat_casa'].id}/subcategorias", json={"nome": "Casa de banho"}
    )

    assert r.status_code == 200
    assert r.json() == {
        "trata_patrimonio": False,
        "nome": "Casa de banho",
        "id": 3,
        "categoria_id": d["cat_casa"].id,
        "classe_despesa": None,
    }

    r2 = client.post(
        f"/api/categorias/{d['cat_receita'].id}/subcategorias",
        json={"nome": "Prémio", "trata_patrimonio": True},
    )

    assert r2.status_code == 200
    assert r2.json() == {
        "trata_patrimonio": True,
        "nome": "Prémio",
        "id": 4,
        "categoria_id": d["cat_receita"].id,
        "classe_despesa": None,
    }

    r_404 = client.post("/api/categorias/9999/subcategorias", json={"nome": "X"})
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Categoria não encontrada"}
    assert session.query(Subcategoria).count() == 4


def test_renomear_subcategoria_mantem_trata_e_404(client, session):
    """Omitir `trata_patrimonio` no PUT não o apaga; URL com categoria errada 404.

    Cálculo à mão:
      PUT {"nome": "Comida"} em Casa/Alimentação: o esquema
        `SubcategoriaCreate` traz `trata_patrimonio` a None, o `if
        subcategoria.trata_patrimonio is not None:` de `renomear_subcategoria`
        é falso e a atribuição não corre, por isso Alimentação mantém
        `trata_patrimonio = False`
      PUT {"nome": "Ordenado"} em Receita/Salário: mantém `True`
      PUT no URL Receita/Alimentação: a query de `renomear_subcategoria` exige
        `categoria_id == categoria_id do URL`, não encontra e responde 404
        {"detail": "Subcategoria não encontrada"}

    Estado final da BD: Alimentação -> "Comida"/False, Salário ->
    "Ordenado"/True, 2 subcategorias.
    """
    d = _semear(session)

    r = client.put(
        f"/api/categorias/{d['cat_casa'].id}/subcategorias/{d['sub_alim'].id}",
        json={"nome": "Comida"},
    )
    assert r.status_code == 200
    assert r.json() == {
        "trata_patrimonio": False,
        "nome": "Comida",
        "id": d["sub_alim"].id,
        "categoria_id": d["cat_casa"].id,
        "classe_despesa": None,
    }

    r2 = client.put(
        f"/api/categorias/{d['cat_receita'].id}/subcategorias/{d['sub_salario'].id}",
        json={"nome": "Ordenado"},
    )
    assert r2.status_code == 200
    assert r2.json() == {
        "trata_patrimonio": True,
        "nome": "Ordenado",
        "id": d["sub_salario"].id,
        "categoria_id": d["cat_receita"].id,
        "classe_despesa": None,
    }

    r_404 = client.put(
        f"/api/categorias/{d['cat_receita'].id}/subcategorias/{d['sub_alim'].id}",
        json={"nome": "Comida"},
    )
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Subcategoria não encontrada"}
    assert session.query(Subcategoria).count() == 2


# ---------------------------------------------------------------------------
# DELETE — o efeito em cascata
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Nomes vazios ou repetidos
# ---------------------------------------------------------------------------

DUPLICADA = "Já existe uma subcategoria com este nome nesta categoria."


def test_nome_so_com_espacos_e_recusado_e_os_espacos_a_volta_saem(client, session):
    """Um nome só de espaços dá 400; com espaços à volta, guarda-se sem eles.

    Cálculo à mão: "   " sem espaços fica "" -> 400 «O nome não pode ficar
    vazio.», nas categorias e nas subcategorias, a criar e a renomear.
    "  Lazer  " fica "Lazer".
    """
    d = _semear(session)
    vazio = {"detail": "O nome não pode ficar vazio."}
    casa, alim = d["cat_casa"].id, d["sub_alim"].id

    pedidos = [
        client.post("/api/categorias/", json={"nome": "   "}),
        client.put(f"/api/categorias/{casa}", json={"nome": "  ", "tipo": "despesa"}),
        client.post(f"/api/categorias/{casa}/subcategorias", json={"nome": " "}),
        client.put(f"/api/categorias/{casa}/subcategorias/{alim}", json={"nome": "  "}),
    ]
    assert [(r.status_code, r.json()) for r in pedidos] == [(400, vazio)] * 4

    r = client.post("/api/categorias/", json={"nome": "  Lazer  "})
    assert r.status_code == 200
    assert r.json()["nome"] == "Lazer"


def test_categoria_com_o_mesmo_nome_sem_acentos_nem_maiusculas_e_repetida(client, session):
    """«saude» e «SAÚDE» são o mesmo nome que «Saúde»: 409 a criar e a renomear.

    Cálculo à mão: sem acentos e em minúsculas, "Saúde", "saude" e "SAÚDE"
    dão todos "saude". Renomear a própria Saúde para "saude" não é repetido
    (a própria fica de fora) -> 200, e o nome passa a "saude".
    """
    d = _semear(session)
    repetida = {"detail": "Já existe uma categoria com este nome."}

    r_criar = client.post("/api/categorias/", json={"nome": "saude"})
    r_renomear = client.put(
        f"/api/categorias/{d['cat_casa'].id}", json={"nome": "SAÚDE", "tipo": "despesa"}
    )
    assert (r_criar.status_code, r_criar.json()) == (409, repetida)
    assert (r_renomear.status_code, r_renomear.json()) == (409, repetida)

    r_propria = client.put(
        f"/api/categorias/{d['cat_saude'].id}", json={"nome": "saude", "tipo": "despesa"}
    )
    assert r_propria.status_code == 200
    assert r_propria.json()["nome"] == "saude"
    assert session.query(Categoria).count() == 3


def test_subcategoria_repetida_na_mesma_categoria_e_recusada(client, session):
    """Na mesma categoria, «salario» e «SALÁRIO» repetem «Salário»: 409.

    Cálculo à mão, na Receita, que já tem Salário:
      POST "salario"                -> 409
      POST "Prémio" (novo)          -> 200
      PUT Prémio -> "SALÁRIO"       -> 409, e o Prémio fica com o nome
      PUT Salário -> "salario"      -> 200 (a própria fica de fora)
    Noutra categoria, o mesmo nome é permitido: POST "Salário" em Casa -> 200.
    """
    d = _semear(session)
    receita = d["cat_receita"].id

    r = client.post(f"/api/categorias/{receita}/subcategorias", json={"nome": "salario"})
    assert (r.status_code, r.json()) == (409, {"detail": DUPLICADA})

    premio = client.post(f"/api/categorias/{receita}/subcategorias", json={"nome": "Prémio"})
    assert premio.status_code == 200
    premio_id = premio.json()["id"]

    r = client.put(f"/api/categorias/{receita}/subcategorias/{premio_id}", json={"nome": "SALÁRIO"})
    assert (r.status_code, r.json()) == (409, {"detail": DUPLICADA})
    session.expire_all()
    assert session.get(Subcategoria, premio_id).nome == "Prémio"

    r = client.put(
        f"/api/categorias/{receita}/subcategorias/{d['sub_salario'].id}",
        json={"nome": "salario"},
    )
    assert r.status_code == 200
    assert r.json()["nome"] == "salario"

    r = client.post(f"/api/categorias/{d['cat_casa'].id}/subcategorias", json={"nome": "Salário"})
    assert r.status_code == 200


def test_apagar_categoria_com_transacoes_da_409_e_nada_muda(client, session):
    """Uma categoria com transações não se apaga: 409, e nada muda.

    Antes da correcção, com subcategorias o pedido rebentava com 500 (NOT NULL em
    `subcategorias.categoria_id`), e só com transações directas a categoria
    era apagada e as transações ficavam a apontar para o vazio.
    Decisão do utilizador: com transações, recusa.
    Cálculo à mão, semente de `_semear`:
      Casa: t1 (Casa/Alimentação)          -> 1 transação -> 409
      Saúde: t2 (directa, sem subcategoria) -> 1 transação -> 409
    Estado final: 3 categorias, 2 subcategorias, 3 transações, t2 em Saúde.
    """
    d = _semear(session)

    for cat in (d["cat_casa"], d["cat_saude"]):
        r = client.delete(f"/api/categorias/{cat.id}")
        assert r.status_code == 409
        assert r.json() == {
            "detail": "A categoria tem 1 transação; muda-as de categoria antes de a apagar.",
        }

    session.expire_all()
    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2
    assert session.query(Transacao).count() == 3
    assert session.get(Transacao, d["t2"].id).categoria_id == d["cat_saude"].id


def test_apagar_categoria_sem_transacoes_leva_subcategorias_e_regras(client, session):
    """Sem transações, a categoria vai com as suas subcategorias e regras.

    Cálculo à mão: Receita tem a subcategoria Salário e nenhuma transação.
    Regras: "salario" -> (Receita, Salário), "bonus" -> (Receita, sem sub),
    "pingo" -> (Casa, Alimentação).
      DELETE Receita -> 200; apagam-se Receita, Salário, "salario" e "bonus"
    Estado final: 2 categorias, 1 subcategoria (Alimentação), 1 regra ("pingo"),
    3 transações.
    """
    d = _semear(session)
    receita = d["cat_receita"]
    session.add_all(
        [
            RegraCategorizacao(
                palavra_chave="salario",
                categoria_id=receita.id,
                subcategoria_id=d["sub_salario"].id,
            ),
            RegraCategorizacao(palavra_chave="bonus", categoria_id=receita.id),
            RegraCategorizacao(
                palavra_chave="pingo",
                categoria_id=d["cat_casa"].id,
                subcategoria_id=d["sub_alim"].id,
            ),
        ]
    )
    session.commit()

    r = client.delete(f"/api/categorias/{receita.id}")

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    session.expire_all()
    assert {c.nome for c in session.query(Categoria).all()} == {"Casa", "Saúde"}
    assert [s.nome for s in session.query(Subcategoria).all()] == ["Alimentação"]
    assert [x.palavra_chave for x in session.query(RegraCategorizacao).all()] == ["pingo"]
    assert session.query(Transacao).count() == 3


def test_apagar_categoria_conta_transacoes_das_suas_subcategorias(client, session):
    """Uma transação que só aponta para uma subcategoria da categoria também conta.

    Cálculo à mão: uma transação órfã (sem categoria, com a subcategoria
    Salário de Receita) -> a contagem inclui `subcategoria_id in (Salário)` ->
    1 transação -> 409, e Receita e Salário ficam.
    """
    d = _semear(session)
    session.add(
        Transacao(
            data=date(2025, 1, 4),
            descricao="Órfã",
            valor=100.0,
            subcategoria_id=d["sub_salario"].id,
        )
    )
    session.commit()

    r = client.delete(f"/api/categorias/{d['cat_receita'].id}")

    assert r.status_code == 409
    session.expire_all()
    assert session.get(Subcategoria, d["sub_salario"].id) is not None


def test_apagar_subcategoria_desassocia_transacoes(client, session):
    """Apagar uma subcategoria põe as suas transacções a NULL (não as apaga).

    Cálculo à mão (o corpo de `apagar_subcategoria`): Alimentação tem a
    transacção 1 a apontar para ela. A `relationship`
    `Subcategoria.transacoes` de `database.py`, sem `cascade`, leva o
    SQLAlchemy a escrever `transacoes.subcategoria_id = NULL`
    — coluna que é `nullable=True` no modelo, por isso o `db.commit()`
    de `apagar_subcategoria` passa. A transacção 1 fica "por categorizar" mas
    mantém a categoria Casa.

    É a política decidida pelo utilizador: as transações ficam por categorizar na mesma
    categoria. As regras que apontavam para a subcategoria ficam sem ela: a
    regra "pingo" -> (Casa, Alimentação) passa a (Casa, None).

    Estado final da BD: 1 subcategoria; a transacção 1 com `categoria_id == 1`
    e `subcategoria_id is None`; a regra com `subcategoria_id is None`.
    """
    d = _semear(session)
    regra = RegraCategorizacao(
        palavra_chave="pingo", categoria_id=d["cat_casa"].id, subcategoria_id=d["sub_alim"].id
    )
    session.add(regra)
    session.commit()

    r = client.delete(f"/api/categorias/{d['cat_casa'].id}/subcategorias/{d['sub_alim'].id}")

    assert r.status_code == 200
    assert r.json() == {"ok": True}

    session.expire_all()
    assert session.query(Subcategoria).count() == 1
    assert session.get(Subcategoria, d["sub_alim"].id) is None
    t1 = session.get(Transacao, d["t1"].id)
    assert t1.categoria_id == d["cat_casa"].id
    assert t1.subcategoria_id is None
    regra = session.get(RegraCategorizacao, regra.id)
    assert (regra.categoria_id, regra.subcategoria_id) == (d["cat_casa"].id, None)


# ---------------------------------------------------------------------------
# DELETE — remoções que correm limpas e ids inexistentes
# ---------------------------------------------------------------------------


def test_apagar_categoria_vazia_e_subcategoria_sem_transacoes(client, session):
    """Categorias sem subcategorias e subcategorias sem transacções apagam-se.

    Cálculo à mão:
      DELETE numa categoria criada na hora (sem subcategorias nem transacções):
        a `first()` de `apagar_categoria` encontra-a e o `db.delete(cat)`
        apaga-a -> 200 {"ok": True}
      DELETE em Salário (Receita), que nenhuma transacção usa -> 200 {"ok": True}

    Estado final da BD: a categoria vazia desaparece (ficam as 3 da semente) e
    fica só 1 subcategoria (Alimentação).
    """
    _semear(session)

    criada = client.post("/api/categorias/", json={"nome": "Vazia", "tipo": "despesa"}).json()
    assert criada["id"] == 4
    assert session.query(Categoria).count() == 4

    r_vazia = client.delete(f"/api/categorias/{criada['id']}")
    assert r_vazia.status_code == 200
    assert r_vazia.json() == {"ok": True}
    assert session.query(Categoria).count() == 3

    d = {s.nome: s for s in session.query(Subcategoria).all()}
    receita = session.query(Categoria).filter_by(nome="Receita").one()
    r_sal = client.delete(f"/api/categorias/{receita.id}/subcategorias/{d['Salário'].id}")
    assert r_sal.status_code == 200
    assert r_sal.json() == {"ok": True}
    assert session.query(Subcategoria).count() == 1


def test_apagar_inexistentes_da_404(client, session):
    """Apagar uma categoria ou subcategoria inexistente dá 404.

    Cálculo à mão:
      DELETE /9999 -> a `first()` de `apagar_categoria` devolve None -> 404
        {"detail": "Categoria não encontrada"}
      DELETE /Casa/subcategorias/9999 -> a query de `apagar_subcategoria` não
        encontra e o `raise` responde 404
        {"detail": "Subcategoria não encontrada"}

    Estado final da BD: nada muda — 3 categorias, 2 subcategorias, 3
    transacções.
    """
    d = _semear(session)

    r_cat = client.delete("/api/categorias/9999")
    assert r_cat.status_code == 404
    assert r_cat.json() == {"detail": "Categoria não encontrada"}

    r_sub = client.delete(f"/api/categorias/{d['cat_casa'].id}/subcategorias/9999")
    assert r_sub.status_code == 404
    assert r_sub.json() == {"detail": "Subcategoria não encontrada"}

    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2
    assert session.query(Transacao).count() == 3


# ---------------------------------------------------------------------------
# Classificação das subcategorias de despesa
# ---------------------------------------------------------------------------


def _classe(session, sub_id):
    session.expire_all()
    return session.get(Subcategoria, sub_id).classe_despesa


def test_criar_subcategoria_com_classe_e_listar(client, session):
    """A classificação grava-se ao criar e lista-se como a string do enum.

    Cálculo à mão:
      POST {"nome": "Carro", "classe_despesa": "extraordinaria"} em Casa
        (despesa) -> 200, id 3 (Alimentação=1, Salário=2), na BD
        ClasseDespesa.extraordinaria
      POST {"nome": "Água"} em Casa -> sem classificação, None
      GET / -> Casa tem Alimentação (None), Carro ("extraordinaria") e Água
        (None), ordenadas por id para não depender da ordem do SQLite
    """
    d = _semear(session)
    url = f"/api/categorias/{d['cat_casa'].id}/subcategorias"

    r = client.post(url, json={"nome": "Carro", "classe_despesa": "extraordinaria"})
    r2 = client.post(url, json={"nome": "Água"})

    assert r.status_code == 200
    assert r.json()["classe_despesa"] == "extraordinaria"
    assert _classe(session, 3) == ClasseDespesa.extraordinaria
    assert r2.status_code == 200
    assert _classe(session, 4) is None

    casa = next(c for c in client.get("/api/categorias/").json() if c["nome"] == "Casa")
    assert sorted((s["id"], s["classe_despesa"]) for s in casa["subcategorias"]) == [
        (1, None),
        (3, "extraordinaria"),
        (4, None),
    ]


def test_classe_fora_das_despesas_e_recusada(client, session):
    """Só as subcategorias de categorias de despesa podem ser classificadas.

    Cálculo à mão, na Receita (receita):
      POST {"nome": "Prémio", "classe_despesa": "essencial"} -> 400, e ficam as
        2 subcategorias da semente
      PUT Salário {"nome": "Ordenado", "classe_despesa": "evitavel"} -> 400, e o
        Salário fica com o nome e sem classificação
      PUT Salário {"nome": "Ordenado", "classe_despesa": null} -> 200: tirar uma
        classificação que não existe não é classificar
      Um valor fora do enum, "luxo", em Casa -> 422
    """
    d = _semear(session)
    detalhe = {"detail": "Só as subcategorias de categorias de despesa podem ser classificadas."}
    url = f"/api/categorias/{d['cat_receita'].id}/subcategorias"

    r = client.post(url, json={"nome": "Prémio", "classe_despesa": "essencial"})
    assert r.status_code == 400
    assert r.json() == detalhe
    assert session.query(Subcategoria).count() == 2

    r = client.put(
        f"{url}/{d['sub_salario'].id}", json={"nome": "Ordenado", "classe_despesa": "evitavel"}
    )
    assert r.status_code == 400
    assert r.json() == detalhe
    session.expire_all()
    salario = session.get(Subcategoria, d["sub_salario"].id)
    assert (salario.nome, salario.classe_despesa) == ("Salário", None)

    r = client.put(
        f"{url}/{d['sub_salario'].id}", json={"nome": "Ordenado", "classe_despesa": None}
    )
    assert r.status_code == 200
    assert _classe(session, d["sub_salario"].id) is None

    r = client.post(
        f"/api/categorias/{d['cat_casa'].id}/subcategorias",
        json={"nome": "Jóias", "classe_despesa": "luxo"},
    )
    assert r.status_code == 422


def test_editar_classe_omitida_mantem_e_null_tira(client, session):
    """No PUT, a classificação omitida fica como estava; enviada a null sai.

    Cálculo à mão, em Casa/Alimentação:
      PUT {"nome": "Alimentação", "classe_despesa": "essencial"} -> essencial
      PUT {"nome": "Comida"}  -> omitida: continua essencial, nome Comida
      PUT {"nome": "Comida", "classe_despesa": "evitavel"} -> evitavel
      PUT {"nome": "Comida", "classe_despesa": null} -> None
    """
    d = _semear(session)
    url = f"/api/categorias/{d['cat_casa'].id}/subcategorias/{d['sub_alim'].id}"
    sub_id = d["sub_alim"].id

    assert (
        client.put(url, json={"nome": "Alimentação", "classe_despesa": "essencial"}).json()[
            "classe_despesa"
        ]
        == "essencial"
    )
    assert _classe(session, sub_id) == ClasseDespesa.essencial

    assert client.put(url, json={"nome": "Comida"}).status_code == 200
    assert _classe(session, sub_id) == ClasseDespesa.essencial
    assert session.get(Subcategoria, sub_id).nome == "Comida"

    client.put(url, json={"nome": "Comida", "classe_despesa": "evitavel"})
    assert _classe(session, sub_id) == ClasseDespesa.evitavel

    client.put(url, json={"nome": "Comida", "classe_despesa": None})
    assert _classe(session, sub_id) is None


def test_categoria_que_deixa_de_ser_despesa_perde_as_classificacoes(client, session):
    """Mudar o tipo de uma categoria de despesa apaga as classificações das suas
    subcategorias, e só dessas.

    Cálculo à mão:
      Casa: Alimentação essencial e Carro (novo, id 3) extraordinaria
      Saúde: Consultas (nova, id 4) essencial
      PUT Casa {"nome": "Casa", "tipo": "despesa"} -> o tipo não muda: ficam
        essencial e extraordinaria
      PUT Casa {"nome": "Casa", "tipo": "receita"} -> Alimentação e Carro None
      Consultas, na Saúde, continua essencial
      PUT Casa de volta a despesa -> continuam None (classificam-se de novo)
      Alimentação volta a essencial; PUT Casa {"tipo": "transferencia"} -> None:
        vale para qualquer tipo que não despesa, e não só para a receita
    """
    d = _semear(session)
    casa = f"/api/categorias/{d['cat_casa'].id}"
    client.put(
        f"{casa}/subcategorias/{d['sub_alim'].id}",
        json={"nome": "Alimentação", "classe_despesa": "essencial"},
    )
    client.post(f"{casa}/subcategorias", json={"nome": "Carro", "classe_despesa": "extraordinaria"})
    client.post(
        f"/api/categorias/{d['cat_saude'].id}/subcategorias",
        json={"nome": "Consultas", "classe_despesa": "essencial"},
    )

    assert client.put(casa, json={"nome": "Casa", "tipo": "despesa"}).status_code == 200
    assert _classe(session, d["sub_alim"].id) == ClasseDespesa.essencial
    assert _classe(session, 3) == ClasseDespesa.extraordinaria

    assert client.put(casa, json={"nome": "Casa", "tipo": "receita"}).status_code == 200
    assert _classe(session, d["sub_alim"].id) is None
    assert _classe(session, 3) is None
    assert _classe(session, 4) == ClasseDespesa.essencial

    client.put(casa, json={"nome": "Casa", "tipo": "despesa"})
    assert _classe(session, d["sub_alim"].id) is None
    assert _classe(session, 3) is None

    client.put(
        f"{casa}/subcategorias/{d['sub_alim'].id}",
        json={"nome": "Alimentação", "classe_despesa": "essencial"},
    )
    assert _classe(session, d["sub_alim"].id) == ClasseDespesa.essencial
    client.put(casa, json={"nome": "Casa", "tipo": "transferencia"})
    assert _classe(session, d["sub_alim"].id) is None

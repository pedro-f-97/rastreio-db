"""Testes da API de categorias (`/api/categorias`).

Cobre os oito endpoints de `backend/routers/categorias.py`:

* `GET /` (linha 8) — lista as categorias com as subcategorias aninhadas;
* `GET /{id}/subcategorias` (linha 24);
* `POST /` (linha 31) e `PUT /{id}` (linha 63) — criação e renomeação;
* `POST /{id}/subcategorias` (linha 39) e
  `PUT /{id}/subcategorias/{sub_id}` (linha 74);
* `DELETE /{id}` (linha 54) e `DELETE /{id}/subcategorias/{sub_id}` (linha 86).

Os valores esperados são calculados à mão e escritos como constantes, com o
cálculo exposto no docstring de cada teste. Nenhum teste toca na base de dados
real (ver `conftest.py`).

A fixture `client` e a fixture `session` partilham a mesma sessão SQLAlchemy.
Os pedidos que rebentam com `IntegrityError` (o `commit()` do router falha e a
excepção sobe até ao teste) deixam a sessão à espera de rollback, por isso cada
`pytest.raises` é seguido de `session.rollback()` antes de afirmar o estado da
BD. Em produção esse `IntegrityError` não é apanhado e o resultado é um **500**;
o teste fixa o comportamento real, não o desejável.

Onde o comportamento é questionável fica a etiqueta `# DEVIDA-TECNICA: Dn`,
a remeter para `docs/divida-tecnica.md`.
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from database import Categoria, Subcategoria, Transacao, TipoCategoria


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

    sub_alim = Subcategoria(nome="Alimentação", categoria_id=cat_casa.id,
                            trata_patrimonio=False)
    sub_salario = Subcategoria(nome="Salário", categoria_id=cat_receita.id,
                               trata_patrimonio=True)
    session.add_all([sub_alim, sub_salario])
    session.commit()
    session.refresh(sub_alim)
    session.refresh(sub_salario)

    t1 = Transacao(data=date(2025, 1, 1), descricao="Pingo Doce", valor=-10.0,
                   categoria_id=cat_casa.id, subcategoria_id=sub_alim.id)
    t2 = Transacao(data=date(2025, 1, 2), descricao="Consulta", valor=-20.0,
                   categoria_id=cat_saude.id)
    t3 = Transacao(data=date(2025, 1, 3), descricao="Sopa", valor=-5.0)
    session.add_all([t1, t2, t3])
    session.commit()
    for t in (t1, t2, t3):
        session.refresh(t)

    return {
        "cat_casa": cat_casa, "cat_receita": cat_receita, "cat_saude": cat_saude,
        "sub_alim": sub_alim, "sub_salario": sub_salario,
        "t1": t1, "t2": t2, "t3": t3,
    }


# ---------------------------------------------------------------------------
# GET /api/categorias/ e GET /api/categorias/{id}/subcategorias
# ---------------------------------------------------------------------------

def test_listar_categorias_devolve_subcategorias(client, session):
    """`GET /` devolve cada categoria com as subcategorias aninhadas.

    Cálculo à mão (linhas 11-22 montam o dicionário à mão, `cat.tipo.value` é
    a string do enum):
      Casa    -> despesa, subcategorias [Alimentação (trata_patrimonio False)]
      Receita -> receita, subcategorias [Salário (trata_patrimonio True)]
      Saúde   -> despesa, subcategorias []

    A query `db.query(Categoria).all()` (linha 10) não tem `order_by`, por isso
    o teste indexa por `id` e não fixa a ordem (que o SQLite não garante).

    Estado final da BD: 3 categorias, 2 subcategorias, 3 transacções.
    """
    d = _semear(session)

    r = client.get("/api/categorias/")

    assert r.status_code == 200
    por_id = {c["id"]: c for c in r.json()}
    assert por_id == {
        d["cat_casa"].id: {
            "id": d["cat_casa"].id, "nome": "Casa", "tipo": "despesa",
            "subcategorias": [{
                "id": d["sub_alim"].id, "nome": "Alimentação",
                "trata_patrimonio": False,
            }],
        },
        d["cat_receita"].id: {
            "id": d["cat_receita"].id, "nome": "Receita", "tipo": "receita",
            "subcategorias": [{
                "id": d["sub_salario"].id, "nome": "Salário",
                "trata_patrimonio": True,
            }],
        },
        d["cat_saude"].id: {
            "id": d["cat_saude"].id, "nome": "Saúde", "tipo": "despesa",
            "subcategorias": [],
        },
    }
    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2
    assert session.query(Transacao).count() == 3


def test_listar_subcategorias_de_categoria_e_404(client, session):
    """`GET /{id}/subcategorias` devolve a lista ORM; id inexistente dá 404.

    Cálculo à mão (linhas 26-29):
      categoria Casa    -> [Alimentação], serializada como
        {trata_patrimonio: False, nome: "Alimentação", id, categoria_id}
      categoria Receita -> [Salário], com trata_patrimonio True
      categoria 9999    -> a `first()` devolve None -> 404
        {"detail": "Categoria não encontrada"}

    Estado final da BD: 3 categorias, 2 subcategorias, 3 transacções.
    """
    d = _semear(session)

    r_casa = client.get(f"/api/categorias/{d['cat_casa'].id}/subcategorias")
    assert r_casa.status_code == 200
    assert r_casa.json() == [{
        "trata_patrimonio": False,
        "nome": "Alimentação",
        "id": d["sub_alim"].id,
        "categoria_id": d["cat_casa"].id,
    }]

    r_receita = client.get(f"/api/categorias/{d['cat_receita'].id}/subcategorias")
    assert r_receita.status_code == 200
    assert r_receita.json() == [{
        "trata_patrimonio": True,
        "nome": "Salário",
        "id": d["sub_salario"].id,
        "categoria_id": d["cat_receita"].id,
    }]

    r_404 = client.get("/api/categorias/9999/subcategorias")
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Categoria não encontrada"}
    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2


# ---------------------------------------------------------------------------
# POST e PUT de categorias — nome duplicado (IntegrityError, não um 4xx)
# ---------------------------------------------------------------------------

def test_criar_categoria_e_nome_duplicado_integrity(client, session):
    """Criar uma categoria funciona; um nome repetido rebenta em `commit()`.

    Cálculo à mão:
      POST {"nome": "Lazer", "tipo": "despesa"} -> a linha 33 cria, as linhas
        35-36 gravam e refrescam; o `id` é 4 (três já existem) e a resposta
        ecoa {nome, tipo, id} — sem `subcategorias`
      POST com o nome "Casa" (já existente): `categorias.nome` é `unique=True`
        (database.py:155), o `db.commit()` (linha 35) falha com
        IntegrityError: UNIQUE constraint failed: categorias.nome

    Inconsistente com contas (routers/contas.py:21 responde 409 "Já existe uma
    conta com este nome.") e regras (routers/regras.py:37 responde 400 "Já
    existe uma regra com esta palavra-chave"): aqui não há pré-checagem e o
    IntegrityError sobe, ou seja, **em produção é um 500**. Possível defeito;
    sem número de Dn (não está catalogado em docs/divida-tecnica.md).

    Estado final da BD: o rollback do teste desfaz a tentativa e ficam as 4
    categorias (as 3 da semente + "Lazer", cujo commit já tinha passado).
    """
    _semear(session)

    r = client.post("/api/categorias/", json={"nome": "Lazer", "tipo": "despesa"})

    assert r.status_code == 200
    assert r.json() == {"nome": "Lazer", "tipo": "despesa", "id": 4}
    assert session.query(Categoria).count() == 4

    with pytest.raises(IntegrityError,
                       match="UNIQUE constraint failed: categorias.nome"):
        client.post("/api/categorias/", json={"nome": "Casa", "tipo": "despesa"})
    session.rollback()

    assert session.query(Categoria).count() == 4


def test_renomear_categoria_duplicado_e_404(client, session):
    """Renomear funciona; renomear para um nome existente rebenta; id errado 404.

    Cálculo à mão:
      PUT {"nome": "Lar", "tipo": "receita"} em Casa -> a linha 68 e a 69
        escrevem nome e tipo, a 70-71 gravam; resposta {nome, tipo, id}
      segundo PUT em Casa com o nome "Receita" (já existente) -> o commit
        (linha 70) falha com UNIQUE constraint failed: categorias.nome
        (mesmo defeito do POST: em produção é um 500; sem Dn)
      PUT em 9999 -> a `first()` (linha 65) devolve None -> 404
        {"detail": "Categoria não encontrada"}

    Estado final da BD: o rollback reverte a segunda tentativa, por isso Casa
    fica "Lar"/receita; contam-se 3 categorias.
    """
    d = _semear(session)

    r = client.put(f"/api/categorias/{d['cat_casa'].id}",
                   json={"nome": "Lar", "tipo": "receita"})
    assert r.status_code == 200
    assert r.json() == {
        "nome": "Lar", "tipo": "receita", "id": d["cat_casa"].id,
    }

    with pytest.raises(IntegrityError,
                       match="UNIQUE constraint failed: categorias.nome"):
        client.put(f"/api/categorias/{d['cat_casa'].id}",
                   json={"nome": "Receita", "tipo": "despesa"})
    session.rollback()

    session.expire_all()
    casa = session.get(Categoria, d["cat_casa"].id)
    assert casa.nome == "Lar"
    assert casa.tipo is TipoCategoria.receita
    assert session.query(Categoria).count() == 3

    r_404 = client.put("/api/categorias/9999",
                       json={"nome": "X", "tipo": "despesa"})
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Categoria não encontrada"}


# ---------------------------------------------------------------------------
# POST e PUT de subcategorias — `trata_patrimonio` opcional
# ---------------------------------------------------------------------------

def test_criar_subcategoria_default_trata_e_404(client, session):
    """`trata_patrimonio` omitido grava `False` (`... or False`, linha 47).

    Cálculo à mão:
      POST {"nome": "Casa de banho"} em Casa -> `None or False` = False,
        resposta {trata_patrimonio: False, nome, id: 3, categoria_id: 1}
        (as ids de subcategoria seguem a criação: Alimentação=1, Salário=2)
      POST {"nome": "Prémio", "trata_patrimonio": True} em Receita ->
        `True or False` = True, id 4, categoria_id 2
      POST em 9999 -> 404 {"detail": "Categoria não encontrada"}

    Estado final da BD: 4 subcategorias (2 da semente + 2 criadas).
    """
    d = _semear(session)

    r = client.post(f"/api/categorias/{d['cat_casa'].id}/subcategorias",
                    json={"nome": "Casa de banho"})

    assert r.status_code == 200
    assert r.json() == {
        "trata_patrimonio": False, "nome": "Casa de banho",
        "id": 3, "categoria_id": d["cat_casa"].id,
    }

    r2 = client.post(f"/api/categorias/{d['cat_receita'].id}/subcategorias",
                     json={"nome": "Prémio", "trata_patrimonio": True})

    assert r2.status_code == 200
    assert r2.json() == {
        "trata_patrimonio": True, "nome": "Prémio",
        "id": 4, "categoria_id": d["cat_receita"].id,
    }

    r_404 = client.post("/api/categorias/9999/subcategorias",
                        json={"nome": "X"})
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Categoria não encontrada"}
    assert session.query(Subcategoria).count() == 4


def test_renomear_subcategoria_mantem_trata_e_404(client, session):
    """Omitir `trata_patrimonio` no PUT não o apaga; URL com categoria errada 404.

    Cálculo à mão:
      PUT {"nome": "Comida"} em Casa/Alimentação: o esquema
        `SubcategoriaCreate` (schemas.py:26-28) traz `trata_patrimonio` a None,
        a linha 80 é falsa e a linha 81 não corre, por isso Alimentação mantém
        `trata_patrimonio = False`
      PUT {"nome": "Ordenado"} em Receita/Salário: mantém `True`
      PUT no URL Receita/Alimentação: a query (linha 76) exige
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
        "trata_patrimonio": False, "nome": "Comida",
        "id": d["sub_alim"].id, "categoria_id": d["cat_casa"].id,
    }

    r2 = client.put(
        f"/api/categorias/{d['cat_receita'].id}/subcategorias/{d['sub_salario'].id}",
        json={"nome": "Ordenado"},
    )
    assert r2.status_code == 200
    assert r2.json() == {
        "trata_patrimonio": True, "nome": "Ordenado",
        "id": d["sub_salario"].id, "categoria_id": d["cat_receita"].id,
    }

    r_404 = client.put(
        f"/api/categorias/{d['cat_receita'].id}/subcategorias/{d['sub_alim'].id}",
        json={"nome": "Comida"},
    )
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Subcategoria não encontrada"}
    assert session.query(Subcategoria).count() == 2


# ---------------------------------------------------------------------------
# DELETE — o efeito em cascata que D1 descreve
# ---------------------------------------------------------------------------

def test_apagar_categoria_com_subcategorias_integrity(client, session):
    # DEVIDA-TECNICA: D1
    """Apagar uma categoria com subcategorias rebenta com `IntegrityError`.

    Cálculo à mão (linhas 56-60): a categoria Casa tem a subcategoria
    Alimentação. A `relationship` Cat.subcategorias (database.py:158) não tem
    `cascade`, por isso ao apagar a categoria o SQLAlchemy tenta pôr
    `subcategorias.categoria_id = NULL` para desassociar; essa coluna é
    `nullable=False` (database.py:167), e o `commit()` (linha 60) falha com
    `NOT NULL constraint failed: subcategorias.categoria_id`.

    O `IntegrityError` não é apanhado: **em produção é um 500**. Faz parte da
    D1 (não há `ON DELETE` nem `cascade` em lado nenhum).

    Estado final da BD: o rollback desfaz a tentativa; continuam 3 categorias,
    2 subcategorias e 3 transacções — Alimentação continua ligada a Casa.
    """
    d = _semear(session)

    with pytest.raises(IntegrityError,
                       match="NOT NULL constraint failed: subcategorias.categoria_id"):
        client.delete(f"/api/categorias/{d['cat_casa'].id}")
    session.rollback()

    session.expire_all()
    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2
    assert session.query(Transacao).count() == 3
    alim = session.get(Subcategoria, d["sub_alim"].id)
    assert alim.categoria_id == d["cat_casa"].id


def test_apagar_categoria_deixa_transacao_orfa(client, session):
    # DEVIDA-TECNICA: D1
    """Apagar uma categoria só com transacções directas deixa-as órfãs.

    Cálculo à mão (linhas 56-61): Saúde (id 3) não tem subcategorias, só a
    transacção 2 a apontar para ela. Como o SQLite não força as chaves
    estrangeiras (D1) e não existe `relationship` de Categoria para Transacao
    (database.py:190 só liga Transacao->Categoria), nada toca em
    `transacoes.categoria_id`: o `DELETE` passa, a categoria desaparece e a
    transacção 2 fica a apontar para o id 3, que já não existe.

    É o efeito da D1: essa transacção desaparece das estatísticas (os joins são
    `INNER`) e aparece sem nome na listagem.

    Estado final da BD: 2 categorias; a transacção 2 mantém `categoria_id == 3`
    (órfão) e `subcategoria_id is None`.
    """
    d = _semear(session)

    r = client.delete(f"/api/categorias/{d['cat_saude'].id}")

    assert r.status_code == 200
    assert r.json() == {"ok": True}

    session.expire_all()
    assert session.query(Categoria).count() == 2
    assert session.get(Categoria, d["cat_saude"].id) is None
    t2 = session.get(Transacao, d["t2"].id)
    assert t2.categoria_id == d["cat_saude"].id
    assert t2.subcategoria_id is None


def test_apagar_subcategoria_desassocia_transacoes(client, session):
    # DEVIDA-TECNICA: D1
    """Apagar uma subcategoria põe as suas transacções a NULL (não as apaga).

    Cálculo à mão (linhas 88-92): Alimentação tem a transacção 1 a apontar para
    ela. A `relationship` Subcategoria.transacoes (database.py:170), sem
    `cascade`, leva o SQLAlchemy a escrever `transacoes.subcategoria_id = NULL`
    — coluna que é `nullable=True` (database.py:185), por isso o `commit`
    (linha 92) passa. A transacção 1 fica "por categorizar" mas mantém a
    categoria Casa.

    Faz parte da D1: a associação some-se por efeito de desassociação, não por
    regra de negócio explícita.

    Estado final da BD: 1 subcategoria; a transacção 1 com `categoria_id == 1`
    e `subcategoria_id is None`.
    """
    d = _semear(session)

    r = client.delete(
        f"/api/categorias/{d['cat_casa'].id}/subcategorias/{d['sub_alim'].id}"
    )

    assert r.status_code == 200
    assert r.json() == {"ok": True}

    session.expire_all()
    assert session.query(Subcategoria).count() == 1
    assert session.get(Subcategoria, d["sub_alim"].id) is None
    t1 = session.get(Transacao, d["t1"].id)
    assert t1.categoria_id == d["cat_casa"].id
    assert t1.subcategoria_id is None


# ---------------------------------------------------------------------------
# DELETE — remoções que correm limpas e ids inexistentes
# ---------------------------------------------------------------------------

def test_apagar_categoria_vazia_e_subcategoria_sem_transacoes(client, session):
    """Categorias sem subcategorias e subcategorias sem transacções apagam-se.

    Cálculo à mão:
      DELETE numa categoria criada na hora (sem subcategorias nem transacções):
        a `first()` (linha 56) encontra-a e a linha 59 apaga-a -> 200 {"ok": True}
      DELETE em Salário (Receita), que nenhuma transacção usa -> 200 {"ok": True}

    Estado final da BD: a categoria vazia desaparece (ficam as 3 da semente) e
    fica só 1 subcategoria (Alimentação).
    """
    _semear(session)

    criada = client.post("/api/categorias/",
                         json={"nome": "Vazia", "tipo": "despesa"}).json()
    assert criada["id"] == 4
    assert session.query(Categoria).count() == 4

    r_vazia = client.delete(f"/api/categorias/{criada['id']}")
    assert r_vazia.status_code == 200
    assert r_vazia.json() == {"ok": True}
    assert session.query(Categoria).count() == 3

    d = {s.nome: s for s in session.query(Subcategoria).all()}
    receita = session.query(Categoria).filter_by(nome="Receita").one()
    r_sal = client.delete(
        f"/api/categorias/{receita.id}/subcategorias/{d['Salário'].id}"
    )
    assert r_sal.status_code == 200
    assert r_sal.json() == {"ok": True}
    assert session.query(Subcategoria).count() == 1


def test_apagar_inexistentes_da_404(client, session):
    """Apagar uma categoria ou subcategoria inexistente dá 404.

    Cálculo à mão:
      DELETE /9999 -> `first()` (linha 56) devolve None -> 404
        {"detail": "Categoria não encontrada"}
      DELETE /Casa/subcategorias/9999 -> a query (linha 88) não encontra e a
        linha 90 responde 404 {"detail": "Subcategoria não encontrada"}

    Estado final da BD: nada muda — 3 categorias, 2 subcategorias, 3
    transacções.
    """
    d = _semear(session)

    r_cat = client.delete("/api/categorias/9999")
    assert r_cat.status_code == 404
    assert r_cat.json() == {"detail": "Categoria não encontrada"}

    r_sub = client.delete(
        f"/api/categorias/{d['cat_casa'].id}/subcategorias/9999"
    )
    assert r_sub.status_code == 404
    assert r_sub.json() == {"detail": "Subcategoria não encontrada"}

    assert session.query(Categoria).count() == 3
    assert session.query(Subcategoria).count() == 2
    assert session.query(Transacao).count() == 3

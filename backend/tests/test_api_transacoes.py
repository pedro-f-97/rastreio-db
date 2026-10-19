"""Testes da API de transacções (`/api/transacoes`).

Cobre os três endpoints de `backend/routers/transacoes.py`:

* `GET /api/transacoes/por-categorizar/total` (linha 10);
* `GET /api/transacoes/` (linha 17) — listagem, filtros e paginação;
* `PUT /api/transacoes/{transacao_id}` (linha 81) — invariante
  subcategoria↔categoria e a semântica de `model_fields_set`.

Os valores esperados são calculados à mão e escritos como constantes, com o
cálculo exposto no docstring de cada teste. As datas são sempre explícitas. A
listagem ordena por `data DESC` e desempata por `id DESC` (linha 31); a semente
de `_semear` tem datas todas distintas, e o desempate é testado à parte em
`test_listar_paginacao_desempata_mesma_data_por_id_desc`. Nenhum teste assenta
na data de hoje nem toca na base de dados real (ver `conftest.py`).

A fixture `client` e a fixture `session` partilham a mesma sessão SQLAlchemy,
por isso cada pedido é seguido de `session.expire_all()` antes de ler o estado
final da base de dados: o pedido escreve na mesma sessão, a leitura tem de a
expirar para não devolver valores em cache.

Onde o comportamento é questionável fica a etiqueta `# DEVIDA-TECNICA: Dn`,
a remeter para `docs/divida-tecnica.md`.
"""

from datetime import date

from database import Categoria, Conta, Subcategoria, TipoCategoria, Transacao

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _semear(session):
    """Semeia duas categorias, duas subcategorias, duas contas e cinco transacções.

    As transacções têm datas todas distintas, de propósito (ver docstring do
    módulo). Devolve-as num dicionário, já com `id` atribuído.
    """
    cat_despesa = Categoria(nome="Casa", tipo=TipoCategoria.despesa)
    cat_receita = Categoria(nome="Receita", tipo=TipoCategoria.receita)
    session.add_all([cat_despesa, cat_receita])
    session.commit()
    session.refresh(cat_despesa)
    session.refresh(cat_receita)

    sub_despesa = Subcategoria(nome="Supermercado", categoria_id=cat_despesa.id)
    sub_receita = Subcategoria(nome="Salário", categoria_id=cat_receita.id)
    session.add_all([sub_despesa, sub_receita])
    session.commit()
    session.refresh(sub_despesa)
    session.refresh(sub_receita)

    conta_ordem = Conta(nome="Ordem", saldo_referencia=0.0,
                        data_referencia=date(2025, 1, 1))
    conta_cartao = Conta(nome="Cartão", saldo_referencia=0.0,
                         data_referencia=date(2025, 1, 1))
    session.add_all([conta_ordem, conta_cartao])
    session.commit()
    session.refresh(conta_ordem)
    session.refresh(conta_cartao)

    def _transacao(data, descricao, valor, categoria=None, subcategoria=None,
                   conta=None):
        t = Transacao(
            data=data,
            descricao=descricao,
            valor=valor,
            categoria_id=categoria.id if categoria else None,
            subcategoria_id=subcategoria.id if subcategoria else None,
            conta_id=conta.id if conta else None,
        )
        session.add(t)
        session.commit()
        session.refresh(t)
        return t

    # Ordem de criação e, por isso, de `id`: t1=1, t2=2, t3=3, t4=4, t5=5.
    t1 = _transacao(date(2025, 3, 10), "Pingo Doce", -50.0,
                    cat_despesa, sub_despesa, conta_ordem)
    t2 = _transacao(date(2025, 3, 20), "Salário", 2000.0,
                    cat_receita, None, conta_ordem)
    t3 = _transacao(date(2025, 2, 5), "Farmácia", -20.0, None, None, conta_cartao)
    t4 = _transacao(date(2025, 3, 1), "Café", -5.0,
                    cat_despesa, None, conta_ordem)
    t5 = _transacao(date(2024, 12, 31), "Jantar", -30.0,
                    cat_despesa, sub_despesa, conta_cartao)

    return {
        "cat_despesa": cat_despesa,
        "cat_receita": cat_receita,
        "sub_despesa": sub_despesa,
        "sub_receita": sub_receita,
        "conta_ordem": conta_ordem,
        "conta_cartao": conta_cartao,
        "t1": t1, "t2": t2, "t3": t3, "t4": t4, "t5": t5,
    }


def _estado(session, transacao_id):
    """Lê o estado final da transacção pela sessão partilhada.

    `expire_all()` é obrigatório: o pedido escreveu na mesma sessão que a
    fixture, e sem expirar a identidade devolveria o objecto em cache.
    """
    session.expire_all()
    t = session.get(Transacao, transacao_id)
    return {
        "categoria_id": t.categoria_id,
        "subcategoria_id": t.subcategoria_id,
        "reembolso": t.reembolso,
        "notas": t.notas,
    }


# ---------------------------------------------------------------------------
# GET /api/transacoes/por-categorizar/total
# ---------------------------------------------------------------------------

def test_total_por_categorizar_conta_categoria_ou_subcategoria_em_falta(client, session):
    """Só as transacções com categoria **ou** subcategoria em falta contam.

    Cálculo à mão, com a semente de `_semear`:
      a condição (linha 13) é `categoria_id == None OR subcategoria_id == None`
      t1: cat Casa, sub Supermercado        -> nenhum em falta   -> não conta
      t2: cat Receita, sub NULL             -> subcategoria NULL -> conta
      t3: sem categoria e sem subcategoria  -> ambos NULL        -> conta
      t4: cat Casa, sub NULL                -> subcategoria NULL -> conta
      t5: cat Casa, sub Supermercado        -> nenhum em falta   -> não conta
      total = 3

    Estado final da BD: as 5 transacções continuam (um GET não escreve).
    """
    _semear(session)

    r = client.get("/api/transacoes/por-categorizar/total")

    assert r.status_code == 200
    assert r.json() == {"total": 3}
    assert session.query(Transacao).count() == 5


# ---------------------------------------------------------------------------
# GET /api/transacoes/ — listagem, filtros e paginação
# ---------------------------------------------------------------------------

def test_listar_por_omissao_ordena_por_data_desc(client, session):
    """A listagem por omissão devolve tudo, ordenado por data descendente.

    Cálculo à mão da ordem (`order_by(Transacao.data.desc(), ...)`, linha 31):
      2025-03-20 (t2) > 2025-03-10 (t1) > 2025-03-01 (t4)
        > 2025-02-05 (t3) > 2024-12-31 (t5)
    Como todas as datas são distintas, o desempate por `id` não entra aqui
    (ver `test_listar_paginacao_desempata_mesma_data_por_id_desc`).

    Os nomes vêm das relationships (linhas 71-75): t3 não tem categoria nem
    subcategoria, e t5 usa a conta Cartão.

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    r = client.get("/api/transacoes/")
    j = r.json()

    assert r.status_code == 200
    assert j["total"] == 5
    assert j["pagina"] == 1
    assert j["tamanho"] == 50
    assert [i["id"] for i in j["items"]] == [
        d["t2"].id, d["t1"].id, d["t4"].id, d["t3"].id, d["t5"].id,
    ]
    assert [i["data"] for i in j["items"]] == [
        "2025-03-20", "2025-03-10", "2025-03-01", "2025-02-05", "2024-12-31",
    ]
    assert [i["categoria_nome"] for i in j["items"]] == [
        "Receita", "Casa", "Casa", None, "Casa",
    ]
    assert [i["subcategoria_nome"] for i in j["items"]] == [
        None, "Supermercado", None, None, "Supermercado",
    ]
    assert [i["conta_nome"] for i in j["items"]] == [
        "Ordem", "Ordem", "Ordem", "Cartão", "Cartão",
    ]
    assert session.query(Transacao).count() == 5


def test_listar_filtra_por_ano_e_mes(client, session):
    """`ano` e `mes` filtram por extract sobre a data, e compõem-se.

    Cálculo à mão:
      ano=2025: t2, t1, t4, t3 -> 4 (t5 é de 2024)
      mes=3:    t2, t1, t4     -> 3 (t3 é de Fevereiro)
      ano=2025&mes=3: t2, t1, t4 -> 3 (igual ao só mes, dentro de 2025)

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    r_ano = client.get("/api/transacoes/", params={"ano": 2025})
    assert r_ano.status_code == 200
    assert r_ano.json()["total"] == 4
    assert [i["id"] for i in r_ano.json()["items"]] == [
        d["t2"].id, d["t1"].id, d["t4"].id, d["t3"].id,
    ]

    r_mes = client.get("/api/transacoes/", params={"mes": 3})
    assert r_mes.status_code == 200
    assert r_mes.json()["total"] == 3
    assert [i["id"] for i in r_mes.json()["items"]] == [
        d["t2"].id, d["t1"].id, d["t4"].id,
    ]

    r_ambos = client.get("/api/transacoes/", params={"ano": 2025, "mes": 3})
    assert r_ambos.status_code == 200
    assert r_ambos.json()["total"] == 3
    assert [i["id"] for i in r_ambos.json()["items"]] == [
        d["t2"].id, d["t1"].id, d["t4"].id,
    ]
    assert session.query(Transacao).count() == 5


def test_listar_filtra_por_categoria_e_subcategoria(client, session):
    """Os filtros de categoria e de subcategoria são independentes.

    Cálculo à mão:
      categoria_id=Casa:    t1, t4, t5 -> 3
      subcategoria_id=Supermercado: t1, t5 -> 2

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    r_cat = client.get("/api/transacoes/",
                       params={"categoria_id": d["cat_despesa"].id})
    assert r_cat.status_code == 200
    assert r_cat.json()["total"] == 3
    assert [i["id"] for i in r_cat.json()["items"]] == [
        d["t1"].id, d["t4"].id, d["t5"].id,
    ]

    r_sub = client.get("/api/transacoes/",
                       params={"subcategoria_id": d["sub_despesa"].id})
    assert r_sub.status_code == 200
    assert r_sub.json()["total"] == 2
    assert [i["id"] for i in r_sub.json()["items"]] == [d["t1"].id, d["t5"].id]
    assert session.query(Transacao).count() == 5


def test_listar_filtra_por_conta(client, session):
    """`conta_id` filtra pela conta da transacção.

    Cálculo à mão: conta Ordem tem t2, t1 e t4 -> 3 (t3 e t5 são do Cartão).

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    r = client.get("/api/transacoes/",
                   params={"conta_id": d["conta_ordem"].id})

    assert r.status_code == 200
    assert r.json()["total"] == 3
    assert [i["id"] for i in r.json()["items"]] == [
        d["t2"].id, d["t1"].id, d["t4"].id,
    ]
    assert session.query(Transacao).count() == 5


def test_listar_filtra_por_sinal(client, session):
    """`sinal` separa por sinal do valor (`< 0` ou `> 0`).

    Cálculo à mão:
      sinal=negativo: t1 -50, t4 -5, t3 -20, t5 -30 -> 4
      sinal=positivo: t2 +2000 -> 1
      um valor 0 não é negativo nem positivo; não há nenhum na semente

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    r_neg = client.get("/api/transacoes/", params={"sinal": "negativo"})
    assert r_neg.status_code == 200
    assert r_neg.json()["total"] == 4
    assert [i["id"] for i in r_neg.json()["items"]] == [
        d["t1"].id, d["t4"].id, d["t3"].id, d["t5"].id,
    ]

    r_pos = client.get("/api/transacoes/", params={"sinal": "positivo"})
    assert r_pos.status_code == 200
    assert r_pos.json()["total"] == 1
    assert [i["id"] for i in r_pos.json()["items"]] == [d["t2"].id]
    assert session.query(Transacao).count() == 5


def test_listar_filtra_por_descricao_sem_acentos_nem_maiusculas(client, session):
    """A pesquisa por descrição ignora acentos e maiúsculas, e é texto literal.

    Era a D28: o filtro era `ilike`, que só ignora maiúsculas em ASCII.
    Decisão do utilizador: na pesquisa, os acentos também não contam.
    Cálculo à mão, contra as cinco descrições da semente:
      "far"      -> "farmacia" contém "far"           -> 1 (t3)
      "farmacia" -> sem acento, casa "Farmácia"       -> 1 (t3)
      "FARMÁCIA" -> "farmacia" depois de normalizar   -> 1 (t3)
      "CAFE"     -> casa "Café"                       -> 1 (t4)
      "%"        -> literal; nenhuma descrição tem "%" -> 0

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    for procura, esperado in [
        ("far", [d["t3"].id]),
        ("farmacia", [d["t3"].id]),
        ("FARMÁCIA", [d["t3"].id]),
        ("CAFE", [d["t4"].id]),
        ("%", []),
    ]:
        r = client.get("/api/transacoes/", params={"descricao": procura})
        assert r.status_code == 200
        assert [i["id"] for i in r.json()["items"]] == esperado, procura
        assert r.json()["total"] == len(esperado), procura
    assert session.query(Transacao).count() == 5


def test_listar_por_descricao_pagina_so_as_que_casam(client, session):
    """Com pesquisa, o `total` e as páginas contam só as transacções que casam.

    Cálculo à mão, "a" sem acentos: "pingo doce" não tem "a"; "salario",
    "farmacia", "cafe" e "jantar" têm -> 4. Por data desc: t2 (03-20),
    t4 (03-01), t3 (02-05), t5 (2024-12-31). Com `tamanho=2`, a página 2 é
    [t3, t5] e o `total` é 4.
    """
    d = _semear(session)

    r = client.get("/api/transacoes/", params={"descricao": "a", "pagina": 2, "tamanho": 2})

    assert r.status_code == 200
    assert r.json()["total"] == 4
    assert [i["id"] for i in r.json()["items"]] == [d["t3"].id, d["t5"].id]


def test_listar_por_categorizar(client, session):
    """`por_categorizar=true` repete a condição do total (categoria **ou** sub).

    Cálculo à mão:
      t1: cat e sub presentes -> fora
      t2: sub NULL             -> dentro
      t3: ambos NULL           -> dentro
      t4: sub NULL             -> dentro
      t5: cat e sub presentes -> fora
      total = 3, ordem por data desc: t2, t4, t3

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    r = client.get("/api/transacoes/", params={"por_categorizar": "true"})

    assert r.status_code == 200
    assert r.json()["total"] == 3
    assert [i["id"] for i in r.json()["items"]] == [
        d["t2"].id, d["t4"].id, d["t3"].id,
    ]
    assert session.query(Transacao).count() == 5


def test_listar_paginacao(client, session):
    """A paginação corta os itens mas o `total` continua a ser o do filtro todo.

    Cálculo à mão, com `tamanho=2` e a ordem desc de t2, t1, t4, t3, t5:
      pagina=1 -> itens [t2, t1]  (offset (1-1)*2 = 0)
      pagina=2 -> itens [t4, t3]  (offset (2-1)*2 = 2)
      pagina=3 -> itens [t5]      (offset (3-1)*2 = 4)
    O `total` é `query.count()` antes do `offset/limit` (linha 54), por isso é
    5 nas três páginas.

    As datas são distintas; o `offset` sobre transacções da mesma data está em
    `test_listar_paginacao_desempata_mesma_data_por_id_desc`.

    Estado final da BD: as 5 transacções continuam.
    """
    d = _semear(session)

    r1 = client.get("/api/transacoes/", params={"pagina": 1, "tamanho": 2})
    assert r1.status_code == 200
    assert r1.json()["total"] == 5
    assert r1.json()["pagina"] == 1
    assert r1.json()["tamanho"] == 2
    assert [i["id"] for i in r1.json()["items"]] == [d["t2"].id, d["t1"].id]

    r2 = client.get("/api/transacoes/", params={"pagina": 2, "tamanho": 2})
    assert r2.status_code == 200
    assert r2.json()["total"] == 5
    assert r2.json()["pagina"] == 2
    assert [i["id"] for i in r2.json()["items"]] == [d["t4"].id, d["t3"].id]

    r3 = client.get("/api/transacoes/", params={"pagina": 3, "tamanho": 2})
    assert r3.status_code == 200
    assert r3.json()["total"] == 5
    assert r3.json()["pagina"] == 3
    assert [i["id"] for i in r3.json()["items"]] == [d["t5"].id]
    assert session.query(Transacao).count() == 5


def test_listar_paginacao_desempata_mesma_data_por_id_desc(client, session):
    """Transacções da mesma data ficam por `id` descendente, estáveis entre páginas.

    Era a D10: sem desempate, a ordem dentro da mesma data ficava ao critério
    do SQLite e o `offset` podia repetir ou saltar linhas entre páginas.

    Semente, por ordem de criação (e de `id`): a1..a4 em 2025-03-10 e b em
    2025-03-20, criada por último para ter o `id` mais alto de todos.

    Cálculo à mão, `order_by(data DESC, id DESC)` (linha 31):
      b (03-20) > a4 > a3 > a2 > a1 (os quatro de 03-10, por id desc)
    Com `tamanho=2`:
      pagina=1 -> [b, a4]   (offset 0)
      pagina=2 -> [a3, a2]  (offset 2)
      pagina=3 -> [a1]      (offset 4)
    As três páginas juntas têm os 5 ids, cada um uma só vez.

    Estado final da BD: as 5 transacções continuam.
    """
    mesmas = []
    for n in range(1, 5):
        t = Transacao(data=date(2025, 3, 10), descricao=f"Igual {n}", valor=-1.0)
        session.add(t)
        session.commit()
        session.refresh(t)
        mesmas.append(t)
    a1, a2, a3, a4 = mesmas
    b = Transacao(data=date(2025, 3, 20), descricao="Depois", valor=-1.0)
    session.add(b)
    session.commit()
    session.refresh(b)

    paginas = []
    for pagina in (1, 2, 3):
        r = client.get("/api/transacoes/", params={"pagina": pagina, "tamanho": 2})
        assert r.status_code == 200
        assert r.json()["total"] == 5
        paginas.append([i["id"] for i in r.json()["items"]])

    assert paginas == [[b.id, a4.id], [a3.id, a2.id], [a1.id]]
    todos = [i for p in paginas for i in p]
    assert sorted(todos) == sorted([a1.id, a2.id, a3.id, a4.id, b.id])
    assert session.query(Transacao).count() == 5


# ---------------------------------------------------------------------------
# PUT /api/transacoes/{id} — notas e reembolso
# ---------------------------------------------------------------------------

def test_put_notas_omitido_null_e_vazio(client, session):
    """`notas` grava com valor, ignora `null` e limpa com a string vazia.

    Cálculo à mão:
      {"notas": "almoço"}: `dados.notas is not None` (linha 128) -> grava
      {"notas": null}:     `is not None` é falso -> nada é tocado, fica "almoço"
      {"notas": ""}:       `"" is not None` é verdadeiro -> grava a string vazia

    Facto do frontend: `TabelaTransacoes.jsx:204` lê `e.target.value`, pelo que
    esvaziar o campo envia `""`, nunca `null`. O `null` é o ramo que o endpoint
    ignora por construção.

    Estado final da BD, lido em cada passo: é o que a tabela mostra.
    """
    d = _semear(session)
    t1 = d["t1"]

    r = client.put(f"/api/transacoes/{t1.id}", json={"notas": "almoço"})
    assert r.status_code == 200
    assert r.json()["notas"] == "almoço"
    assert _estado(session, t1.id) == {
        "categoria_id": d["cat_despesa"].id,
        "subcategoria_id": d["sub_despesa"].id,
        "reembolso": False,
        "notas": "almoço",
    }

    r = client.put(f"/api/transacoes/{t1.id}", json={"notas": None})
    assert r.status_code == 200
    assert _estado(session, t1.id) == {
        "categoria_id": d["cat_despesa"].id,
        "subcategoria_id": d["sub_despesa"].id,
        "reembolso": False,
        "notas": "almoço",
    }

    r = client.put(f"/api/transacoes/{t1.id}", json={"notas": ""})
    assert r.status_code == 200
    assert _estado(session, t1.id) == {
        "categoria_id": d["cat_despesa"].id,
        "subcategoria_id": d["sub_despesa"].id,
        "reembolso": False,
        "notas": "",
    }


def test_put_reembolso_false_grava_e_omitido_mantem(client, session):
    """`reembolso` grava `False` (não é `None`) e o campo omitido não é tocado.

    Cálculo à mão:
      {"reembolso": true}:  `True is not None` (linha 125) -> grava True
      {"reembolso": false}: `False is not None` é verdadeiro -> grava False
        (a guarda é `is not None`, não um teste de verdade, por isso `False`
        passa e é mesmo escrito)
      {"notas": "x"}: só `notas` vem no payload; `reembolso` fica False

    Estado final da BD, lido em cada passo.
    """
    d = _semear(session)
    t1 = d["t1"]

    r = client.put(f"/api/transacoes/{t1.id}", json={"reembolso": True})
    assert r.status_code == 200
    assert r.json()["reembolso"] is True
    assert _estado(session, t1.id)["reembolso"] is True

    r = client.put(f"/api/transacoes/{t1.id}", json={"reembolso": False})
    assert r.status_code == 200
    assert r.json()["reembolso"] is False
    assert _estado(session, t1.id)["reembolso"] is False

    r = client.put(f"/api/transacoes/{t1.id}", json={"notas": "x"})
    assert r.status_code == 200
    assert _estado(session, t1.id)["reembolso"] is False


# ---------------------------------------------------------------------------
# PUT /api/transacoes/{id} — categoria e subcategoria
# ---------------------------------------------------------------------------

def test_put_muda_so_categoria_em_transacao_sem_subcategoria(client, session):
    """Numa transacção sem subcategoria, mudar só a categoria é aceite.

    Cenário: t4 tem categoria Casa e subcategoria NULL. Pedido
    `{"categoria_id": Receita}`.

    Cálculo à mão:
      categoria_alvo = Receita (veio no payload)
      subcategoria_alvo = t.subcategoria_id = NULL (não veio no payload)
      a invariante (linha 108) só corre `if subcategoria_alvo is not None`,
        por isso é saltada
      grava Receita, e a subcategoria continua NULL

    Estado final da BD: t4 com categoria Receita e subcategoria None.
    """
    d = _semear(session)
    t4 = d["t4"]

    r = client.put(f"/api/transacoes/{t4.id}",
                   json={"categoria_id": d["cat_receita"].id})

    assert r.status_code == 200
    assert r.json()["categoria_id"] == d["cat_receita"].id
    assert r.json()["subcategoria_id"] is None
    assert _estado(session, t4.id) == {
        "categoria_id": d["cat_receita"].id,
        "subcategoria_id": None,
        "reembolso": False,
        "notas": None,
    }


def test_put_invariante_subcategoria_de_outra_categoria_da_400(client, session):
    """A subcategoria alvo tem de pertencer à categoria alvo.

    Cenário: t1 tem Casa/Supermercado. Três pedidos incoerentes:
      {"categoria_id": Receita}:      categoria_alvo=Receita,
        subcategoria_alvo=Supermercado (herdada); Supermercado é de Casa
        -> 400, linha 114
      {"subcategoria_id": Salário}:   categoria_alvo=Casa (herdada),
        subcategoria_alvo=Salário; Salário é de Receita -> 400
      {"categoria_id": null}:         categoria_alvo=None,
        subcategoria_alvo=Supermercado; `sub.categoria_id != None` -> 400

    Nenhum dos três escreve: a validação (107-117) corre antes das
    atribuições (119-123).

    Estado final da BD: t1 continua Casa/Supermercado.
    """
    d = _semear(session)
    t1 = d["t1"]

    r = client.put(f"/api/transacoes/{t1.id}",
                   json={"categoria_id": d["cat_receita"].id})
    assert r.status_code == 400
    assert r.json() == {
        "detail": "A subcategoria não pertence à categoria selecionada."
    }

    r = client.put(f"/api/transacoes/{t1.id}",
                   json={"subcategoria_id": d["sub_receita"].id})
    assert r.status_code == 400
    assert r.json() == {
        "detail": "A subcategoria não pertence à categoria selecionada."
    }

    r = client.put(f"/api/transacoes/{t1.id}", json={"categoria_id": None})
    assert r.status_code == 400
    assert r.json() == {
        "detail": "A subcategoria não pertence à categoria selecionada."
    }

    assert _estado(session, t1.id) == {
        "categoria_id": d["cat_despesa"].id,
        "subcategoria_id": d["sub_despesa"].id,
        "reembolso": False,
        "notas": None,
    }


def test_put_par_valido_atualiza_categoria_e_subcategoria(client, session):
    """Um par categoria+subcategoria coerente é gravado nos dois campos.

    Cenário: t1 (Casa/Supermercado) -> `{"categoria_id": Receita,
    "subcategoria_id": Salário}`.

    Cálculo à mão:
      categoria_alvo = Receita, subcategoria_alvo = Salário
      Salário pertence a Receita -> a invariante passa (linha 114 falsa)
      as duas atribuições (119-123) gravam ambos os campos

    Estado final da BD: t1 com Receita/Salário.
    """
    d = _semear(session)
    t1 = d["t1"]

    r = client.put(f"/api/transacoes/{t1.id}", json={
        "categoria_id": d["cat_receita"].id,
        "subcategoria_id": d["sub_receita"].id,
    })

    assert r.status_code == 200
    assert r.json()["categoria_id"] == d["cat_receita"].id
    assert r.json()["subcategoria_id"] == d["sub_receita"].id
    assert _estado(session, t1.id) == {
        "categoria_id": d["cat_receita"].id,
        "subcategoria_id": d["sub_receita"].id,
        "reembolso": False,
        "notas": None,
    }


def test_put_limpar_subcategoria_com_null_mantem_categoria(client, session):
    """Limpar a subcategoria com `null` explícito mantém a categoria.

    Cenário: t1 (Casa/Supermercado) -> `{"subcategoria_id": null}`.

    Cálculo à mão:
      subcategoria_alvo = None -> a invariante é saltada
      `"subcategoria_id" in model_fields_set` é verdadeiro (veio explícito),
        por isso a linha 123 grava None
      categoria não veio no payload -> fica Casa

    Distingue-se de omitir `subcategoria_id`: aí a chave não está em
    `model_fields_set` e a linha 123 também não corre, deixando tudo como
    estava.

    Estado final da BD: t1 com Casa e subcategoria None.
    """
    d = _semear(session)
    t1 = d["t1"]

    r = client.put(f"/api/transacoes/{t1.id}", json={"subcategoria_id": None})

    assert r.status_code == 200
    assert r.json()["categoria_id"] == d["cat_despesa"].id
    assert r.json()["subcategoria_id"] is None
    assert _estado(session, t1.id) == {
        "categoria_id": d["cat_despesa"].id,
        "subcategoria_id": None,
        "reembolso": False,
        "notas": None,
    }


def test_put_subcategoria_inexistente_da_400(client, session):
    """Uma subcategoria que não existe dá 400, não 404 nem escrita.

    Cálculo à mão: `db.query(Subcategoria).filter(id == 9999).first()` devolve
    None, logo a linha 112 responde 400 com "Subcategoria não encontrada.".

    Estado final da BD: t1 continua Casa/Supermercado.
    """
    d = _semear(session)
    t1 = d["t1"]

    r = client.put(f"/api/transacoes/{t1.id}", json={"subcategoria_id": 9999})

    assert r.status_code == 400
    assert r.json() == {"detail": "Subcategoria não encontrada."}
    assert _estado(session, t1.id) == {
        "categoria_id": d["cat_despesa"].id,
        "subcategoria_id": d["sub_despesa"].id,
        "reembolso": False,
        "notas": None,
    }


def test_put_transacao_inexistente_da_404(client, session):
    """Actualizar uma transacção que não existe dá 404.

    Cálculo à mão: `db.query(Transacao).filter(id == 9999).first()` devolve
    None, a linha 89 entra no `if` e a 90-93 responde 404.

    Estado final da BD: as 5 transacções da semente continuam.
    """
    _semear(session)

    r = client.put("/api/transacoes/9999", json={"notas": "x"})

    assert r.status_code == 404
    assert r.json() == {"detail": "Transação não encontrada"}
    assert session.query(Transacao).count() == 5


def test_put_categoria_inexistente_da_400(client, session):
    """Uma categoria que não existe dá 400 e não é gravada (D1).

    Cálculo à mão: `db.get(Categoria, 9999)` devolve None, logo a validação de
    `atualizar_transacao` responde 400 com "Categoria não encontrada." antes de
    escrever. Sem ela, a pragma `foreign_keys` recusaria o `commit` com 500.

    Estado final da BD: t4 continua Casa e subcategoria None.
    """
    d = _semear(session)
    t4 = d["t4"]

    r = client.put(f"/api/transacoes/{t4.id}", json={"categoria_id": 9999})

    assert r.status_code == 400
    assert r.json() == {"detail": "Categoria não encontrada."}
    assert _estado(session, t4.id) == {
        "categoria_id": d["cat_despesa"].id,
        "subcategoria_id": None,
        "reembolso": False,
        "notas": None,
    }

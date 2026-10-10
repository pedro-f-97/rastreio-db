"""Testes de API do router `routers/patrimonio.py`.

Âmbito deste ficheiro
---------------------
O router estava quase todo por cobrir. O relatório de cobertura dava 127
declarações e 79 em falta em `routers/patrimonio.py`, e 85 declarações com 31
em falta em `servicos/patrimonio_serv.py`.

O que **não** se repete aqui: os ramos felizes de `GET
/api/patrimonio/ativos/{id}/resumo` e o núcleo `_resumo_valor_ativo` já estão
fixados por `test_patrimonio_fifo.py`. Deste endpoint só se cobre o 404.

Este commit cobre **ativos, movimentos e preços** de ativos (B2 a B23).
Pendentes e evolução de património ficam para o commit seguinte.

Estado final da BD
------------------
Entra-se sempre pelo endpoint real, sobre a BD in-memory da fixture `session`,
e confirma-se também o que ficou gravado na sessão. Os valores esperados são
calculados à mão e escritos como constantes.

Notas de comportamento (sem correcção)
--------------------------------------
* `DELETE /api/patrimonio/ativos/{id}` apaga à mão os movimentos e os preços do
  ativo antes de apagar o ativo (`routers/patrimonio.py:79-81`), porque o
  SQLite não aplica as chaves estrangeiras (D1).
* `POST /api/patrimonio/movimentos` faz dois `commit()` no mesmo handler
  (`routers/patrimonio.py:94` e `:107`): se a gravação do preço falhasse, o
  movimento já estaria gravado (DEVIDA-TECNICA: D12c). Não se força a falha.
* O upsert de preço só acontece em movimentos de `compra` com `preco_unitario`
  preenchido (`routers/patrimonio.py:97`).
"""

from datetime import date

from database import (
    Ativo,
    MovimentoAtivo,
    PrecoAtivo,
    TipoAtivo,
    TipoContabilizacao,
    TipoMovimento,
)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def semear_tipo(session, nome, tem_unidades):
    tipo = TipoAtivo(nome=nome, tem_unidades=tem_unidades)
    session.add(tipo)
    session.commit()
    return tipo


def semear_ativo(session, nome, tipo, simbolo=None):
    contabilizacao = (
        TipoContabilizacao.investimento
        if tipo.tem_unidades
        else TipoContabilizacao.patrimonio
    )
    ativo = Ativo(
        nome=nome,
        tipo_id=tipo.id,
        simbolo=simbolo,
        contabilizacao=contabilizacao,
    )
    session.add(ativo)
    session.commit()
    return ativo


def semear_movimento(session, ativo, tipo_movimento, data, valor_total,
                     quantidade=None, preco_unitario=None):
    movimento = MovimentoAtivo(
        ativo_id=ativo.id,
        tipo_movimento=tipo_movimento,
        data=data,
        quantidade=quantidade,
        preco_unitario=preco_unitario,
        valor_total=valor_total,
    )
    session.add(movimento)
    session.commit()
    return movimento


def semear_preco(session, ativo, data, preco):
    registo = PrecoAtivo(ativo_id=ativo.id, data=data, preco=preco)
    session.add(registo)
    session.commit()
    return registo


# ---------------------------------------------------------------------------
# B2/B3 — GET /api/patrimonio/ativos
# ---------------------------------------------------------------------------

def test_listar_ativos_sem_ativos_devolve_lista_vazia(client, session):
    """Sem ativos, a resposta e `[]` (200) e a BD fica a zero linhas."""
    r = client.get("/api/patrimonio/ativos")

    assert r.status_code == 200
    assert r.json() == []
    assert session.query(Ativo).count() == 0


def test_listar_ativos_ordena_por_tipo_e_nome(client, session):
    """A listagem vem ordenada por `(tipo_id, nome)`.

    Cálculo à mão: tipo 1 (`Acoes`) e tipo 2 (`Imovel`); ativos semeados por
    esta ordem: `Z` (tipo 2), `A` (tipo 1), `B` (tipo 1). A query
    `order_by(AtivoModel.tipo_id, AtivoModel.nome)`
    (`routers/patrimonio.py:37`) devolve `[A, B, Z]`.
    """
    tipo_acoes = semear_tipo(session, "Acoes", tem_unidades=True)
    tipo_imovel = semear_tipo(session, "Imovel", tem_unidades=False)
    semear_ativo(session, "Z", tipo_imovel)
    semear_ativo(session, "A", tipo_acoes)
    semear_ativo(session, "B", tipo_acoes)

    r = client.get("/api/patrimonio/ativos")

    assert r.status_code == 200
    assert [a["nome"] for a in r.json()] == ["A", "B", "Z"]
    assert [a["tipo_id"] for a in r.json()] == [tipo_acoes.id, tipo_acoes.id, tipo_imovel.id]


# ---------------------------------------------------------------------------
# B4/B5/B6 — POST /api/patrimonio/ativos
# ---------------------------------------------------------------------------

def test_criar_ativo_grava_e_embute_o_tipo(client, session):
    """Um ativo válido é gravado e a resposta traz o tipo embutido.

    Cálculo à mão: um `POST` -> uma linha. A rota não declara `status_code`,
    por isso a resposta é 200.

    Nota: não se testa o caso de `tipo_id` inexistente. A resposta
    `schemas.Ativo` exige `tipo: TipoAtivo` e, sem linha correspondente, o
    `None` reprova a serialização — daria 500. Possível defeito ligado à D1
    (chaves estrangeiras desligadas); fica como nota, não como teste.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)

    r = client.post(
        "/api/patrimonio/ativos",
        json={
            "nome": "Acao X",
            "tipo_id": tipo.id,
            "simbolo": "XPT",
            "contabilizacao": "investimento",
        },
    )

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["nome"] == "Acao X"
    assert corpo["simbolo"] == "XPT"
    assert corpo["tipo"]["nome"] == "Acoes"

    assert session.query(Ativo).count() == 1
    ativo = session.query(Ativo).one()
    assert ativo.nome == "Acao X"
    assert ativo.contabilizacao == TipoContabilizacao.investimento


def test_criar_ativo_com_simbolo_duplicado_da_409(client, session):
    """Símbolo já existente: 409 e nenhuma linha nova.

    Cálculo à mão: um ativo com símbolo `XPT` + um `POST` com `XPT` -> 1
    linha.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    semear_ativo(session, "Existente", tipo, simbolo="XPT")

    r = client.post(
        "/api/patrimonio/ativos",
        json={
            "nome": "Outro",
            "tipo_id": tipo.id,
            "simbolo": "XPT",
            "contabilizacao": "investimento",
        },
    )

    assert r.status_code == 409
    assert r.json()["detail"] == "Já existe um ativo com este símbolo."
    assert session.query(Ativo).count() == 1


def test_criar_dois_ativos_sem_simbolo_e_aceite(client, session):
    """Vários ativos sem símbolo coexistem (`unique` admite vários `NULL`).

    Cálculo à mão: dois `POST` sem `simbolo` -> 200 e 200, com 2 linhas na BD.
    A restrição `unique` do SQLite não colide com `NULL`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    base = {"tipo_id": tipo.id, "contabilizacao": "investimento"}

    r1 = client.post("/api/patrimonio/ativos", json={**base, "nome": "Um"})
    r2 = client.post("/api/patrimonio/ativos", json={**base, "nome": "Dois"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert session.query(Ativo).count() == 2


# ---------------------------------------------------------------------------
# B7/B8/B9 — PUT /api/patrimonio/ativos/{id}
# ---------------------------------------------------------------------------

def test_editar_ativo_muda_apenas_o_nome(client, session):
    """Editar só o nome deixa o símbolo intacto.

    Cálculo à mão: ativo `A`/`AAA`; `PUT {"nome": "B"}` -> nome `B` e símbolo
    ainda `AAA` (o router só toca nos campos não nulos,
    `routers/patrimonio.py:66-69`).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "A", tipo, simbolo="AAA")

    r = client.put(f"/api/patrimonio/ativos/{ativo.id}", json={"nome": "B"})

    assert r.status_code == 200
    assert r.json()["nome"] == "B"
    assert r.json()["simbolo"] == "AAA"
    session.refresh(ativo)
    assert ativo.nome == "B"
    assert ativo.simbolo == "AAA"


def test_editar_ativo_com_simbolo_de_outro_da_409(client, session):
    """Mudar para um símbolo já usado por outro ativo dá 409.

    Cálculo à mão: ativos `AAA` (id 1) e `BBB` (id 2); `PUT` no id 1 com
    `simbolo=BBB` -> 409, e o id 1 fica com `AAA`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    primeiro = semear_ativo(session, "Primeiro", tipo, simbolo="AAA")
    semear_ativo(session, "Segundo", tipo, simbolo="BBB")

    r = client.put(
        f"/api/patrimonio/ativos/{primeiro.id}",
        json={"simbolo": "BBB"},
    )

    assert r.status_code == 409
    assert r.json()["detail"] == "Já existe um ativo com este símbolo."
    session.refresh(primeiro)
    assert primeiro.simbolo == "AAA"


def test_editar_ativo_inexistente_da_404(client, session):
    """Editar um ativo que não existe responde 404."""
    r = client.put("/api/patrimonio/ativos/999", json={"nome": "B"})

    assert r.status_code == 404
    assert r.json()["detail"] == "Ativo não encontrado."


# ---------------------------------------------------------------------------
# B10/B11 — DELETE /api/patrimonio/ativos/{id}
# ---------------------------------------------------------------------------

def test_eliminar_ativo_apaga_movimentos_e_precos(client, session):
    """Apagar um ativo remove também os seus movimentos e preços.

    Cálculo à mão: ativo com 1 movimento e 2 preços -> depois do `DELETE`,
    0 ativos, 0 movimentos e 0 preços. A cascata é feita à mão
    (`routers/patrimonio.py:79-81`), porque o SQLite não aplica as chaves
    estrangeiras (D1).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-200.0, quantidade=10)
    semear_preco(session, ativo, date(2025, 1, 10), 20.0)
    semear_preco(session, ativo, date(2025, 2, 10), 25.0)

    r = client.delete(f"/api/patrimonio/ativos/{ativo.id}")

    assert r.status_code == 204
    assert r.content == b""
    assert session.query(Ativo).count() == 0
    assert session.query(MovimentoAtivo).count() == 0
    assert session.query(PrecoAtivo).count() == 0


def test_eliminar_ativo_inexistente_da_404(client, session):
    """Apagar um ativo que não existe responde 404."""
    r = client.delete("/api/patrimonio/ativos/999")

    assert r.status_code == 404
    assert r.json()["detail"] == "Ativo não encontrado."


# ---------------------------------------------------------------------------
# B12..B16 — POST /api/patrimonio/movimentos
# ---------------------------------------------------------------------------

def test_criar_movimento_de_compra_grava_e_cria_preco(client, session):
    """Compra com `preco_unitario`: grava o movimento e cria o preço do dia.

    Cálculo à mão: um `POST` -> 1 movimento + 1 preço `(ativo, 2025-01-10,
    20.0)`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)

    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "tipo_movimento": "compra",
            "data": "2025-01-10",
            "quantidade": 10,
            "preco_unitario": 20.0,
            "valor_total": -200.0,
        },
    )

    assert r.status_code == 200
    assert r.json()["id"] == 1
    assert session.query(MovimentoAtivo).count() == 1

    precos = session.query(PrecoAtivo).all()
    assert len(precos) == 1
    assert precos[0].ativo_id == ativo.id
    assert precos[0].data == date(2025, 1, 10)
    assert precos[0].preco == 20.0


def test_compra_no_mesmo_dia_actualiza_o_preco(client, session):
    """Uma segunda compra no mesmo ativo e dia faz upsert do preço.

    Cálculo à mão: compra a 20.0 e outra a 21.0 no mesmo dia -> 2 movimentos,
    mas **1** preço, com o valor 21.0 (`routers/patrimonio.py:98-107`).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    base = {
        "ativo_id": ativo.id,
        "tipo_movimento": "compra",
        "data": "2025-01-10",
        "quantidade": 10,
        "valor_total": -200.0,
    }
    client.post("/api/patrimonio/movimentos", json={**base, "preco_unitario": 20.0})

    r = client.post("/api/patrimonio/movimentos", json={**base, "preco_unitario": 21.0})

    assert r.status_code == 200
    assert session.query(MovimentoAtivo).count() == 2
    precos = session.query(PrecoAtivo).all()
    assert len(precos) == 1
    assert precos[0].preco == 21.0


def test_venda_nao_cria_preco(client, session):
    """Só a `compra` faz upsert; uma `venda` com preço não grava preço.

    Cálculo à mão: uma compra (cria 1 preço) + uma venda com `preco_unitario`
    -> 2 movimentos e **1** preço. A condição é
    `payload.tipo_movimento.value == "compra"` (`routers/patrimonio.py:97`).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "tipo_movimento": "compra",
            "data": "2025-01-10",
            "quantidade": 10,
            "preco_unitario": 20.0,
            "valor_total": -200.0,
        },
    )

    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "tipo_movimento": "venda",
            "data": "2025-03-10",
            "quantidade": 10,
            "preco_unitario": 30.0,
            "valor_total": 300.0,
        },
    )

    assert r.status_code == 200
    assert session.query(MovimentoAtivo).count() == 2
    assert session.query(PrecoAtivo).count() == 1


def test_compra_sem_preco_unitario_nao_cria_preco(client, session):
    """Uma compra sem `preco_unitario` não grava preço nenhum.

    Cálculo à mão: 1 movimento e 0 preços; a segunda condição da linha 97
    (`preco_unitario is not None`) falha.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)

    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "tipo_movimento": "compra",
            "data": "2025-01-10",
            "quantidade": 10,
            "valor_total": -200.0,
        },
    )

    assert r.status_code == 200
    assert session.query(MovimentoAtivo).count() == 1
    assert session.query(PrecoAtivo).count() == 0


def test_criar_movimento_em_ativo_inexistente_da_404(client, session):
    """Um movimento para um ativo que não existe responde 404 e não grava nada."""
    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": 999,
            "tipo_movimento": "compra",
            "data": "2025-01-10",
            "quantidade": 10,
            "preco_unitario": 20.0,
            "valor_total": -200.0,
        },
    )

    assert r.status_code == 404
    assert r.json()["detail"] == "Ativo não encontrado."
    assert session.query(MovimentoAtivo).count() == 0


# ---------------------------------------------------------------------------
# B17/B18 — DELETE /api/patrimonio/movimentos/{id}
# ---------------------------------------------------------------------------

def test_eliminar_movimento_apaga_so_o_movimento(client, session):
    """Apagar um movimento não toca nos preços.

    Cálculo à mão: ativo com 1 movimento e 1 preço -> `DELETE` do movimento
    -> 0 movimentos e 1 preço (o preço é por `(ativo, data)`, não por
    movimento).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    movimento = semear_movimento(session, ativo, TipoMovimento.compra,
                                 date(2025, 1, 10), valor_total=-200.0,
                                 quantidade=10)
    semear_preco(session, ativo, date(2025, 1, 10), 20.0)

    r = client.delete(f"/api/patrimonio/movimentos/{movimento.id}")

    assert r.status_code == 204
    assert r.content == b""
    assert session.query(MovimentoAtivo).count() == 0
    assert session.query(PrecoAtivo).count() == 1


def test_eliminar_movimento_inexistente_da_404(client, session):
    """Apagar um movimento que não existe responde 404."""
    r = client.delete("/api/patrimonio/movimentos/999")

    assert r.status_code == 404
    assert r.json()["detail"] == "Movimento não encontrado."


# ---------------------------------------------------------------------------
# B19 — GET /api/patrimonio/ativos/{id}/movimentos
# ---------------------------------------------------------------------------

def test_listar_movimentos_ordena_por_data(client, session):
    """Os movimentos vêm por `data` ascendente.

    Cálculo à mão: semeados por esta ordem — `2025-02-01` e `2025-01-01`. A
    query `order_by(MovimentoAtivoModel.data)` (`routers/patrimonio.py:128`)
    devolve primeiro o de `2025-01-01`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 2, 1),
                     valor_total=-200.0, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 1),
                     valor_total=-100.0, quantidade=5)

    r = client.get(f"/api/patrimonio/ativos/{ativo.id}/movimentos")

    assert r.status_code == 200
    assert [m["data"] for m in r.json()] == ["2025-01-01", "2025-02-01"]


def test_listar_movimentos_de_ativo_inexistente_da_404(client, session):
    """Listar movimentos de um ativo que não existe responde 404."""
    r = client.get("/api/patrimonio/ativos/999/movimentos")

    assert r.status_code == 404
    assert r.json()["detail"] == "Ativo não encontrado."


# ---------------------------------------------------------------------------
# B20/B21/B22 — POST /api/patrimonio/precos
# ---------------------------------------------------------------------------

def test_registar_preco_cria_o_registo(client, session):
    """Um preço novo é gravado.

    Cálculo à mão: um `POST` -> 1 preço `(ativo, 2025-01-10, 20.0)`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)

    r = client.post(
        "/api/patrimonio/precos",
        json={"ativo_id": ativo.id, "data": "2025-01-10", "preco": 20.0},
    )

    assert r.status_code == 200
    assert r.json()["preco"] == 20.0
    assert session.query(PrecoAtivo).count() == 1


def test_registar_preco_no_mesmo_dia_actualiza(client, session):
    """Preço repetido para o mesmo ativo e dia faz upsert.

    Cálculo à mão: 20.0 e depois 25.0 no mesmo `(ativo, data)` -> continua a
    haver **1** preço, com 25.0 (`routers/patrimonio.py:141-150`).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    base = {"ativo_id": ativo.id, "data": "2025-01-10"}
    client.post("/api/patrimonio/precos", json={**base, "preco": 20.0})

    r = client.post("/api/patrimonio/precos", json={**base, "preco": 25.0})

    assert r.status_code == 200
    assert r.json()["preco"] == 25.0
    precos = session.query(PrecoAtivo).all()
    assert len(precos) == 1
    assert precos[0].preco == 25.0


def test_registar_preco_em_ativo_inexistente_da_404(client, session):
    """Um preço para um ativo que não existe responde 404 e não grava nada."""
    r = client.post(
        "/api/patrimonio/precos",
        json={"ativo_id": 999, "data": "2025-01-10", "preco": 20.0},
    )

    assert r.status_code == 404
    assert r.json()["detail"] == "Ativo não encontrado."
    assert session.query(PrecoAtivo).count() == 0


# ---------------------------------------------------------------------------
# B23 — GET /api/patrimonio/ativos/{id}/resumo (só o 404)
# ---------------------------------------------------------------------------

def test_resumo_de_ativo_inexistente_da_404(client, session):
    """O resumo de um ativo que não existe responde 404.

    Os ramos felizes deste endpoint estão em `test_patrimonio_fifo.py`; aqui
    cobre-se apenas a guarda `if not ativo` (`routers/patrimonio.py:159-161`).
    """
    r = client.get("/api/patrimonio/ativos/999/resumo")

    assert r.status_code == 404
    assert r.json()["detail"] == "Ativo não encontrado."

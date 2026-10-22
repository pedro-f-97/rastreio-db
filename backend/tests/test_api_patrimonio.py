"""Testes de API do router `routers/patrimonio.py`.

Âmbito deste ficheiro
---------------------
O router estava quase todo por cobrir. O relatório de cobertura dava 127
declarações e 79 em falta em `routers/patrimonio.py`, e 85 declarações com 31
em falta em `servicos/patrimonio_serv.py`.

O que **não** se repete aqui: os ramos felizes de `GET
/api/patrimonio/ativos/{id}/resumo` e o núcleo `_resumo_valor_ativo` já estão
fixados por `test_patrimonio_fifo.py`. Deste endpoint só se cobre o 404.

Cobre-se ativos, movimentos e preços de ativos (B2 a B23), e ainda os
pendentes e a evolução de património (B1 e B24 a B30). A evolução não tem
endpoint próprio para `calcular_patrimonio_em`, por isso é exercitada por
`GET /api/patrimonio/evolucao`.

Estado final da BD
------------------
Entra-se sempre pelo endpoint real, sobre a BD in-memory da fixture `session`,
e confirma-se também o que ficou gravado na sessão. Os valores esperados são
calculados à mão e escritos como constantes.

Notas de comportamento (sem correcção)
--------------------------------------
* `DELETE /api/patrimonio/ativos/{id}` apaga à mão os movimentos e os preços do
  ativo antes de apagar o ativo (`routers/patrimonio.py:79-81`): com a pragma
  `foreign_keys` ligada e sem `ON DELETE`, a BD recusaria apagá-lo com
  filhos.
* `POST /api/patrimonio/movimentos` grava o movimento e o preço num só
  `commit()` (`routers/patrimonio.py:107`): se a gravação do preço falhar, o
  movimento também não fica gravado (ver
  `test_criar_movimento_falha_no_preco_nao_grava_o_movimento`).
* O upsert de preço só acontece em movimentos de `compra` com `preco_unitario`
  preenchido (`routers/patrimonio.py:95`).
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from database import (
    Ativo,
    Categoria,
    Conta,
    MovimentoAtivo,
    PrecoAtivo,
    Subcategoria,
    TipoAtivo,
    TipoCategoria,
    TipoContabilizacao,
    TipoMovimento,
    Transacao,
)
from routers import patrimonio as patrimonio_router

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
        TipoContabilizacao.investimento if tipo.tem_unidades else TipoContabilizacao.patrimonio
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


def semear_movimento(
    session, ativo, tipo_movimento, data, valor_total, quantidade=None, preco_unitario=None
):
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


def semear_conta(session, nome, saldo_referencia, data_referencia):
    conta = Conta(
        nome=nome,
        saldo_referencia=saldo_referencia,
        data_referencia=data_referencia,
        ativa=True,
    )
    session.add(conta)
    session.commit()
    return conta


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

    O `tipo_id` inexistente está em
    `test_criar_ativo_com_tipo_inexistente_da_404_e_nao_grava`.
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
    ainda `AAA` (o router só muda o símbolo se o campo vier no pedido).
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


def test_editar_ativo_com_simbolo_null_apaga_o_simbolo(client, session):
    """`simbolo: null` apaga o símbolo, e o nome fica (achado 5.1).

    Cálculo à mão: ativo `A`/`AAA`; `PUT {"nome": "A", "simbolo": null}`, que é
    o que a página envia com o campo vazio -> símbolo `None`. Antes da
    correcção, `null` contava como «não alterar» e o símbolo ficava `AAA`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "A", tipo, simbolo="AAA")

    r = client.put(f"/api/patrimonio/ativos/{ativo.id}", json={"nome": "A", "simbolo": None})

    assert r.status_code == 200
    assert (r.json()["nome"], r.json()["simbolo"]) == ("A", None)
    session.refresh(ativo)
    assert ativo.simbolo is None


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
    (`routers/patrimonio.py:79-81`), porque a BD não a faz: as chaves não têm
    `ON DELETE`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-200.0, quantidade=10
    )
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


def test_criar_movimento_falha_no_preco_nao_grava_o_movimento(client, session):
    """Se a gravação do preço falhar, o movimento da mesma compra não fica gravado.

    Antes da correcção, o handler fazia `commit()` do movimento antes de tratar do
    preço, e uma falha no preço deixava o movimento gravado sozinho.

    A falha é provocada por um trigger que recusa qualquer `INSERT` em
    `precos_ativo`. Uma compra com `preco_unitario` cria um preço novo
    (`routers/patrimonio.py:95-104`), por isso o `commit()` único da linha 107
    rebenta com `IntegrityError` e a transacção inteira é desfeita.

    O `session.rollback()` depois do pedido faz o que o `get_db` real faz ao
    fechar a sessão; a fixture de testes partilha a sessão e não a fecha.

    Estado final da BD, calculado à mão: 0 movimentos e 0 preços.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    session.execute(
        text(
            "CREATE TRIGGER recusa_preco BEFORE INSERT ON precos_ativo "
            "BEGIN SELECT RAISE(ABORT, 'falha simulada no preço'); END"
        )
    )
    session.commit()

    with pytest.raises(IntegrityError):
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

    session.rollback()
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 0
    assert session.query(PrecoAtivo).count() == 0


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


def test_venda_regista_o_preco_como_cotacao(client, session):
    """Uma `venda` com preço também regista a cotação do dia (achado 5.3).

    Cálculo à mão: uma compra de 10 a 20.0 em 2025-01-10 (cria o preço 20.0) e
    uma venda de 4 a 30.0 em 2025-03-10 -> 2 movimentos e **2** preços. O resumo
    usa o preço mais recente: restam 10 - 4 = 6 unidades, avaliadas a 30.0 ->
    6 * 30.0 = 180.0. Antes da correcção, a venda não gravava preço e as 6
    unidades ficavam a 20.0 (120.0).
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
            "quantidade": 4,
            "preco_unitario": 30.0,
            "valor_total": 120.0,
        },
    )

    assert r.status_code == 200
    assert session.query(MovimentoAtivo).count() == 2
    assert sorted((p.data, p.preco) for p in session.query(PrecoAtivo).all()) == [
        (date(2025, 1, 10), 20.0),
        (date(2025, 3, 10), 30.0),
    ]

    resumo = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo").json()
    assert (resumo["quantidade"], resumo["preco_atual"], resumo["data_preco"]) == (
        6.0,
        30.0,
        "2025-03-10",
    )
    assert resumo["valor_atual"] == 180.0


def test_venda_recusada_nao_regista_preco(client, session):
    """Uma venda acima da posição é recusada, e o seu preço também não fica.

    Cálculo à mão: compra de 10 a 20.0 (1 preço); venda de 15 a 30.0 -> 15 > 10,
    422. O movimento e o preço da venda iam no mesmo `commit`, que não chega a
    correr: ficam 1 movimento e 1 preço (o da compra, 20.0).
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
            "quantidade": 15,
            "preco_unitario": 30.0,
            "valor_total": 450.0,
        },
    )

    assert r.status_code == 422
    session.rollback()
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 1
    assert [p.preco for p in session.query(PrecoAtivo).all()] == [20.0]


def test_dividendo_nao_regista_preco(client, session):
    """Um `dividendo` com preço não regista cotação: não é uma troca de unidades.

    Cálculo à mão: só compras e vendas gravam preço; um dividendo com
    `preco_unitario` 0.5 -> 1 movimento e 0 preços.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)

    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "tipo_movimento": "dividendo",
            "data": "2025-03-10",
            "quantidade": 10,
            "preco_unitario": 0.5,
            "valor_total": 5.0,
        },
    )

    assert r.status_code == 200
    assert session.query(MovimentoAtivo).count() == 1
    assert session.query(PrecoAtivo).count() == 0


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
    movimento = semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-200.0, quantidade=10
    )
    semear_preco(session, ativo, date(2025, 1, 10), 20.0)

    r = client.delete(f"/api/patrimonio/movimentos/{movimento.id}")

    assert r.status_code == 204
    assert r.content == b""
    assert session.query(MovimentoAtivo).count() == 0
    assert session.query(PrecoAtivo).count() == 1


# ---------------------------------------------------------------------------
# Sobre-venda recusada
# ---------------------------------------------------------------------------


def _vender(client, ativo, data, quantidade, valor_total):
    return client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "tipo_movimento": "venda",
            "data": data,
            "quantidade": quantidade,
            "valor_total": valor_total,
        },
    )


def test_venda_acima_da_posicao_da_422_e_nao_grava(client, session):
    """Vender 15 unidades tendo 10 é recusado, e nada fica gravado.

    Antes da correcção, a venda era aceite e o FIFO reescalava o encaixe em silêncio.
    Cálculo à mão: compra de 10 em 2025-01-10; venda de 15 em 2025-04-10 ->
    15 - 10 = 5 > 0 -> 422. Fica só a compra (1 movimento).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-100.0, quantidade=10
    )

    r = _vender(client, ativo, "2025-04-10", 15, 300.0)

    assert r.status_code == 422
    assert r.json()["detail"] == (
        "A venda de 10/04/2025 (15 unidades) excede as 10 unidades em carteira nessa data."
    )
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 1


def test_venda_de_toda_a_posicao_e_aceite(client, session):
    """Vender exactamente as unidades em carteira continua a ser aceite.

    Cálculo à mão: compras de 2,5 e 7,5 (total 10); venda de 10 -> 10 - 10 = 0,
    não excede -> 200 e 3 movimentos.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-25.0, quantidade=2.5
    )
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 2, 10), valor_total=-75.0, quantidade=7.5
    )

    r = _vender(client, ativo, "2025-04-10", 10, 120.0)

    assert r.status_code == 200
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 3


def test_venda_antiga_que_deixa_uma_venda_posterior_sem_unidades_da_422(client, session):
    """Uma venda inserida no passado é recusada se uma venda posterior deixar de caber.

    Cálculo à mão: compra de 10 em 2025-01-10 e venda de 8 em 2025-03-01, já
    gravadas. Nova venda de 5 em 2025-02-01: nessa data há 10, e a venda cabe;
    mas a de 2025-03-01 passa a ter só 10 - 5 = 5 em carteira para vender 8 ->
    422 a apontar a venda de 01/03/2025. Ficam os 2 movimentos de antes.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-100.0, quantidade=10
    )
    semear_movimento(
        session, ativo, TipoMovimento.venda, date(2025, 3, 1), valor_total=96.0, quantidade=8
    )

    r = _vender(client, ativo, "2025-02-01", 5, 60.0)

    assert r.status_code == 422
    assert r.json()["detail"] == (
        "A venda de 01/03/2025 (8 unidades) excede as 5 unidades em carteira nessa data."
    )
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 2


def test_apagar_compra_que_deixa_uma_venda_sem_unidades_da_422(client, session):
    """Apagar uma compra é recusado se uma venda deixar de ter unidades.

    Cálculo à mão: compras de 10 (2025-01-10) e 0,5 (2025-02-10), venda de
    10,5 (2025-03-01). Sem a compra de 0,5, a venda tem só 10 em carteira ->
    422. A compra continua gravada (3 movimentos).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-100.0, quantidade=10
    )
    compra = semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 2, 10), valor_total=-5.0, quantidade=0.5
    )
    semear_movimento(
        session, ativo, TipoMovimento.venda, date(2025, 3, 1), valor_total=126.0, quantidade=10.5
    )

    r = client.delete(f"/api/patrimonio/movimentos/{compra.id}")

    assert r.status_code == 422
    assert r.json()["detail"] == (
        "A venda de 01/03/2025 (10,5 unidades) excede as 10 unidades em carteira nessa data."
    )
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 3


def test_apagar_venda_ou_vender_bem_sem_unidades_nao_e_verificado(client, session):
    """A verificação só se aplica a ativos com unidades, e apagar uma venda passa sempre.

    Cálculo à mão:
      * bem sem unidades (casa), com uma compra sem quantidade: venda com
        `quantidade=1` -> 200. Se o bem fosse verificado, a posição seria 0 e
        a venda de 1 seria recusada; o ramo dos bens não tem posição;
      * ativo com unidades: compra de 10 e venda de 4; apagar a venda -> 204,
        e fica 1 movimento no ativo com unidades.
    """
    tipo_bem = semear_tipo(session, "Imovel", tem_unidades=False)
    casa = semear_ativo(session, "Casa", tipo_bem)
    semear_movimento(session, casa, TipoMovimento.compra, date(2024, 1, 1), valor_total=-150000.0)
    r_bem = _vender(client, casa, "2025-05-01", 1, 200000.0)
    assert r_bem.status_code == 200

    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-100.0, quantidade=10
    )
    venda = semear_movimento(
        session, ativo, TipoMovimento.venda, date(2025, 3, 1), valor_total=48.0, quantidade=4
    )

    r = client.delete(f"/api/patrimonio/movimentos/{venda.id}")

    assert r.status_code == 204
    session.expire_all()
    assert session.query(MovimentoAtivo).filter_by(ativo_id=ativo.id).count() == 1


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
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 2, 1), valor_total=-200.0, quantidade=10
    )
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 1), valor_total=-100.0, quantidade=5
    )

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


def test_registar_preco_infinito_e_recusado_sem_gravar(client, session):
    """Um preço Infinity é recusado à entrada e não fica gravado.

    O JSON não tem o literal `Infinity`, mas o `json` do Python aceita-o, por
    isso o corpo vai escrito à mão. Antes da correcção era gravado, e o resumo e a
    evolução do património passavam a dar 500, porque a resposta não se
    serializa.

    Cálculo à mão: o `FiniteFloat` do schema recusa-o, e nada é gravado. A
    resposta é 500 e não 422: o handler de validação do FastAPI repete o valor
    recebido no corpo do erro (`"input": inf`), e o JSON não o aceita. Pelo
    browser isto não acontece, porque `JSON.stringify(Infinity)` dá `null`, e
    `null` dá 422.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    cliente = TestClient(client.app, raise_server_exceptions=False)

    r = cliente.post(
        "/api/patrimonio/precos",
        content=f'{{"ativo_id": {ativo.id}, "data": "2025-01-10", "preco": Infinity}}',
        headers={"Content-Type": "application/json"},
    )

    assert r.status_code == 500
    assert session.query(PrecoAtivo).count() == 0


def test_criar_movimento_com_quantidade_nan_e_recusado_sem_gravar(client, session):
    """Uma quantidade NaN é recusada à entrada e o movimento não fica gravado.

    Antes da correcção, o SQLite gravava o NaN como NULL, e numa coluna que aceita
    NULL o movimento ficava gravado em silêncio, com a quantidade a 0 para o
    FIFO. A resposta é 500 e não 422, pela mesma razão do teste do preço
    infinito (o erro repete `"input": nan`).

    Cálculo à mão: o `FiniteFloat` recusa o NaN -> 0 movimentos.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    cliente = TestClient(client.app, raise_server_exceptions=False)

    r = cliente.post(
        "/api/patrimonio/movimentos",
        content=(
            f'{{"ativo_id": {ativo.id}, "tipo_movimento": "compra", '
            '"data": "2025-01-10", "quantidade": NaN, "valor_total": -200.0}'
        ),
        headers={"Content-Type": "application/json"},
    )

    assert r.status_code == 500
    assert session.query(MovimentoAtivo).count() == 0


# ---------------------------------------------------------------------------
# B23 — GET /api/patrimonio/ativos/{id}/resumo (só o 404)
# ---------------------------------------------------------------------------


def _hoje_fixo(monkeypatch, ano, mes, dia):
    """Fixa o `date.today()` do router, como em
    `test_evolucao_sem_parametros_usa_hoje_como_data_fim`."""
    from datetime import date as Date

    class HojeFixo(Date):
        @classmethod
        def today(cls):
            return cls(ano, mes, dia)

    monkeypatch.setattr(patrimonio_router, "date", HojeFixo)


def test_registar_preco_com_data_futura_da_422(client, session, monkeypatch):
    """Um preço com data depois de hoje é recusado; o de hoje é aceite.

    Cálculo à mão, com hoje = 2025-06-30:
      2025-07-01 > 2025-06-30 -> 422, nada gravado
      2025-06-30 = hoje       -> 200, 1 preço gravado
    """
    _hoje_fixo(monkeypatch, 2025, 6, 30)
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)

    r_futuro = client.post(
        "/api/patrimonio/precos", json={"ativo_id": ativo.id, "data": "2025-07-01", "preco": 20.0}
    )
    assert r_futuro.status_code == 422
    assert r_futuro.json()["detail"] == "A data do preço não pode ser futura."
    session.expire_all()
    assert session.query(PrecoAtivo).count() == 0

    r_hoje = client.post(
        "/api/patrimonio/precos", json={"ativo_id": ativo.id, "data": "2025-06-30", "preco": 20.0}
    )
    assert r_hoje.status_code == 200
    session.expire_all()
    assert session.query(PrecoAtivo).count() == 1


def test_listar_precos_do_mais_recente_para_o_mais_antigo(client, session):
    """`GET /ativos/{id}/precos` lista só os preços do ativo, por data descendente.

    Cálculo à mão: Acao com preços em 2025-01-10 (20.0) e 2025-03-01 (25.0);
    outro ativo com um preço que não pode aparecer. Ordem esperada:
    2025-03-01, 2025-01-10. Ativo inexistente -> 404.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    outro = semear_ativo(session, "Outra", tipo)
    semear_preco(session, ativo, date(2025, 1, 10), 20.0)
    semear_preco(session, ativo, date(2025, 3, 1), 25.0)
    semear_preco(session, outro, date(2025, 2, 1), 99.0)

    r = client.get(f"/api/patrimonio/ativos/{ativo.id}/precos")

    assert r.status_code == 200
    assert [(x["data"], x["preco"]) for x in r.json()] == [
        ("2025-03-01", 25.0),
        ("2025-01-10", 20.0),
    ]
    assert client.get("/api/patrimonio/ativos/999/precos").status_code == 404


def test_eliminar_preco_apaga_so_esse_preco(client, session):
    """`DELETE /precos/{id}` apaga o preço e o resumo passa a usar o anterior.

    Cálculo à mão: 10 un.; preços 20.0 (2025-01-10) e 25.0 (2025-03-01).
    Antes: valor_atual = 10 x 25 = 250.0. Apagar o de 2025-03-01 -> 204,
    fica 1 preço e valor_atual = 10 x 20 = 200.0. Apagar outra vez -> 404.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-200.0, quantidade=10
    )
    semear_preco(session, ativo, date(2025, 1, 10), 20.0)
    recente = semear_preco(session, ativo, date(2025, 3, 1), 25.0)

    resumo = f"/api/patrimonio/ativos/{ativo.id}/resumo"
    assert client.get(resumo).json()["valor_atual"] == 250.0

    r = client.delete(f"/api/patrimonio/precos/{recente.id}")

    assert r.status_code == 204
    session.expire_all()
    assert session.query(PrecoAtivo).count() == 1
    assert client.get(resumo).json()["valor_atual"] == 200.0
    assert client.delete(f"/api/patrimonio/precos/{recente.id}").status_code == 404


def test_resumo_de_ativo_inexistente_da_404(client, session):
    """O resumo de um ativo que não existe responde 404.

    Os ramos felizes deste endpoint estão em `test_patrimonio_fifo.py`; aqui
    cobre-se apenas a guarda `if not ativo` (`routers/patrimonio.py:159-161`).
    """
    r = client.get("/api/patrimonio/ativos/999/resumo")

    assert r.status_code == 404
    assert r.json()["detail"] == "Ativo não encontrado."


# ---------------------------------------------------------------------------
# B1 — GET /api/patrimonio/pendentes
# ---------------------------------------------------------------------------


def test_pendentes_so_transacoes_de_patrimonio_sem_movimento(client, session):
    """Só entram transações de subcategoria de património e sem movimento.

    Cálculo à mão: das cinco transações semeadas, só `t2` e `t1` cumprem:
      * `t5` não tem subcategoria -> o `JOIN` interno com `subcategorias`
        exclui-a;
      * `t4` tem subcategoria com `trata_patrimonio=0` -> excluída;
      * `t3` já tem um movimento ligado (`m.transacao_id`) -> o
        `LEFT JOIN ... m.id IS NULL` exclui-a.

    Sobram `t2` (2025-01-20) e `t1` (2025-01-10), por `data DESC`.
    """
    categoria = Categoria(nome="Investimentos", tipo=TipoCategoria.despesa)
    session.add(categoria)
    session.commit()
    categoria_patrimonio = Subcategoria(
        nome="Acoes", categoria_id=categoria.id, trata_patrimonio=True
    )
    categoria_normal = Subcategoria(nome="Casa", categoria_id=categoria.id, trata_patrimonio=False)
    session.add_all([categoria_patrimonio, categoria_normal])
    session.commit()

    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)

    t1 = Transacao(
        data=date(2025, 1, 10),
        descricao="Compra ETF",
        valor=-300.0,
        subcategoria_id=categoria_patrimonio.id,
    )
    t2 = Transacao(
        data=date(2025, 1, 20),
        descricao="Compra acoes",
        valor=-200.0,
        subcategoria_id=categoria_patrimonio.id,
    )
    t3 = Transacao(
        data=date(2025, 1, 15),
        descricao="Venda",
        valor=150.0,
        subcategoria_id=categoria_patrimonio.id,
    )
    t4 = Transacao(
        data=date(2025, 1, 5),
        descricao="Supermercado",
        valor=-50.0,
        subcategoria_id=categoria_normal.id,
    )
    t5 = Transacao(
        data=date(2025, 1, 1), descricao="Sem subcategoria", valor=-10.0, subcategoria_id=None
    )
    session.add_all([t1, t2, t3, t4, t5])
    session.commit()

    movimento = MovimentoAtivo(
        ativo_id=ativo.id,
        transacao_id=t3.id,
        tipo_movimento=TipoMovimento.venda,
        data=date(2025, 1, 15),
        valor_total=150.0,
    )
    session.add(movimento)
    session.commit()

    r = client.get("/api/patrimonio/pendentes")

    assert r.status_code == 200
    assert [p["id"] for p in r.json()] == [t2.id, t1.id]
    assert [p["descricao"] for p in r.json()] == ["Compra acoes", "Compra ETF"]
    assert [p["subcategoria_id"] for p in r.json()] == [
        categoria_patrimonio.id,
        categoria_patrimonio.id,
    ]


# ---------------------------------------------------------------------------
# B24 — GET /api/patrimonio/evolucao (cenário completo)
# ---------------------------------------------------------------------------


def test_evolucao_calcula_por_mes_e_por_tipo(client, session):
    """Evolução de 2025-01-15 a 2025-03-20, com liquidez e dois tipos de ativo.

    Semente, por conta e por data:
      * conta A: `saldo_referencia=1000.00`, `data_referencia=2025-01-01`;
        transações `2025-01-01 +50.00` e `2025-01-15 -200.00`;
      * conta B: `saldo_referencia=100.00`, `data_referencia=2025-02-01`;
      * ativo de investimento (com unidades): compra `2025-01-10` de 10 un.
        por 200.00; preço `2025-01-20=25.00`; preço `2025-03-15=30.00`;
      * ativo físico (sem unidades): compra `2025-01-05` de 15000.00; preço
        `2025-03-01=14000.00` (diferente do custo, para distinguir os dois).

    Cálculo à mão, ponto a ponto (`gerar_evolucao` faz `min(fim do mês,
    data_fim)`):

    * **2025-01-31**
      - liquidez: conta A `1000.00 + (-200.00) = 800.00`. A transação de
        `2025-01-01 +50.00` fica de fora: o filtro é `data >
        conta.data_referencia` (estrito: o saldo de referência é o do fim do dia), e é exactamente a
        data de referência. A conta B, com referência `2025-02-01`, calcula-se
        para trás: `100.00 - (transações em ]2025-01-31, 2025-02-01]) =
        100.00 - 0 = 100.00` (antes do achado 4.1 valia 0). Liquidez:
        `800.00 + 100.00 = 900.00`.
      - investimentos: lote de 10 un. a 20.00; preço de `2025-01-20` (o de
        `2025-03-15` é posterior) -> `10 x 25.00 = 250.00`.
      - ativos_físicos: ainda sem preço até esta data -> vale o custo,
        `15000.00` (antes da correcção era 0.0).
      - total: `900.00 + 250.00 + 15000.00 = 16150.00`.
    * **2025-02-28**
      - liquidez: `800.00` (conta A) `+ 100.00` (conta B, sem transações
        próprias) `= 900.00`.
      - investimentos: `250.00` (o preço de 30.00 só chega a `2025-03-15`).
      - ativos_físicos: ainda sem preço -> custo, `15000.00`.
      - total: `900.00 + 250.00 + 15000.00 = 16150.00`.
    * **2025-03-20** (`min(2025-03-31, data_fim)`)
      - liquidez: `900.00`.
      - investimentos: `10 x 30.00 = 300.00`.
      - ativos_físicos: o preço de `2025-03-01` -> `14000.00`.
      - total: `900.00 + 300.00 + 14000.00 = 15200.00`.
    """
    conta_a = semear_conta(session, "A", 1000.00, date(2025, 1, 1))
    semear_conta(session, "B", 100.00, date(2025, 2, 1))
    session.add_all(
        [
            Transacao(data=date(2025, 1, 1), descricao="Entrada", valor=50.0, conta_id=conta_a.id),
            Transacao(data=date(2025, 1, 15), descricao="Saída", valor=-200.0, conta_id=conta_a.id),
        ]
    )
    session.commit()

    tipo_unidades = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo_invest = semear_ativo(session, "Acao", tipo_unidades)
    semear_movimento(
        session,
        ativo_invest,
        TipoMovimento.compra,
        date(2025, 1, 10),
        valor_total=-200.0,
        quantidade=10,
    )
    semear_preco(session, ativo_invest, date(2025, 1, 20), 25.00)
    semear_preco(session, ativo_invest, date(2025, 3, 15), 30.00)

    tipo_bem = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo_fisico = semear_ativo(session, "Casa", tipo_bem)
    semear_movimento(
        session, ativo_fisico, TipoMovimento.compra, date(2025, 1, 5), valor_total=-15000.0
    )
    semear_preco(session, ativo_fisico, date(2025, 3, 1), 14000.00)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-01-15", "data_fim": "2025-03-20"},
    )

    assert r.status_code == 200
    pontos = r.json()
    assert [p["data"] for p in pontos] == ["2025-01-31", "2025-02-28", "2025-03-20"]

    assert pontos[0] == {
        "data": "2025-01-31",
        "liquidez": 900.00,
        "investimentos": 250.00,
        "ativos_fisicos": 15000.00,
        "total": 16150.00,
    }
    assert pontos[1] == {
        "data": "2025-02-28",
        "liquidez": 900.00,
        "investimentos": 250.00,
        "ativos_fisicos": 15000.00,
        "total": 16150.00,
    }
    assert pontos[2] == {
        "data": "2025-03-20",
        "liquidez": 900.00,
        "investimentos": 300.00,
        "ativos_fisicos": 14000.00,
        "total": 15200.00,
    }


# ---------------------------------------------------------------------------
# B25 — o total é a soma dos componentes apresentados
# ---------------------------------------------------------------------------


def test_evolucao_total_e_a_soma_dos_componentes_arredondados(client, session):
    """O `total` é a soma dos três componentes já arredondados.

    Cálculo à mão:
      * conta: `saldo_referencia=0.005`, `data_referencia=2025-01-01`;
      * ativo físico com compra de 1.00 e preço `0.01`;
      * só há um ponto (`data_inicio = data_fim = 2025-06-30`).

    Componentes devolvidos, cada um arredondado a 2 casas:
      - liquidez        = `round(0.005, 2)      = 0.01`
      - investimentos   = `round(0.0, 2)        = 0.0`
      - ativos_físicos  = `round(0.01, 2)       = 0.01`
      - total           = `round(0.01 + 0.0 + 0.01, 2) = 0.02`

    Antes da correcção, o total vinha da soma **não** arredondada,
    `round(0.005 + 0.0 + 0.01, 2) = round(0.015, 2) = 0.01`, e ficava 1 cêntimo
    abaixo dos três componentes que o ecrã mostra ao lado (0.02).
    """
    semear_conta(session, "A", 0.005, date(2025, 1, 1))
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Terreno", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 1), valor_total=-1.0)
    semear_preco(session, ativo, date(2025, 1, 2), 0.01)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-06-30", "data_fim": "2025-06-30"},
    )

    assert r.status_code == 200
    assert len(r.json()) == 1
    ponto = r.json()[0]

    soma_componentes = round(
        ponto["liquidez"] + ponto["investimentos"] + ponto["ativos_fisicos"], 2
    )
    assert ponto["liquidez"] == 0.01
    assert ponto["investimentos"] == 0.0
    assert ponto["ativos_fisicos"] == 0.01
    assert soma_componentes == 0.02
    assert ponto["total"] == 0.02


def test_evolucao_total_sem_ruido_de_virgula_flutuante(client, session):
    """O `total` volta a ser arredondado depois de somar os componentes.

    Cálculo à mão: liquidez `0.10` (conta) e ativos físicos `0.20` (preço do
    bem). Em vírgula flutuante, `0.1 + 0.2 = 0.30000000000000004`; o total
    tem de vir `round(0.1 + 0.0 + 0.2, 2) = 0.3`.
    """
    semear_conta(session, "A", 0.10, date(2025, 1, 1))
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Terreno", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 1), valor_total=-1.0)
    semear_preco(session, ativo, date(2025, 1, 2), 0.20)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-06-30", "data_fim": "2025-06-30"},
    )

    assert r.status_code == 200
    ponto = r.json()[0]
    assert ponto["liquidez"] == 0.1
    assert ponto["investimentos"] == 0.0
    assert ponto["ativos_fisicos"] == 0.2
    assert ponto["total"] == 0.3


# ---------------------------------------------------------------------------
# B26 — a fronteira da data de referência é estrita
# ---------------------------------------------------------------------------


def test_evolucao_exclui_transacao_na_data_de_referencia(client, session):
    """Uma transação exactamente na data de referência fica de fora.

    Cálculo à mão: conta `100.00`, `data_referencia=2025-01-01`, e uma
    transação de `+50.00` na mesma data. O filtro é `data >
    conta.data_referencia` (`servicos/patrimonio_serv.py:112`), estrito, pelo
    que a liquidez é `100.00`.

    O saldo de referência é o do fim desse dia, que já inclui as transacções
    do dia. O `/api/contas/{id}/saldo` (`saldo_conta_em`) usa o mesmo
    `>`; antes da correcção usava `>=` e devolvia `150.00` para esta conta.
    """
    conta = semear_conta(session, "A", 100.0, date(2025, 1, 1))
    session.add(
        Transacao(data=date(2025, 1, 1), descricao="No limite", valor=50.0, conta_id=conta.id)
    )
    session.commit()

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-01-31", "data_fim": "2025-01-31"},
    )

    assert r.status_code == 200
    ponto = r.json()[0]
    assert ponto["liquidez"] == 100.00
    assert ponto["total"] == 100.00


# ---------------------------------------------------------------------------
# B27 — bem sem preço conta pelo custo
# ---------------------------------------------------------------------------


def test_evolucao_bem_sem_preco_conta_pelo_custo(client, session):
    """Um bem comprado e sem preço registado conta pelo custo de aquisição.

    Cálculo à mão: compra de `15000.00` num bem sem unidades e sem linha em
    `precos_ativo`. Para um `data_alvo` depois da compra, `_resumo_valor_ativo`
    devolve `valor = custo_base = 15000.00`, pelo que `ativos_fisicos` e o
    `total` são `15000.00`.

    Antes da correcção, o valor era 0.0 e o bem desaparecia do total. Decisão do
    utilizador: o custo é o valor de recurso enquanto não houver avaliação.
    """
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Terreno", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-15000.0)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-01-31", "data_fim": "2025-01-31"},
    )

    assert r.status_code == 200
    ponto = r.json()[0]
    assert ponto["investimentos"] == 0.0
    assert ponto["ativos_fisicos"] == 15000.0
    assert ponto["total"] == 15000.0


# ---------------------------------------------------------------------------
# B28 — a evolução ignora preços posteriores ao data_alvo
# ---------------------------------------------------------------------------


def test_evolucao_ignora_preco_posterior_ao_data_alvo(client, session):
    """Um preço registado depois do `data_alvo` não entra no cálculo.

    Cálculo à mão: ativo de investimento com 10 un. e um único preço a 20.00,
    registado em `2025-06-01`. Para `data_alvo=2025-03-31`, o filtro
    `PrecoAtivoModel.data <= data_alvo` não encontra preço, e o
    ativo vale então o custo das unidades, `100.00`. Se o preço posterior
    entrasse, valeria `10 x 20.00 = 200.00`.

    Vale para os pontos passados. O ponto de hoje usa o preço mais recente,
    como o resumo do ativo (ver
    `test_evolucao_ponto_de_hoje_usa_o_preco_mais_recente_como_o_resumo`).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-100.0, quantidade=10
    )
    semear_preco(session, ativo, date(2025, 6, 1), 20.00)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-03-31", "data_fim": "2025-03-31"},
    )

    assert r.status_code == 200
    ponto = r.json()[0]
    assert ponto["investimentos"] == 100.0
    assert ponto["total"] == 100.0


def test_evolucao_conta_tudo_o_que_tem_a_data_do_ponto(client, session):
    """O ponto é o fim do dia `data_alvo`: tudo o que tem essa data entra.

    Fixa as quatro fronteiras de `calcular_patrimonio_em`: a transacção, a conta
    cuja referência é o próprio dia, o movimento e o preço, todos com a data do
    ponto, `2025-03-31`.

    Semente:
      * conta A: `1000.00`, referência `2025-01-01`; transacção `2025-03-31
        -100.00`;
      * conta B: `50.00`, referência `2025-03-31`, sem transacções;
      * ativo com unidades: compras `2025-01-10` de 10 un. por 200.00 e
        `2025-03-31` de 5 un. por 150.00; preços `2025-02-01=20.00` e
        `2025-03-31=30.00`.

    Cálculo à mão, para o ponto `2025-03-31` (passado, sem preços futuros):
      * liquidez: `1000.00 - 100.00 + 50.00 = 950.00`;
      * investimentos: `(10 + 5) x 30.00 = 450.00`;
      * total: `950.00 + 450.00 = 1400.00`.

    Se uma fronteira deixasse o dia de fora: sem a transacção, liquidez
    `1050.00`; sem a conta B, `900.00`; sem o preço do dia, investimentos
    `15 x 20.00 = 300.00`; sem a compra do dia, `10 x 30.00 = 300.00`.
    """
    conta_a = semear_conta(session, "A", 1000.00, date(2025, 1, 1))
    semear_conta(session, "B", 50.00, date(2025, 3, 31))
    session.add(
        Transacao(data=date(2025, 3, 31), descricao="Saída", valor=-100.0, conta_id=conta_a.id)
    )
    session.commit()

    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-200.0, quantidade=10
    )
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 3, 31), valor_total=-150.0, quantidade=5
    )
    semear_preco(session, ativo, date(2025, 2, 1), 20.00)
    semear_preco(session, ativo, date(2025, 3, 31), 30.00)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-03-31", "data_fim": "2025-03-31"},
    )

    assert r.status_code == 200
    assert r.json() == [
        {
            "data": "2025-03-31",
            "liquidez": 950.00,
            "investimentos": 450.00,
            "ativos_fisicos": 0.0,
            "total": 1400.00,
        }
    ]


def test_evolucao_ponto_de_hoje_usa_o_preco_mais_recente_como_o_resumo(
    client, session, monkeypatch
):
    """O ponto de hoje usa o preço mais recente, mesmo com data futura.

    Decisão do utilizador: o resumo do ativo e o ponto de hoje do
    gráfico usam os dois o preço mais recente, para baterem certo no mesmo
    ecrã; os pontos passados continuam a usar o preço dessa data. O frontend
    mostra um aviso quando a data do preço é futura.

    "Hoje" fixado em 2025-06-30, como em
    `test_evolucao_sem_parametros_usa_hoje_como_data_fim`.

    Cálculo à mão: 10 un.; preços 20.00 em 2025-05-01 e 30.00 em 2025-08-01
    (futuro face a hoje).
      2025-05-31 (passado): preço até essa data = 20.00 -> 10 x 20 = 200.00
      2025-06-30 (hoje):    preço mais recente = 30.00 -> 10 x 30 = 300.00
      resumo: preço mais recente = 30.00 -> valor_atual 300.00, data_preco
        2025-08-01
    """
    from datetime import date as Date

    class HojeFixo(Date):
        @classmethod
        def today(cls):
            return cls(2025, 6, 30)

    monkeypatch.setattr(patrimonio_router, "date", HojeFixo)

    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)
    semear_movimento(
        session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-100.0, quantidade=10
    )
    semear_preco(session, ativo, date(2025, 5, 1), 20.00)
    semear_preco(session, ativo, date(2025, 8, 1), 30.00)

    r = client.get("/api/patrimonio/evolucao", params={"data_inicio": "2025-05-01"})

    assert r.status_code == 200
    assert [(p["data"], p["investimentos"]) for p in r.json()] == [
        ("2025-05-31", 200.00),
        ("2025-06-30", 300.00),
    ]

    resumo = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo").json()
    assert resumo["valor_atual"] == 300.00
    assert resumo["data_preco"] == "2025-08-01"


# ---------------------------------------------------------------------------
# B29 — dividendo num bem sem unidades
# ---------------------------------------------------------------------------


def test_evolucao_dividendo_de_bem_nao_chega_ao_total(client, session):
    """O dividendo de um bem sem unidades não entra no total do património.

    Cálculo à mão: bem com compra de `10000.00`, dividendo de `500.00` e preço
    de `10000.00`. O ramo dos bens soma o dividendo ao `realizado`
    (`servicos/patrimonio_serv.py:49-51`), mas `calcular_patrimonio_em` só lê
    o campo `valor` (`:145`): o dividendo não chega ao `ativos_fisicos` nem ao
    `total`, que ficam em `10000.00`.
    """
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Casa", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10), valor_total=-10000.0)
    semear_movimento(session, ativo, TipoMovimento.dividendo, date(2025, 2, 10), valor_total=500.0)
    semear_preco(session, ativo, date(2025, 2, 15), 10000.0)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-03-31", "data_fim": "2025-03-31"},
    )

    assert r.status_code == 200
    ponto = r.json()[0]
    assert ponto["ativos_fisicos"] == 10000.0
    assert ponto["total"] == 10000.0


# ---------------------------------------------------------------------------
# Número de queries da evolução
# ---------------------------------------------------------------------------


def test_evolucao_le_o_tipo_com_os_ativos_sem_query_por_tipo(client, session):
    """Fixa o número de queries de `/evolucao`: o tipo vem com os ativos.

    Semente: 1 conta (`100.00`, referência `2025-01-01`, sem transações) e 2
    ativos de 2 tipos diferentes:
      * "ETF" (com unidades): compra `2025-01-10` de 10 un. por 200.00; preço
        `2025-01-10=25.00`;
      * "Casa" (sem unidades): compra `2025-01-05` de 1000.00, sem preço.

    Evolução de `2025-01-01` a `2025-02-28`, com as duas datas explícitas para
    o router não fazer a query da data mínima: 2 pontos.

    Queries à mão, por ponto (`calcular_patrimonio_em`): 1 (contas activas)
    + 1 (soma da conta, já com a referência passada) + 1 (ativos, com o tipo
    junto) + 2 x 2 (movimentos e preço de cada ativo) = 7. Com 2 pontos dá
    `2 x 7 = 14`. Sem o `joinedload` do tipo, cada ponto lia cada um dos 2
    tipos à parte: `14 + 2 x 2 = 18`.

    O `expunge_all()` antes do pedido põe o teste nas condições de produção,
    onde cada pedido tem a sua sessão e, sem a correção, cada ponto relê os
    tipos da BD. Sem ele, os tipos semeados ficam no identity map da sessão:
    o SQLAlchemy só os relê no primeiro ponto e, sem a correção, o teste daria
    `14 + 2 = 16` em vez dos 18 de produção.

    Valores à mão, iguais nos dois pontos: liquidez `100.00`; investimentos
    `10 x 25.00 = 250.00`; ativos_fisicos sem preço valem o custo, `1000.00`;
    total `100.00 + 250.00 + 1000.00 = 1350.00`.
    """
    from sqlalchemy import event

    semear_conta(session, "A", 100.0, date(2025, 1, 1))
    tipo_invest = semear_tipo(session, "Acoes", tem_unidades=True)
    etf = semear_ativo(session, "ETF", tipo_invest)
    semear_movimento(
        session, etf, TipoMovimento.compra, date(2025, 1, 10), valor_total=-200.0, quantidade=10
    )
    semear_preco(session, etf, date(2025, 1, 10), 25.00)
    tipo_bem = semear_tipo(session, "Imovel", tem_unidades=False)
    casa = semear_ativo(session, "Casa", tipo_bem)
    semear_movimento(session, casa, TipoMovimento.compra, date(2025, 1, 5), valor_total=-1000.0)
    session.expunge_all()

    queries = []

    def contar(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    engine = session.get_bind()
    event.listen(engine, "before_cursor_execute", contar)
    try:
        r = client.get(
            "/api/patrimonio/evolucao",
            params={"data_inicio": "2025-01-01", "data_fim": "2025-02-28"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", contar)

    assert r.status_code == 200
    assert len(queries) == 14
    assert r.json() == [
        {
            "data": "2025-01-31",
            "liquidez": 100.00,
            "investimentos": 250.00,
            "ativos_fisicos": 1000.00,
            "total": 1350.00,
        },
        {
            "data": "2025-02-28",
            "liquidez": 100.00,
            "investimentos": 250.00,
            "ativos_fisicos": 1000.00,
            "total": 1350.00,
        },
    ]


# ---------------------------------------------------------------------------
# B30 — datas por omissão de /evolucao
# ---------------------------------------------------------------------------


def test_evolucao_sem_parametros_usa_hoje_como_data_fim(client, session, monkeypatch):
    """ "Hoje" é injectado, para fixar as linhas 213-218 sem usar a data real.

    Sem parâmetros, `data_fim = date.today()` e, sem transações,
    `data_inicio = data_fim` (`routers/patrimonio.py:213-218`). Em vez de
    depender da data real do dia, substitui-se o símbolo `date` do módulo do
    router por uma subclasse que devolve `2025-06-30` em `today()`. É só
    "hoje" que muda; a construção de datas da evolução continua a correr no
    módulo do serviço.

    Cálculo à mão: conta `100.00` referência `2025-01-01`, sem transações ->
    um só ponto, em `2025-06-30`, com liquidez `100.00` e total `100.00`.
    """
    from datetime import date as Date

    class HojeFixo(Date):
        @classmethod
        def today(cls):
            return cls(2025, 6, 30)

    monkeypatch.setattr(patrimonio_router, "date", HojeFixo)

    semear_conta(session, "A", 100.0, date(2025, 1, 1))

    r = client.get("/api/patrimonio/evolucao")

    assert r.status_code == 200
    pontos = r.json()
    assert len(pontos) == 1
    assert pontos[0]["data"] == "2025-06-30"
    assert pontos[0]["liquidez"] == 100.00
    assert pontos[0]["total"] == 100.00


# ---------------------------------------------------------------------------
# IDs inexistentes
# ---------------------------------------------------------------------------


def test_criar_ativo_com_tipo_inexistente_da_404_e_nao_grava(client, session):
    """Um `tipo_id` que não existe dá 404 e o ativo não é gravado.

    Era um 500 que deixava o ativo gravado e órfão: o `commit` passava, e só a
    serialização de `schemas.Ativo` (que exige `tipo`) falhava.

    Cálculo à mão: `db.get(TipoAtivo, 999)` devolve None, logo `criar_ativo`
    responde 404 com "Tipo de ativo não encontrado." antes do `db.add`.

    Estado final da BD: 0 ativos.
    """
    r = client.post(
        "/api/patrimonio/ativos",
        json={
            "nome": "Acao X",
            "tipo_id": 999,
            "contabilizacao": "investimento",
        },
    )

    assert r.status_code == 404
    assert r.json() == {"detail": "Tipo de ativo não encontrado."}
    session.expire_all()
    assert session.query(Ativo).count() == 0


def test_criar_movimento_com_transacao_inexistente_da_404_e_nao_grava(client, session):
    """Um `transacao_id` que não existe dá 404 e nada é gravado.

    Cálculo à mão: o ativo existe, `db.get(Transacao, 999)` devolve None, logo
    `criar_movimento` responde 404 com "Transação não encontrada." antes do
    `db.add`; o upsert do preço (compra com `preco_unitario`) também não corre.

    Estado final da BD: 0 movimentos e 0 preços.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acao", tipo)

    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "transacao_id": 999,
            "tipo_movimento": "compra",
            "data": "2025-01-10",
            "quantidade": 10,
            "preco_unitario": 20.0,
            "valor_total": -200.0,
        },
    )

    assert r.status_code == 404
    assert r.json() == {"detail": "Transação não encontrada."}
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 0
    assert session.query(PrecoAtivo).count() == 0

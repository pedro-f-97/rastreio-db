"""Testes da API de contas (`/api/contas`).

Os valores esperados são calculados à mão e escritos como constantes, com o
cálculo exposto no docstring de cada teste. As datas são sempre explícitas:
nenhum destes testes assenta na data de hoje nem toca na base de dados real
(ver conftest.py).
"""

from datetime import date

from database import Conta, ModoValor, PerfilImportacao, Transacao

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def semear_conta(session, nome, saldo_referencia, data_referencia, ativa=True):
    conta = Conta(
        nome=nome,
        saldo_referencia=saldo_referencia,
        data_referencia=data_referencia,
        ativa=ativa,
    )
    session.add(conta)
    session.commit()
    return conta


def semear_transacao(session, data, descricao, valor, conta):
    transacao = Transacao(
        data=data,
        descricao=descricao,
        valor=valor,
        conta_id=conta.id,
    )
    session.add(transacao)
    session.commit()
    return transacao


# ---------------------------------------------------------------------------
# B1 — GET /api/contas/ (com barra final) e `incluir_inativas`
# ---------------------------------------------------------------------------


def test_listar_contas_filtra_inativas_por_omissao(client, session):
    """Sem `incluir_inativas`, só aparecem as contas activas.

    Cenário semeado: "Alfa" activa e "Zeta" inactiva (`ativa=False`), ambas
    criadas no mesmo momento, sem transacções.

    Cálculo à mão:
      get /api/contas/            -> só "Alfa" (linha 13-14 filtra
        `ativa == True` quando `incluir_inativas` é falso)
      get /api/contas/?incluir_inativas=true -> "Alfa" e "Zeta", por ordem
        alfabética (`order_by(ContaModel.nome)`, linha 15)

    Estado final da BD: as 2 contas continuam.
    """
    semear_conta(session, "Alfa", 0.0, date(2025, 1, 1), ativa=True)
    semear_conta(session, "Zeta", 0.0, date(2025, 1, 1), ativa=False)

    r = client.get("/api/contas/")

    assert r.status_code == 200
    assert [c["nome"] for c in r.json()] == ["Alfa"]
    assert all(c["ativa"] is True for c in r.json())

    r_tudo = client.get("/api/contas/", params={"incluir_inativas": "true"})

    assert r_tudo.status_code == 200
    assert [c["nome"] for c in r_tudo.json()] == ["Alfa", "Zeta"]

    assert session.query(Conta).count() == 2


# ---------------------------------------------------------------------------
# B2 — POST /api/contas/ e duplicado (409)
# ---------------------------------------------------------------------------


def test_criar_conta_e_rejeitar_duplicado(client, session):
    """Criar uma conta devolve-a completa e um nome repetido dá 409.

    Cenário: POST com nome "Cartão", saldo de referência 100.00 e referência
    em 2025-01-01.

    Cálculo à mão:
      resposta do POST = o Conta criado (`id` atribuído pelo SQLite, os
        restantes campos ecoados tal como enviados e `ativa` com o valor por
        omissão `True`) — schemas.py:183-190;
      segundo POST com o mesmo nome: a linha 19 encontra a existente e a
        linha 21 responde 409 com `{"detail": "Já existe uma conta com este
        nome."}`.

    Estado final da BD: 1 conta — o segundo POST não cria nada.
    """
    payload = {"nome": "Cartão", "saldo_referencia": 100.0, "data_referencia": "2025-01-01"}

    r = client.post("/api/contas/", json=payload)

    assert r.status_code == 200
    conta_id = r.json()["id"]
    assert r.json() == {
        "id": conta_id,
        "nome": "Cartão",
        "saldo_referencia": 100.0,
        "data_referencia": "2025-01-01",
        "ativa": True,
    }
    assert session.query(Conta).count() == 1

    r_dup = client.post("/api/contas/", json=payload)

    assert r_dup.status_code == 409
    assert r_dup.json() == {"detail": "Já existe uma conta com este nome."}
    assert session.query(Conta).count() == 1


# ---------------------------------------------------------------------------
# B3 — PUT /api/contas/{id} parcial (exclude_none) e 404
# ---------------------------------------------------------------------------


def test_atualizar_conta_parcialmente_e_404_se_nao_existir(client, session):
    """O PUT só muda os campos enviados; atualizar um id inexistente dá 404.

    Cenário: conta "Ordem" com 200.00 de referência em 2025-02-01, depois
    `PUT {"saldo_referencia": 900.0}`.

    Cálculo à mão: `model_dump(exclude_none=True)` (linha 33) só deixa a
    chave `saldo_referencia` no payload, por isso `nome`, `data_referencia`
    e `ativa` não são tocados — a resposta mantém-nos.

    PUT de um `conta_id` que não existe: a linha 31 falha a `first()` e a
    linha 32 responde 404 com `{"detail": "Conta não encontrada."}`.

    Estado final da BD: 1 conta, com o saldo de referência actualizado.
    """
    conta = semear_conta(session, "Ordem", 200.0, date(2025, 2, 1))

    r = client.put(f"/api/contas/{conta.id}", json={"saldo_referencia": 900.0})

    assert r.status_code == 200
    assert r.json() == {
        "id": conta.id,
        "nome": "Ordem",
        "saldo_referencia": 900.0,
        "data_referencia": "2025-02-01",
        "ativa": True,
    }

    r_404 = client.put("/api/contas/9999", json={"saldo_referencia": 1.0})

    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Conta não encontrada."}
    assert session.query(Conta).count() == 1


# ---------------------------------------------------------------------------
# B4/B5 — DELETE /api/contas/{id}: elimina ou desactiva
# ---------------------------------------------------------------------------


def test_apagar_conta_sem_transacoes_elimina(client, session):
    """Sem transacções, o DELETE elimina a conta.

    Cenário: conta "Poupança" sem nenhuma transacção.

    Cálculo à mão: a pré-checagem `tem_transacoes` (linha 44) não encontra a
    linha, o ramo `if` é saltado e a linha 49 apaga a conta — a resposta é
    `{"acao": "eliminada", "conta_id": <id>}` e a BD fica a 0 contas.

    Depois do DELETE, a lista activa também fica vazia.
    """
    conta = semear_conta(session, "Poupança", 0.0, date(2025, 1, 1))

    r = client.delete(f"/api/contas/{conta.id}")

    assert r.status_code == 200
    assert r.json() == {"acao": "eliminada", "conta_id": conta.id}
    assert session.query(Conta).filter_by(id=conta.id).count() == 0
    assert session.query(Transacao).count() == 0
    assert client.get("/api/contas/").json() == []


def test_apagar_conta_sem_transacoes_desassocia_os_perfis(client, session):
    """Sem transacções, a conta apaga-se e o perfil que a usava fica sem conta.

    Cenário: conta "Poupança" sem transacções e um perfil "Banco" associado.

    Cálculo à mão: `tem_transacoes` é None e `db.delete(conta)` corre; a
    `relationship` `Conta.perfis_importacao` (sem `cascade` de delete) põe
    `perfis_importacao.conta_id` a NULL antes do `DELETE`. Com a pragma
    `foreign_keys` ligada, é isso que deixa o `DELETE` passar.

    Estado final da BD: 0 contas, 1 perfil com `conta_id` None.
    """
    conta = semear_conta(session, "Poupança", 0.0, date(2025, 1, 1))
    perfil = PerfilImportacao(
        nome="Banco",
        linha_inicio_dados=1,
        coluna_data=0,
        formato_data="%d/%m/%Y",
        coluna_descricao=1,
        modo_valor=ModoValor.coluna_unica,
        coluna_valor=2,
        conta_id=conta.id,
    )
    session.add(perfil)
    session.commit()

    r = client.delete(f"/api/contas/{conta.id}")

    assert r.status_code == 200
    assert r.json() == {"acao": "eliminada", "conta_id": conta.id}
    session.expire_all()
    assert session.query(Conta).count() == 0
    assert session.get(PerfilImportacao, perfil.id).conta_id is None


def test_apagar_conta_com_transacoes_desativa(client, session):
    """Com transacções, o DELETE desactiva em vez de eliminar.

    Cenário: conta "Ordem" com uma transacção de -10.00 em 2025-01-02.

    Cálculo à mão: `tem_transacoes` (linha 44) encontra a transacção, o ramo
    `if` (linhas 45-48) marca `ativa = False` e responde `{"acao":
    "desativada", "conta_id": <id>}` — a linha NÃO é apagada, a transacção
    continua associada, e a lista activa (B1) fica vazia.

    Estado final da BD: 1 conta com `ativa=False` e 1 transacção.
    """
    conta = semear_conta(session, "Ordem", 0.0, date(2025, 1, 1))
    semear_transacao(session, date(2025, 1, 2), "Compra", -10.0, conta)

    r = client.delete(f"/api/contas/{conta.id}")

    assert r.status_code == 200
    assert r.json() == {"acao": "desativada", "conta_id": conta.id}

    conta_re = session.query(Conta).filter_by(id=conta.id).one()
    assert conta_re.ativa is False
    assert session.query(Transacao).filter_by(conta_id=conta.id).count() == 1
    assert client.get("/api/contas/").json() == []


# ---------------------------------------------------------------------------
# B6 — GET /api/contas/{id}/saldo e /api/patrimonio/evolucao concordam
# ---------------------------------------------------------------------------


def test_saldo_conta_e_evolucao_excluem_a_data_de_referencia(client, session):
    """O saldo da conta e a evolução excluem os dois a data de referência.

    O saldo de referência é o saldo no **fim** desse dia (decisão do
    utilizador): já reflecte as transacções do dia, que não se somam outra vez.

    Cenário: conta "Activa" com saldo de referência 100.00 e referência em
    2025-01-10, e três transacções:
      +50.00 em 2025-01-10  (exactamente na data de referência)
      +30.00 em 2025-01-15
      -20.00 em 2024-12-31  (antes da referência, não conta em lado nenhum)

    Cálculo à mão:
      saldo: a query usa `data > :data_referencia` (routers/contas.py:62):
        entra só o +30.00; ficam de fora o +50.00 da própria data e o -20.00
        de 2024.
        saldo = 100.00 + 30.00 = 130.0
      evolução a 2025-01-31: o filtro é `data > conta.data_referencia`
        (servicos/patrimonio_serv.py:112): o +50.00 da própria data fica de
        fora, o +30.00 entra; a data_fim corta em 2025-01-31, sem activos.
        liquidez = 100.00 + 30.00 = 130.0
        total = liquidez + 0 + 0 = 130.0

    Antes da correcção, o saldo usava `>=` e dava 180.0, enquanto a evolução dava 130.0
    para a mesma conta, no mesmo ecrã (o cartão Liquidez e o gráfico da página
    Património). Ver o teste homólogo
    `test_evolucao_exclui_transacao_na_data_de_referencia` em
    test_api_patrimonio.py.

    Estado final da BD: 1 conta e 3 transacções (o GET não escreve).
    """
    conta = semear_conta(session, "Activa", 100.0, date(2025, 1, 10))
    semear_transacao(session, date(2025, 1, 10), "No limite", 50.0, conta)
    semear_transacao(session, date(2025, 1, 15), "Almoço", 30.0, conta)
    semear_transacao(session, date(2024, 12, 31), "Jantar 2024", -20.0, conta)

    r_saldo = client.get(f"/api/contas/{conta.id}/saldo")

    assert r_saldo.status_code == 200
    assert r_saldo.json() == {
        "conta_id": conta.id,
        "nome": "Activa",
        "saldo_referencia": 100.0,
        "data_referencia": "2025-01-10",
        "saldo_atual": 130.0,
    }

    r_evolucao = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-01-31", "data_fim": "2025-01-31"},
    )

    assert r_evolucao.status_code == 200
    assert r_evolucao.json() == [
        {
            "data": "2025-01-31",
            "liquidez": 130.0,
            "investimentos": 0.0,
            "ativos_fisicos": 0.0,
            "total": 130.0,
        }
    ]
    assert session.query(Conta).count() == 1
    assert session.query(Transacao).count() == 3


# ---------------------------------------------------------------------------
# B7 — GET /api/contas/{id}/saldo sem transacções e 404
# ---------------------------------------------------------------------------


def test_saldo_conta_sem_transacoes_devolve_referencia_e_404(client, session):
    """Sem transacções o saldo é a referência; id inexistente dá 404.

    Cenário: conta "Poupança" com 50.00 de referência em 2025-01-01 e sem
    transacções.

    Cálculo à mão: `COALESCE(SUM(valor), 0)` (contas.py:59) devolve 0 quando
    não há linhas, pelo que `saldo_atual = 50.0 + 0.0 = 50.0`.

    GET de um id que não existe: a linha 56 falha a `first()` e a linha 57
    responde 404 com `{"detail": "Conta não encontrada."}`.

    Estado final da BD: 1 conta, 0 transacções.
    """
    conta = semear_conta(session, "Poupança", 50.0, date(2025, 1, 1))

    r = client.get(f"/api/contas/{conta.id}/saldo")

    assert r.status_code == 200
    assert r.json() == {
        "conta_id": conta.id,
        "nome": "Poupança",
        "saldo_referencia": 50.0,
        "data_referencia": "2025-01-01",
        "saldo_atual": 50.0,
    }

    r_404 = client.get("/api/contas/9999/saldo")

    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Conta não encontrada."}
    assert session.query(Conta).count() == 1

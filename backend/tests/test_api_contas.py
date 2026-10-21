"""Testes da API de contas (`/api/contas`).

Os valores esperados são calculados à mão e escritos como constantes, com o
cálculo exposto no docstring de cada teste. As datas são sempre explícitas:
nenhum destes testes assenta na data de hoje nem toca na base de dados real
(ver conftest.py).
"""

from datetime import date

from database import Conta, ModoValor, PerfilImportacao, Transacao
from routers import contas as contas_router

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


def test_apagar_conta_sem_transacoes_com_perfil_e_recusado(client, session):
    """Sem transacções mas com um perfil associado, a conta não se apaga (achado 1.2).

    Cenário: conta "Poupança" sem transacções e um perfil "Banco" associado.

    Cálculo à mão: `tem_transacoes` é None, mas `conta.perfis_importacao` tem o
    perfil "Banco", pelo que o endpoint responde 409 antes do `db.delete`.
    Antes da correcção, a conta apagava-se e o perfil ficava com `conta_id`
    None, sem aviso.

    Estado final da BD: a conta continua lá, activa, e o perfil continua com
    `conta_id` igual ao id da conta.
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

    assert r.status_code == 409
    assert r.json() == {
        "detail": "Não é possível apagar uma conta com perfis de importação associados."
    }
    session.expire_all()
    assert [(c.nome, c.ativa) for c in session.query(Conta).all()] == [("Poupança", True)]
    assert session.get(PerfilImportacao, perfil.id).conta_id == conta.id


def test_apagar_conta_com_transacoes_e_perfil_desativa(client, session):
    """Com transacções e um perfil, a conta desactiva-se e o perfil fica com ela.

    Cenário: conta "Ordem" com uma transacção de -10.00 em 2025-01-02 e um
    perfil "Banco" associado.

    Cálculo à mão: `tem_transacoes` encontra a transacção e o endpoint desactiva
    a conta antes de olhar para os perfis, pelo que o 409 do perfil não chega a
    acontecer. Nada é apagado, e o perfil continua a apontar para a conta.

    Estado final da BD: 1 conta com `ativa=False`; o perfil com `conta_id`
    igual ao id da conta.
    """
    conta = semear_conta(session, "Ordem", 0.0, date(2025, 1, 1))
    semear_transacao(session, date(2025, 1, 2), "Compra", -10.0, conta)
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
    assert r.json() == {"acao": "desativada", "conta_id": conta.id}
    session.expire_all()
    assert session.get(Conta, conta.id).ativa is False
    assert session.get(PerfilImportacao, perfil.id).conta_id == conta.id


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


def test_conta_desativada_continua_no_historico_da_liquidez(client, session):
    """Desactivar uma conta não a tira da evolução do património (achado 4.2).

    Cenário:
      "Fechada": 1000.00 de referência em 2025-02-28; +1200.00 em 2025-04-10;
        -2200.00 em 2025-05-15 (esvaziada); depois desactivada pelo DELETE.
      "Aberta": 500.00 de referência em 2025-01-01, sem transacções, activa.

    Cálculo à mão (liquidez no fim de cada mês, sem activos):
      Março: Fechada 1000.00 + Aberta 500.00 = 1500.00
      Abril: Fechada 1000.00 + 1200.00 = 2200.00; + 500.00 = 2700.00
      Maio:  Fechada 2200.00 - 2200.00 = 0.00;   + 500.00 = 500.00
    Antes da correcção, só contavam as activas: 500.00 nos três meses.
    """
    fechada = semear_conta(session, "Fechada", 1000.0, date(2025, 2, 28))
    semear_conta(session, "Aberta", 500.0, date(2025, 1, 1))
    semear_transacao(session, date(2025, 4, 10), "Salário", 1200.0, fechada)
    semear_transacao(session, date(2025, 5, 15), "Transferência", -2200.0, fechada)

    assert client.delete(f"/api/contas/{fechada.id}").json()["acao"] == "desativada"

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2025-03-01", "data_fim": "2025-05-31"},
    )

    assert r.status_code == 200
    assert [(p["data"], p["liquidez"]) for p in r.json()] == [
        ("2025-03-31", 1500.0),
        ("2025-04-30", 2700.0),
        ("2025-05-31", 500.0),
    ]


def _hoje_fixo(monkeypatch, ano, mes, dia):
    """Fixa o `date.today()` do router de contas, como em test_api_patrimonio.py."""
    from datetime import date as Date

    class HojeFixo(Date):
        @classmethod
        def today(cls):
            return cls(ano, mes, dia)

    monkeypatch.setattr(contas_router, "date", HojeFixo)


def _liquidez_em(client, dia):
    r = client.get("/api/patrimonio/evolucao", params={"data_inicio": dia, "data_fim": dia})
    assert r.status_code == 200
    return r.json()[0]["liquidez"]


def test_saldo_de_hoje_ignora_transacao_com_data_futura(client, session, monkeypatch):
    """O saldo de hoje e a evolução usam o mesmo cálculo: o futuro não conta.

    Cenário, com hoje = 2025-06-30: conta com 100.00 de referência em
    2025-06-01; +20.00 em 2025-06-15; +50.00 em 2025-07-10 (data futura).

    Cálculo à mão: entra só o que está em ]2025-06-01, 2025-06-30]:
      saldo = 100.00 + 20.00 = 120.00
    Antes da unificação, o saldo não tinha limite superior e dava
    100.00 + 20.00 + 50.00 = 170.00, enquanto a evolução já dava 120.00.
    """
    _hoje_fixo(monkeypatch, 2025, 6, 30)
    conta = semear_conta(session, "Corrente", 100.0, date(2025, 6, 1))
    semear_transacao(session, date(2025, 6, 15), "Reembolso", 20.0, conta)
    semear_transacao(session, date(2025, 7, 10), "Agendada", 50.0, conta)

    saldo = client.get(f"/api/contas/{conta.id}/saldo").json()["saldo_atual"]

    assert saldo == 120.0
    assert _liquidez_em(client, "2025-06-30") == 120.0


def test_liquidez_e_a_soma_dos_saldos_arredondados(client, session):
    """A liquidez soma os saldos de cada conta já arredondados, como o cartão.

    Cenário (meio cêntimo semeado à mão, só para forçar o arredondamento):
    duas contas com 10.005 de referência em 2025-01-01, sem transacções.

    Cálculo à mão: cada saldo arredonda para 10.01 (metade para longe de
    zero); o cartão soma 10.01 + 10.01 = 20.02, e a evolução a 2025-01-31
    também. Antes da unificação, a evolução arredondava a soma:
    10.005 + 10.005 = 20.01 -> 20.01, um cêntimo abaixo do cartão.
    """
    a = semear_conta(session, "A", 10.005, date(2025, 1, 1))
    b = semear_conta(session, "B", 10.005, date(2025, 1, 1))

    saldos = [client.get(f"/api/contas/{c.id}/saldo").json()["saldo_atual"] for c in (a, b)]

    assert saldos == [10.01, 10.01]
    assert _liquidez_em(client, "2025-01-31") == 20.02


def test_saldo_de_hoje_com_referencia_no_futuro_calcula_para_tras(client, session, monkeypatch):
    """Uma conta cuja referência ainda não chegou calcula-se para trás (4.1).

    Com hoje = 2025-06-30, 300.00 de referência em 2025-07-01 e +40.00 em
    2025-07-01 (no próprio dia, já incluído na referência):
      saldo = 300.00 - (transacções em ]2025-06-30, 2025-07-01]) = 300.00 - 40.00
            = 260.00, no saldo de hoje e na evolução
    (antes da unificação o saldo dava 300.00; depois dela e antes do 4.1, 0.00).
    """
    _hoje_fixo(monkeypatch, 2025, 6, 30)
    conta = semear_conta(session, "Nova", 300.0, date(2025, 7, 1))
    semear_transacao(session, date(2025, 7, 1), "Depósito", 40.0, conta)

    saldo = client.get(f"/api/contas/{conta.id}/saldo").json()["saldo_atual"]

    assert saldo == 260.0
    assert _liquidez_em(client, "2025-06-30") == 260.0


def test_evolucao_antes_da_referencia_calcula_para_tras(client, session):
    """Antes da data de referência, o saldo é a referência menos o que veio depois.

    O exemplo do achado 4.1: a conta é criada com o saldo de hoje e o histórico
    é importado. Referência: 2150.00 no fim de 2026-04-30. Transacções:
      +400.00 em 2026-02-10
      +400.00 em 2026-03-31 (no último dia do mês: conta nesse mês)
      +1200.00 em 2026-04-10
      -50.00 em 2026-04-30 (no dia da referência: já está nos 2150.00)

    Cálculo à mão, saldo(d) = 2150.00 - soma das transacções em ]d, 2026-04-30]:
      2026-01-31: 2150.00 - (400 + 400 + 1200 - 50) = 2150.00 - 1950.00 = 200.00
      2026-02-28: 2150.00 - (400 + 1200 - 50)       = 2150.00 - 1550.00 = 600.00
      2026-03-31: 2150.00 - (1200 - 50)             = 2150.00 - 1150.00 = 1000.00
      2026-04-30: a própria referência              = 2150.00
    Antes da correcção, os três primeiros meses davam 0.00.
    """
    conta = semear_conta(session, "Corrente", 2150.0, date(2026, 4, 30))
    semear_transacao(session, date(2026, 2, 10), "Salário", 400.0, conta)
    semear_transacao(session, date(2026, 3, 31), "Salário", 400.0, conta)
    semear_transacao(session, date(2026, 4, 10), "Prémio", 1200.0, conta)
    semear_transacao(session, date(2026, 4, 30), "Compras", -50.0, conta)

    r = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2026-01-01", "data_fim": "2026-04-30"},
    )

    assert r.status_code == 200
    assert [(p["data"], p["liquidez"]) for p in r.json()] == [
        ("2026-01-31", 200.0),
        ("2026-02-28", 600.0),
        ("2026-03-31", 1000.0),
        ("2026-04-30", 2150.0),
    ]


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
      saldo: `saldo_conta_em` usa `data > data_referencia`:
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

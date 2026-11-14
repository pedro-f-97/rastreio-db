"""Testes da data de um movimento de ativo.

O movimento tem a sua própria data, que pode ser diferente da da transação: o
extracto do banco costuma dar a da liquidação, dias depois da operação. Cria-se
com a data que se escolhe (`POST /api/patrimonio/movimentos`) e corrige-se
depois (`PATCH /api/patrimonio/movimentos/{id}`), sem deixar nenhuma venda com
mais unidades do que as que havia nessa data.

Os valores esperados são escritos à mão, com a conta no docstring. As datas são
fixas; a data futura é 2999-01-01, para não depender do dia de hoje.
"""

from datetime import date

import pytest

from database import Ativo, Conta, MovimentoAtivo, TipoAtivo, TipoContabilizacao, Transacao


@pytest.fixture
def etf(session):
    tipo = TipoAtivo(nome="ETF", tem_unidades=True)
    session.add(tipo)
    session.commit()
    ativo = Ativo(nome="VWCE", tipo_id=tipo.id, contabilizacao=TipoContabilizacao.investimento)
    session.add(ativo)
    session.commit()
    return ativo.id


def _movimento(client, ativo_id, tipo, dia, quantidade, valor_total, **campos):
    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo_id,
            "tipo_movimento": tipo,
            "data": dia,
            "quantidade": quantidade,
            "valor_total": valor_total,
        }
        | campos,
    )
    assert r.status_code == 200, r.json()
    return r.json()["id"]


@pytest.fixture
def compra_e_venda(client, etf):
    """Compra de 10 a 10/01/2025 e venda de 4 a 10/02/2025."""
    compra = _movimento(client, etf, "compra", "2025-01-10", 10, -1000.0)
    venda = _movimento(client, etf, "venda", "2025-02-10", 4, 520.0)
    return compra, venda


def _datas(session):
    session.expire_all()
    return {m.id: m.data for m in session.query(MovimentoAtivo).all()}


def test_movimento_com_data_diferente_da_transacao_conta_nessa_data(client, session, etf):
    """A transação da compra é de 03/01/2025 (a liquidação) e o movimento de
    30/12/2024 (a operação): 10 unidades a 100 €.

    Cálculo à mão do património no fim de dezembro de 2024:
      liquidez: referência 5 000 a 01/12/2024; a transação de −1 000 ainda não
                aconteceu -> 5 000,00
      investimentos: o movimento já conta: 10 × 100 (o preço gravado a 30/12)
                     -> 1 000,00
      total = 6 000,00
    """
    conta = Conta(nome="Ordem", saldo_referencia=5000.0, data_referencia=date(2024, 12, 1))
    session.add(conta)
    session.commit()
    transacao = Transacao(
        data=date(2025, 1, 3), descricao="Compra VWCE", valor=-1000.0, conta_id=conta.id
    )
    session.add(transacao)
    session.commit()

    _movimento(
        client,
        etf,
        "compra",
        "2024-12-30",
        10,
        -1000.0,
        transacao_id=transacao.id,
        preco_unitario=100.0,
    )

    assert list(_datas(session).values()) == [date(2024, 12, 30)]
    pontos = client.get(
        "/api/patrimonio/evolucao",
        params={"data_inicio": "2024-12-01", "data_fim": "2024-12-31"},
    ).json()
    assert [(p["data"], p["liquidez"], p["investimentos"], p["total"]) for p in pontos] == [
        ("2024-12-31", 5000.0, 1000.0, 6000.0)
    ]


def test_corrigir_a_data_de_uma_compra(client, session, etf, compra_e_venda):
    """A compra passa de 10/01 para 05/01/2025: continua antes da venda, por isso
    é aceite (200), e ficam as mesmas 10 − 4 = 6 unidades."""
    compra, venda = compra_e_venda

    r = client.patch(f"/api/patrimonio/movimentos/{compra}", json={"data": "2025-01-05"})

    assert r.status_code == 200
    assert r.json()["data"] == "2025-01-05"
    assert _datas(session) == {compra: date(2025, 1, 5), venda: date(2025, 2, 10)}
    assert client.get(f"/api/patrimonio/ativos/{etf}/resumo").json()["quantidade"] == 6


def test_compra_para_depois_da_venda_que_a_consome_e_recusada(client, session, etf, compra_e_venda):
    """A compra a 01/03/2025, depois da venda de 10/02: a 10/02 não havia
    unidades para vender 4. 422, e as datas ficam como estavam."""
    compra, venda = compra_e_venda

    r = client.patch(f"/api/patrimonio/movimentos/{compra}", json={"data": "2025-03-01"})

    assert r.status_code == 422
    assert r.json() == {
        "detail": "A venda de 10/02/2025 (4 unidades) excede as 0 unidades em carteira nessa data."
    }
    assert _datas(session) == {compra: date(2025, 1, 10), venda: date(2025, 2, 10)}


def test_venda_para_antes_da_compra_que_consome_e_recusada(client, session, etf, compra_e_venda):
    """A venda a 01/01/2025, antes da compra de 10/01: nesse dia não havia
    unidades. 422, e as datas ficam como estavam."""
    compra, venda = compra_e_venda

    r = client.patch(f"/api/patrimonio/movimentos/{venda}", json={"data": "2025-01-01"})

    assert r.status_code == 422
    assert _datas(session) == {compra: date(2025, 1, 10), venda: date(2025, 2, 10)}


def test_data_futura_e_recusada(client, session, etf, compra_e_venda):
    compra, venda = compra_e_venda

    r = client.patch(f"/api/patrimonio/movimentos/{compra}", json={"data": "2999-01-01"})

    assert r.status_code == 422
    assert r.json() == {"detail": "A data do movimento não pode ser futura."}
    assert _datas(session)[compra] == date(2025, 1, 10)


def test_so_a_data_se_muda(client, session, etf, compra_e_venda):
    """Uma quantidade enviada com a data dá 422, em vez de ser ignorada."""
    compra, _venda = compra_e_venda

    r = client.patch(
        f"/api/patrimonio/movimentos/{compra}", json={"data": "2025-01-05", "quantidade": 99}
    )

    assert r.status_code == 422
    assert _datas(session)[compra] == date(2025, 1, 10)


def test_movimento_inexistente_da_404(client, session):
    r = client.patch("/api/patrimonio/movimentos/9999", json={"data": "2025-01-05"})

    assert r.status_code == 404
    assert r.json() == {"detail": "Movimento não encontrado."}

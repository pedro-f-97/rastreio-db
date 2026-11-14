"""Testes de `POST /api/patrimonio/compras-antigas`.

Uma compra antiga é uma compra de antes dos extractos: um movimento de compra
sem transação. Entra no FIFO e no valor do ativo como as outras, mas não mexe
no saldo das contas, que se faz das transações. O endpoint só cria compras: não
tem tipo de movimento, e recusa campos a mais.

Os valores esperados são escritos à mão, com a conta no docstring. As datas são
fixas; a data futura é 2999-01-01, para não depender do dia de hoje.
"""

from datetime import date

import pytest

from database import (
    Ativo,
    Conta,
    MovimentoAtivo,
    TipoAtivo,
    TipoContabilizacao,
    TipoMovimento,
)

URL = "/api/patrimonio/compras-antigas"


@pytest.fixture
def etf(session):
    """Um ETF (com unidades), sem movimentos."""
    tipo = TipoAtivo(nome="ETF", tem_unidades=True)
    session.add(tipo)
    session.commit()
    ativo = Ativo(nome="VWCE", tipo_id=tipo.id, contabilizacao=TipoContabilizacao.investimento)
    session.add(ativo)
    session.commit()
    return ativo.id


@pytest.fixture
def casa(session):
    """Um imóvel (sem unidades), sem movimentos."""
    tipo = TipoAtivo(nome="Imóvel", tem_unidades=False)
    session.add(tipo)
    session.commit()
    ativo = Ativo(nome="Casa", tipo_id=tipo.id, contabilizacao=TipoContabilizacao.patrimonio)
    session.add(ativo)
    session.commit()
    return ativo.id


def _compra(ativo_id, **campos):
    return {
        "ativo_id": ativo_id,
        "data": "2021-03-10",
        "quantidade": 10,
        "preco_unitario": 100.0,
        "comissao": 1.0,
        "valor_total": -1001.0,
    } | campos


def test_compra_antiga_entra_no_ativo_sem_mexer_no_saldo(client, session, etf):
    """10 unidades a 10/03/2021 por 1 000 € mais 1 € de comissão
    (`valor_total` −1 001, como a janela «Tratar» grava as compras).

    Cálculo à mão:
      resumo: quantidade 10, custo_total −1 001,00 (o custo, com a comissão)
      movimento: compra, sem transação
      saldo da conta (referência 2 000 € a 01/01/2021, sem transações): fica
      2 000,00 antes e depois
    """
    conta = Conta(nome="Ordem", saldo_referencia=2000.0, data_referencia=date(2021, 1, 1))
    session.add(conta)
    session.commit()
    saldo_antes = client.get(f"/api/contas/{conta.id}/saldo").json()["saldo_atual"]

    r = client.post(URL, json=_compra(etf))

    assert r.status_code == 200
    assert (r.json()["tipo_movimento"], r.json()["transacao_id"]) == ("compra", None)
    resumo = client.get(f"/api/patrimonio/ativos/{etf}/resumo").json()
    assert (resumo["quantidade"], resumo["custo_total"]) == (10, -1001.0)
    assert saldo_antes == 2000.0
    assert client.get(f"/api/contas/{conta.id}/saldo").json()["saldo_atual"] == 2000.0


def test_venda_recusada_por_falta_de_unidades_passa_depois_da_compra_antiga(client, session, etf):
    """Uma venda de 4 unidades a 01/06/2025, sem nada em carteira, é recusada
    (422). Com a compra antiga de 10 a 10/03/2021, a mesma venda passa (200), e
    ficam 10 − 4 = 6 unidades."""
    venda = {
        "ativo_id": etf,
        "tipo_movimento": "venda",
        "data": "2025-06-01",
        "quantidade": 4,
        "preco_unitario": 130.0,
        "valor_total": 520.0,
    }
    assert client.post("/api/patrimonio/movimentos", json=venda).status_code == 422

    assert client.post(URL, json=_compra(etf)).status_code == 200
    r = client.post("/api/patrimonio/movimentos", json=venda)

    assert r.status_code == 200
    assert client.get(f"/api/patrimonio/ativos/{etf}/resumo").json()["quantidade"] == 6


@pytest.mark.parametrize(
    ("campos", "detalhe"),
    [
        ({"data": "2999-01-01"}, "A data da compra não pode ser futura."),
        ({"quantidade": 0}, "A quantidade tem de ser maior do que zero."),
        ({"quantidade": -2}, "A quantidade tem de ser maior do que zero."),
        ({"quantidade": None}, "A quantidade tem de ser maior do que zero."),
        ({"valor_total": 0}, "O total da compra não pode ser zero."),
    ],
)
def test_compra_antiga_invalida_e_recusada(client, session, etf, campos, detalhe):
    """Data futura, quantidade zero, negativa ou em falta (num ativo com
    unidades), ou total zero: 422 com a mensagem, e nada é gravado."""
    r = client.post(URL, json=_compra(etf, **campos))

    assert r.status_code == 422
    assert r.json() == {"detail": detalhe}
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 0


def test_campos_a_mais_sao_recusados(client, session, etf):
    """Um `tipo_movimento` (venda) ou um `transacao_id` enviados aqui dão 422:
    o endpoint só cria compras sem transação, e não os ignora em silêncio."""
    for extra in ({"tipo_movimento": "venda"}, {"transacao_id": 1}):
        assert client.post(URL, json=_compra(etf, **extra)).status_code == 422
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 0


def test_compra_antiga_de_um_bem_sem_unidades(client, session, casa):
    """Uma casa comprada a 01/07/2015 por 150 000 €, sem quantidade.

    Cálculo à mão: sem unidades, o custo acumula: custo_total −150 000,00, e
    sem avaliação registada o valor é o custo, 150 000,00.
    """
    r = client.post(
        URL,
        json={"ativo_id": casa, "data": "2015-07-01", "valor_total": -150000.0, "comissao": None},
    )

    assert r.status_code == 200
    resumo = client.get(f"/api/patrimonio/ativos/{casa}/resumo").json()
    assert (resumo["custo_total"], resumo["valor_atual"]) == (-150000.0, 150000.0)


def test_apagar_a_compra_antiga_de_que_uma_venda_precisa_e_recusado(client, session, etf):
    """Compra antiga de 10 e venda de 4: apagar a compra deixava a venda sem
    unidades. 422, e os dois movimentos ficam."""
    compra = client.post(URL, json=_compra(etf)).json()
    client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": etf,
            "tipo_movimento": "venda",
            "data": "2025-06-01",
            "quantidade": 4,
            "valor_total": 520.0,
        },
    )

    r = client.delete(f"/api/patrimonio/movimentos/{compra['id']}")

    assert r.status_code == 422
    session.expire_all()
    tipos = [m.tipo_movimento for m in session.query(MovimentoAtivo).all()]
    assert len(tipos) == 2
    assert set(tipos) == {TipoMovimento.compra, TipoMovimento.venda}


def test_ativo_inexistente_da_404(client, session):
    r = client.post(URL, json=_compra(9999))

    assert r.status_code == 404
    assert r.json() == {"detail": "Ativo não encontrado."}

"""
Testes para GET /api/patrimonio/ativos/{id}/resumo.

Cobrem o bug B2 original (venda não reduzia o custo base nem registava o
encaixe — mais/menos-valia ficava errada e com o sinal trocado assim que
havia uma venda) e casos adicionais do ramo FIFO e do ramo sem unidades
(bens como casas/carros).
"""
from datetime import date

from database import Ativo, MovimentoAtivo, PrecoAtivo, TipoAtivo


def _criar_tipo(db_session, nome: str, tem_unidades: bool) -> TipoAtivo:
    tipo = TipoAtivo(nome=nome, tem_unidades=tem_unidades)
    db_session.add(tipo)
    db_session.commit()
    db_session.refresh(tipo)
    return tipo


def _criar_ativo(db_session, tipo: TipoAtivo, nome: str, contabilizacao: str) -> Ativo:
    ativo = Ativo(nome=nome, simbolo=nome, tipo_id=tipo.id, contabilizacao=contabilizacao)
    db_session.add(ativo)
    db_session.commit()
    db_session.refresh(ativo)
    return ativo


def test_venda_parcial_calcula_realizado_e_latente_corretamente(client, db_session):
    """Compra 10@100 (-1000), venda 5@150 (+750), cotação atual 150.

    Antes do fix: mais_menos_valia = -250 (custo_total nunca reduzido).
    Correto: +500 (250 realizados na venda + 250 de valorização latente).
    """
    tipo = _criar_tipo(db_session, "ETF", tem_unidades=True)
    ativo = _criar_ativo(db_session, tipo, "X1", "investimento")

    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="compra", data=date(2024, 1, 1),
        quantidade=10, valor_total=-1000, preco_unitario=100,
    ))
    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="venda", data=date(2024, 6, 1),
        quantidade=5, valor_total=750,
    ))
    db_session.add(PrecoAtivo(ativo_id=ativo.id, data=date(2024, 12, 1), preco=150))
    db_session.commit()

    r = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo")
    assert r.status_code == 200
    corpo = r.json()

    assert corpo["quantidade"] == 5.0
    assert corpo["realizado"] == 250.0
    assert corpo["latente"] == 250.0
    assert corpo["mais_menos_valia"] == 500.0


def test_posicao_totalmente_liquidada_nao_conta_valor_de_mercado(client, db_session):
    """Compra 10@100 (-1000), venda 10@120 (+1200): posição a zero.

    Antes do fix: valor_atual usava o preço unitário mesmo com quantidade 0,
    e mais_menos_valia dava -850. Correto: valor_atual=0, ganho=+200.
    """
    tipo = _criar_tipo(db_session, "ETF", tem_unidades=True)
    ativo = _criar_ativo(db_session, tipo, "X2", "investimento")

    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="compra", data=date(2024, 1, 1),
        quantidade=10, valor_total=-1000, preco_unitario=100,
    ))
    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="venda", data=date(2024, 6, 1),
        quantidade=10, valor_total=1200,
    ))
    db_session.add(PrecoAtivo(ativo_id=ativo.id, data=date(2024, 12, 1), preco=150))
    db_session.commit()

    r = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo")
    corpo = r.json()

    assert corpo["quantidade"] == 0
    assert corpo["valor_atual"] == 0.0
    assert corpo["realizado"] == 200.0
    assert corpo["mais_menos_valia"] == 200.0


def test_venda_maior_que_a_posicao_nao_rebenta_nem_fica_negativa(client, db_session):
    """Venda de 10 unidades quando só há registo de compra de 5 (erro de
    dados). Não deve rebentar nem deixar quantidade negativa; o encaixe é
    pró-rateado às unidades que realmente existiam.

    NOTA: isto não avisa o utilizador de que os dados não batem certo — é
    um comportamento aceite, não necessariamente o desejado a prazo.
    """
    tipo = _criar_tipo(db_session, "ETF", tem_unidades=True)
    ativo = _criar_ativo(db_session, tipo, "X3", "investimento")

    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="compra", data=date(2024, 1, 1),
        quantidade=5, valor_total=-500, preco_unitario=100,
    ))
    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="venda", data=date(2024, 6, 1),
        quantidade=10, valor_total=1500,
    ))
    db_session.commit()

    r = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo")
    assert r.status_code == 200
    corpo = r.json()

    assert corpo["quantidade"] == 0
    assert corpo["realizado"] == 250.0  # pró-rateado: 1500 * (5/10) - 500


def test_bem_sem_unidades_detido_soma_custo_e_valorizacao(client, db_session):
    """Casa comprada por 200000, ainda não vendida, preço de mercado 250000."""
    tipo = _criar_tipo(db_session, "Imovel", tem_unidades=False)
    ativo = _criar_ativo(db_session, tipo, "Casa", "patrimonio")

    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="compra", data=date(2020, 1, 1),
        valor_total=-200000,
    ))
    db_session.add(PrecoAtivo(ativo_id=ativo.id, data=date(2024, 1, 1), preco=250000))
    db_session.commit()

    r = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo")
    corpo = r.json()

    assert corpo["valor_atual"] == 250000.0
    assert corpo["latente"] == 50000.0
    assert corpo["mais_menos_valia"] == 50000.0


def test_bem_sem_unidades_vendido_ignora_preco_de_mercado_posterior(client, db_session):
    """Carro comprado por 20000, vendido por 12000 (perda). Um preço de
    mercado registado DEPOIS da venda não deve contar para valor_atual —
    o bem já não é detido.
    """
    tipo = _criar_tipo(db_session, "Veiculo", tem_unidades=False)
    ativo = _criar_ativo(db_session, tipo, "Carro", "patrimonio")

    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="compra", data=date(2020, 1, 1),
        valor_total=-20000,
    ))
    db_session.add(MovimentoAtivo(
        ativo_id=ativo.id, tipo_movimento="venda", data=date(2023, 1, 1),
        valor_total=12000,
    ))
    # Preço "de mercado" registado depois da venda — não se aplica.
    db_session.add(PrecoAtivo(ativo_id=ativo.id, data=date(2024, 1, 1), preco=99999))
    db_session.commit()

    r = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo")
    corpo = r.json()

    assert corpo["valor_atual"] == 0.0
    assert corpo["realizado"] == -8000.0
    assert corpo["mais_menos_valia"] == -8000.0

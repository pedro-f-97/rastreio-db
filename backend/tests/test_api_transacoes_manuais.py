"""Testes das transacções criadas à mão e do saldo escrito à mão.

* `POST /api/transacoes/` cria uma transacção `manual`, sem saldo nem
  importação; se não se escolher categoria nem subcategoria, aplica as regras.
* `DELETE /api/transacoes/{id}` só apaga as manuais, e não as que estão ligadas
  a um movimento de ativo.
* `PUT /api/transacoes/{id}` aceita `saldo` (omitido mantém, null apaga) só nas
  contas sem nenhum perfil de importação com saldo.
* A listagem diz, por linha, se é `manual` e se o saldo é editável.

Os valores esperados são escritos à mão. As datas são fixas. Como em
`test_api_transacoes.py`, a sessão é partilhada com o `client`, por isso cada
leitura depois de um pedido começa por `session.expire_all()`.
"""

from datetime import date

import pytest

from database import (
    Ativo,
    Categoria,
    Conta,
    ModoValor,
    MovimentoAtivo,
    PerfilImportacao,
    RegraCategorizacao,
    Subcategoria,
    TipoAtivo,
    TipoCategoria,
    TipoContabilizacao,
    TipoFicheiro,
    TipoMovimento,
    Transacao,
)

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def semear_conta(session, nome="Ordem"):
    conta = Conta(nome=nome, saldo_referencia=0.0, data_referencia=date(2026, 1, 1))
    session.add(conta)
    session.commit()
    return conta


def semear_categorias(session):
    """Casa (despesa) com Supermercado, e Receita com Salário."""
    casa = Categoria(nome="Casa", tipo=TipoCategoria.despesa)
    receita = Categoria(nome="Receita", tipo=TipoCategoria.receita)
    session.add_all([casa, receita])
    session.commit()
    supermercado = Subcategoria(nome="Supermercado", categoria_id=casa.id)
    salario = Subcategoria(nome="Salário", categoria_id=receita.id)
    session.add_all([supermercado, salario])
    session.commit()
    return casa, supermercado, receita, salario


def semear_perfil(session, conta, tem_saldo):
    perfil = PerfilImportacao(
        nome=f"Perfil {conta.nome} {tem_saldo}",
        tipo_ficheiro=TipoFicheiro.csv,
        linha_inicio_dados=2,
        coluna_data=0,
        formato_data="%d/%m/%Y",
        coluna_descricao=1,
        modo_valor=ModoValor.coluna_unica,
        coluna_valor=2,
        separador_decimal=",",
        tem_saldo=tem_saldo,
        coluna_saldo=3 if tem_saldo else None,
        conta_id=conta.id,
    )
    session.add(perfil)
    session.commit()
    return perfil


def semear_transacao(session, conta, manual=False, saldo=None):
    t = Transacao(
        data=date(2026, 3, 10),
        descricao="Pingo Doce",
        valor=-50.0,
        saldo=saldo,
        conta_id=conta.id,
        manual=manual,
    )
    session.add(t)
    session.commit()
    return t


def nova(conta, **campos):
    corpo = {
        "conta_id": conta.id,
        "data": "2025-06-11",
        "descricao": "Transferência em falta",
        "valor": -10.0,
    }
    corpo.update(campos)
    return corpo


# ---------------------------------------------------------------------------
# POST /api/transacoes/
# ---------------------------------------------------------------------------


def test_criar_com_categoria_fica_manual(client, session):
    """Os campos enviados ficam como vieram; `manual` verdadeiro, sem saldo nem
    importação."""
    conta = semear_conta(session)
    casa, supermercado, _, _ = semear_categorias(session)

    r = client.post(
        "/api/transacoes/",
        json=nova(conta, categoria_id=casa.id, subcategoria_id=supermercado.id, notas="Correção"),
    )

    assert r.status_code == 200
    session.expire_all()
    t = session.get(Transacao, r.json()["id"])
    assert (t.data, t.descricao, t.valor, t.conta_id) == (
        date(2025, 6, 11),
        "Transferência em falta",
        -10.0,
        conta.id,
    )
    assert (t.categoria_id, t.subcategoria_id, t.notas) == (casa.id, supermercado.id, "Correção")
    assert t.manual is True
    assert t.saldo is None
    assert t.importacao_id is None


def test_criar_sem_categoria_aplica_as_regras(client, session):
    """A regra «PINGO» -> Casa/Supermercado casa com «Pingo Doce»."""
    conta = semear_conta(session)
    casa, supermercado, _, _ = semear_categorias(session)
    session.add(
        RegraCategorizacao(
            palavra_chave="PINGO", categoria_id=casa.id, subcategoria_id=supermercado.id
        )
    )
    session.commit()

    r = client.post("/api/transacoes/", json=nova(conta, descricao="Pingo Doce"))

    assert r.status_code == 200
    session.expire_all()
    t = session.get(Transacao, r.json()["id"])
    assert (t.categoria_id, t.subcategoria_id) == (casa.id, supermercado.id)


def test_criar_com_categoria_escolhida_nao_aplica_as_regras(client, session):
    """Escolhida só a categoria Casa, a regra (que daria a subcategoria
    Supermercado) não corre: a subcategoria fica vazia."""
    conta = semear_conta(session)
    casa, supermercado, _, _ = semear_categorias(session)
    session.add(
        RegraCategorizacao(
            palavra_chave="PINGO", categoria_id=casa.id, subcategoria_id=supermercado.id
        )
    )
    session.commit()

    r = client.post(
        "/api/transacoes/", json=nova(conta, descricao="Pingo Doce", categoria_id=casa.id)
    )

    assert r.status_code == 200
    session.expire_all()
    t = session.get(Transacao, r.json()["id"])
    assert (t.categoria_id, t.subcategoria_id) == (casa.id, None)


@pytest.mark.parametrize(
    "campos, estado",
    [
        ({"conta_id": 999}, 404),
        ({"categoria_id": 999}, 400),
        ({"descricao": "   "}, 422),
    ],
)
def test_criar_invalido_nao_grava(client, session, campos, estado):
    conta = semear_conta(session)

    r = client.post("/api/transacoes/", json=nova(conta, **campos))

    assert r.status_code == estado
    assert session.query(Transacao).count() == 0


def test_criar_com_subcategoria_de_outra_categoria_da_400(client, session):
    """Salário é da Receita, não da Casa."""
    conta = semear_conta(session)
    casa, _, _, salario = semear_categorias(session)

    r = client.post(
        "/api/transacoes/", json=nova(conta, categoria_id=casa.id, subcategoria_id=salario.id)
    )

    assert r.status_code == 400
    assert session.query(Transacao).count() == 0


# ---------------------------------------------------------------------------
# DELETE /api/transacoes/{id}
# ---------------------------------------------------------------------------


def test_apagar_manual(client, session):
    conta = semear_conta(session)
    t = semear_transacao(session, conta, manual=True)

    r = client.delete(f"/api/transacoes/{t.id}")

    assert r.status_code == 204
    session.expire_all()
    assert session.query(Transacao).count() == 0


def test_apagar_importada_da_409(client, session):
    conta = semear_conta(session)
    t = semear_transacao(session, conta, manual=False)

    r = client.delete(f"/api/transacoes/{t.id}")

    assert r.status_code == 409
    session.expire_all()
    assert session.query(Transacao).count() == 1


def test_apagar_manual_ligada_a_movimento_da_409(client, session):
    conta = semear_conta(session)
    t = semear_transacao(session, conta, manual=True)
    tipo = TipoAtivo(nome="Ações", tem_unidades=True)
    session.add(tipo)
    session.commit()
    ativo = Ativo(nome="ETF", tipo_id=tipo.id, contabilizacao=TipoContabilizacao.investimento)
    session.add(ativo)
    session.commit()
    session.add(
        MovimentoAtivo(
            ativo_id=ativo.id,
            transacao_id=t.id,
            tipo_movimento=TipoMovimento.compra,
            data=date(2026, 3, 10),
            quantidade=1.0,
            preco_unitario=50.0,
            valor_total=50.0,
        )
    )
    session.commit()

    r = client.delete(f"/api/transacoes/{t.id}")

    assert r.status_code == 409
    session.expire_all()
    assert session.query(Transacao).count() == 1


def test_apagar_inexistente_da_404(client):
    assert client.delete("/api/transacoes/999").status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/transacoes/{id} com saldo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("perfil", [None, False])
def test_saldo_escreve_muda_e_apaga_sem_saldo_no_extracto(client, session, perfil):
    """Sem perfil, ou com um perfil sem saldo: escreve 950, muda para 945,
    mantém com o campo omitido, e apaga com null."""
    conta = semear_conta(session)
    if perfil is not None:
        semear_perfil(session, conta, tem_saldo=perfil)
    t = semear_transacao(session, conta)

    def saldo_depois(corpo):
        r = client.put(f"/api/transacoes/{t.id}", json=corpo)
        assert r.status_code == 200
        session.expire_all()
        return session.get(Transacao, t.id).saldo

    assert saldo_depois({"saldo": 950.0}) == 950.0
    assert saldo_depois({"saldo": 945.0}) == 945.0
    assert saldo_depois({"notas": "x"}) == 945.0
    assert saldo_depois({"saldo": None}) is None


def test_saldo_recusado_com_saldo_no_extracto(client, session):
    """Um dos perfis da conta traz o saldo: 409, e o do extracto fica."""
    conta = semear_conta(session)
    semear_perfil(session, conta, tem_saldo=False)
    semear_perfil(session, conta, tem_saldo=True)
    t = semear_transacao(session, conta, saldo=900.0)

    r = client.put(f"/api/transacoes/{t.id}", json={"saldo": 950.0})

    assert r.status_code == 409
    session.expire_all()
    assert session.get(Transacao, t.id).saldo == 900.0


def test_saldo_recusado_sem_conta(client, session):
    """Uma transacção sem conta não tem saldo a verificar: 409, com essa razão."""
    t = Transacao(data=date(2026, 3, 10), descricao="Antiga", valor=-5.0, conta_id=None)
    session.add(t)
    session.commit()

    r = client.put(f"/api/transacoes/{t.id}", json={"saldo": 950.0})

    assert r.status_code == 409
    assert "não tem conta" in r.json()["detail"]
    session.expire_all()
    assert session.get(Transacao, t.id).saldo is None


def test_saldo_de_outra_conta_com_saldo_no_extracto_nao_conta(client, session):
    """Só os perfis da própria conta contam."""
    conta = semear_conta(session)
    outra = semear_conta(session, nome="Outra")
    semear_perfil(session, outra, tem_saldo=True)
    t = semear_transacao(session, conta)

    r = client.put(f"/api/transacoes/{t.id}", json={"saldo": 950.0})

    assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/transacoes/
# ---------------------------------------------------------------------------


def test_listagem_diz_se_e_manual_e_se_o_saldo_e_editavel(client, session):
    """Ordem tem um perfil com saldo, Cartão não tem perfil. A manual é de
    Cartão, a importada de Ordem."""
    ordem = semear_conta(session)
    cartao = semear_conta(session, nome="Cartão")
    semear_perfil(session, ordem, tem_saldo=True)
    importada = semear_transacao(session, ordem)
    manual = semear_transacao(session, cartao, manual=True)

    r = client.get("/api/transacoes/")

    assert r.status_code == 200
    por_id = {i["id"]: (i["manual"], i["saldo_editavel"]) for i in r.json()["items"]}
    assert por_id == {importada.id: (False, False), manual.id: (True, True)}

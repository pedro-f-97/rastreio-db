"""Testes dos campos do relatório do IRS na API.

* `classificacao_fiscal` dos tipos de ativo (`/api/tipos-ativo`): fora do IRS
  num tipo novo, e omitida na edição fica a que já tinha;
* `pais` dos ativos (`/api/patrimonio/ativos`) e das contas (`/api/contas`):
  um código de duas letras, guardado em maiúsculas, PT por omissão;
* `juros_irs` das subcategorias (`/api/categorias`): só nas categorias de
  receita, e perde-se quando a categoria deixa de o ser;
* o primeiro uso (`/api/configuracao/inicializar`): os tipos que entram no IRS
  vêm classificados, e Receita › Juros vem marcada.

Os valores esperados são escritos à mão. Como a fixture `client` e a fixture
`session` partilham a sessão, o estado final lê-se depois de
`session.expire_all()`.
"""

from datetime import date

import pytest

from database import (
    Ativo,
    Categoria,
    ClassificacaoFiscal,
    Conta,
    Subcategoria,
    TipoAtivo,
    TipoCategoria,
    TipoContabilizacao,
)

# ---------------------------------------------------------------------------
# Classificação fiscal dos tipos de ativo
# ---------------------------------------------------------------------------


def test_criar_tipo_guarda_a_classificacao_indicada(client, session):
    """POST com `criptoativos` -> 200, e o tipo fica criptoativos."""
    r = client.post(
        "/api/tipos-ativo/",
        json={"nome": "Cripto", "tem_unidades": True, "classificacao_fiscal": "criptoativos"},
    )

    assert r.status_code == 200
    assert r.json()["classificacao_fiscal"] == "criptoativos"
    session.expire_all()
    tipo = session.query(TipoAtivo).one()
    assert tipo.classificacao_fiscal == ClassificacaoFiscal.criptoativos


def test_criar_tipo_com_classificacao_desconhecida_e_recusado(client, session):
    """POST com `valores_mobiliarios`, que já não é um valor do enum (partiu-se
    em quatro) -> 422, e nada é criado."""
    r = client.post(
        "/api/tipos-ativo/",
        json={
            "nome": "Ações",
            "tem_unidades": True,
            "classificacao_fiscal": "valores_mobiliarios",
        },
    )

    assert r.status_code == 422
    session.expire_all()
    assert session.query(TipoAtivo).count() == 0


def test_editar_tipo_sem_classificacao_mantem_a_que_tinha(client, session):
    """Um tipo de fundos, renomeado sem `classificacao_fiscal`, continua em
    fundos; com `fora`, passa a fora."""
    tipo = TipoAtivo(
        nome="ETF",
        tem_unidades=True,
        classificacao_fiscal=ClassificacaoFiscal.fundos,
    )
    session.add(tipo)
    session.commit()
    tipo_id = tipo.id

    r = client.put(f"/api/tipos-ativo/{tipo_id}", json={"nome": "ETFs", "tem_unidades": True})
    assert r.status_code == 200
    assert r.json()["classificacao_fiscal"] == "fundos"

    r = client.put(
        f"/api/tipos-ativo/{tipo_id}",
        json={"nome": "ETFs", "tem_unidades": True, "classificacao_fiscal": "fora"},
    )
    assert r.status_code == 200
    session.expire_all()
    assert session.get(TipoAtivo, tipo_id).classificacao_fiscal == ClassificacaoFiscal.fora


# ---------------------------------------------------------------------------
# País dos ativos
# ---------------------------------------------------------------------------


@pytest.fixture
def tipo_etf(session):
    tipo = TipoAtivo(nome="ETF", tem_unidades=True)
    session.add(tipo)
    session.commit()
    return tipo.id


def _criar_ativo(client, tipo_id, **campos):
    return client.post(
        "/api/patrimonio/ativos",
        json={"nome": "Vanguard", "tipo_id": tipo_id, "contabilizacao": "investimento"} | campos,
    )


def test_ativo_sem_pais_fica_pt(client, session, tipo_etf):
    r = _criar_ativo(client, tipo_etf)

    assert r.status_code == 200
    assert r.json()["pais"] == "PT"


def test_ativo_com_pais_em_minusculas_guarda_maiusculas(client, session, tipo_etf):
    """`de` -> `DE`, e um espaço à volta não conta."""
    r = _criar_ativo(client, tipo_etf, pais=" de ")

    assert r.status_code == 200
    session.expire_all()
    assert session.query(Ativo).one().pais == "DE"


@pytest.mark.parametrize("pais", ["PRT", "D", "1A", ""])
def test_ativo_com_pais_que_nao_tem_duas_letras_e_recusado(client, session, tipo_etf, pais):
    """Três letras, uma letra, um algarismo ou vazio -> 422, e nada é criado."""
    r = _criar_ativo(client, tipo_etf, pais=pais)

    assert r.status_code == 422
    session.expire_all()
    assert session.query(Ativo).count() == 0


def test_editar_ativo_muda_o_pais_e_sem_pais_mantem_o_que_tinha(client, session, tipo_etf):
    """PUT com `nl` -> NL; depois um PUT só com o nome deixa NL."""
    ativo = Ativo(nome="Vanguard", tipo_id=tipo_etf, contabilizacao=TipoContabilizacao.investimento)
    session.add(ativo)
    session.commit()
    ativo_id = ativo.id

    r = client.put(f"/api/patrimonio/ativos/{ativo_id}", json={"pais": "nl"})
    assert r.status_code == 200
    assert r.json()["pais"] == "NL"

    r = client.put(f"/api/patrimonio/ativos/{ativo_id}", json={"nome": "Vanguard All-World"})
    assert r.status_code == 200
    session.expire_all()
    assert session.get(Ativo, ativo_id).pais == "NL"


def test_ativo_sem_pais_do_emitente_fica_vazio_e_com_ele_guarda_maiusculas(
    client, session, tipo_etf
):
    """Sem `pais_emitente` -> null (vale o da corretora); com `ie` -> IE, ao
    lado de DE na corretora."""
    assert _criar_ativo(client, tipo_etf).json()["pais_emitente"] is None

    r = _criar_ativo(client, tipo_etf, nome="VWCE", pais="de", pais_emitente="ie")

    assert r.status_code == 200
    assert (r.json()["pais"], r.json()["pais_emitente"]) == ("DE", "IE")


def test_editar_o_pais_do_emitente(client, session, tipo_etf):
    """PUT com `ie` -> IE; um PUT só com o nome deixa IE; com `null` volta a
    vazio (o da corretora); com `IRL` -> 422 e fica vazio."""
    ativo = Ativo(nome="VWCE", tipo_id=tipo_etf, contabilizacao=TipoContabilizacao.investimento)
    session.add(ativo)
    session.commit()
    url = f"/api/patrimonio/ativos/{ativo.id}"
    ativo_id = ativo.id

    assert client.put(url, json={"pais_emitente": "ie"}).json()["pais_emitente"] == "IE"
    assert client.put(url, json={"nome": "Vanguard"}).json()["pais_emitente"] == "IE"
    assert client.put(url, json={"pais_emitente": None}).json()["pais_emitente"] is None
    assert client.put(url, json={"pais_emitente": "IRL"}).status_code == 422
    session.expire_all()
    assert session.get(Ativo, ativo_id).pais_emitente is None


# ---------------------------------------------------------------------------
# País das contas
# ---------------------------------------------------------------------------


def test_conta_sem_pais_fica_pt_e_com_pais_guarda_maiusculas(client, session):
    r = client.post("/api/contas/", json={"nome": "Ordem", "data_referencia": "2025-01-01"})
    assert r.status_code == 200
    assert r.json()["pais"] == "PT"

    r = client.post(
        "/api/contas/",
        json={"nome": "Trade Republic", "data_referencia": "2025-01-01", "pais": "de"},
    )
    assert r.status_code == 200
    assert r.json()["pais"] == "DE"


def test_editar_conta_com_pais_invalido_e_recusado_e_sem_pais_mantem(client, session):
    """PUT com `x1` -> 422 e o país fica DE; PUT só com o nome também deixa DE."""
    conta = Conta(
        nome="Trade Republic",
        saldo_referencia=0.0,
        data_referencia=date(2025, 1, 1),
        pais="DE",
    )
    session.add(conta)
    session.commit()
    conta_id = conta.id

    r = client.put(f"/api/contas/{conta_id}", json={"pais": "x1"})
    assert r.status_code == 422

    r = client.put(f"/api/contas/{conta_id}", json={"nome": "TR"})
    assert r.status_code == 200
    session.expire_all()
    assert session.get(Conta, conta_id).pais == "DE"


# ---------------------------------------------------------------------------
# Marca de juros das subcategorias
# ---------------------------------------------------------------------------


@pytest.fixture
def categorias(session):
    receita = Categoria(nome="Receita", tipo=TipoCategoria.receita)
    casa = Categoria(nome="Casa", tipo=TipoCategoria.despesa)
    session.add_all([receita, casa])
    session.commit()
    return {"receita": receita.id, "casa": casa.id}


def test_subcategoria_de_receita_pode_ser_de_juros(client, session, categorias):
    r = client.post(
        f"/api/categorias/{categorias['receita']}/subcategorias",
        json={"nome": "Juros", "juros_irs": True},
    )

    assert r.status_code == 200
    assert r.json()["juros_irs"] is True


def test_subcategoria_sem_marca_fica_sem_juros(client, session, categorias):
    r = client.post(
        f"/api/categorias/{categorias['receita']}/subcategorias", json={"nome": "Venda"}
    )

    assert r.status_code == 200
    assert r.json()["juros_irs"] is False


def test_subcategoria_de_despesa_marcada_de_juros_e_recusada(client, session, categorias):
    """POST numa categoria de despesa com `juros_irs` -> 400, nada é criado."""
    r = client.post(
        f"/api/categorias/{categorias['casa']}/subcategorias",
        json={"nome": "Juros", "juros_irs": True},
    )

    assert r.status_code == 400
    assert r.json() == {
        "detail": "Só as subcategorias de categorias de receita podem ser de juros."
    }
    session.expire_all()
    assert session.query(Subcategoria).count() == 0


@pytest.mark.parametrize("tipo", [TipoCategoria.investimento, TipoCategoria.transferencia])
def test_subcategoria_de_juros_fora_das_receitas_e_recusada(client, session, tipo):
    """Não são só as despesas: numa categoria de investimento ou de
    transferência, `juros_irs` também dá 400, e nada é criado."""
    cat = Categoria(nome="Outra", tipo=tipo)
    session.add(cat)
    session.commit()

    r = client.post(
        f"/api/categorias/{cat.id}/subcategorias", json={"nome": "Juros", "juros_irs": True}
    )

    assert r.status_code == 400
    session.expire_all()
    assert session.query(Subcategoria).count() == 0


def test_editar_subcategoria_de_despesa_para_juros_e_recusado(client, session, categorias):
    """PUT numa subcategoria de despesa com `juros_irs` -> 400, fica sem marca."""
    sub = Subcategoria(nome="Renda", categoria_id=categorias["casa"])
    session.add(sub)
    session.commit()
    sub_id = sub.id

    r = client.put(
        f"/api/categorias/{categorias['casa']}/subcategorias/{sub_id}",
        json={"nome": "Renda", "juros_irs": True},
    )

    assert r.status_code == 400
    session.expire_all()
    assert session.get(Subcategoria, sub_id).juros_irs is False


def test_editar_subcategoria_sem_marca_mantem_a_que_tinha(client, session, categorias):
    """Uma subcategoria de juros renomeada sem `juros_irs` continua de juros; com
    `false`, deixa de ser."""
    sub = Subcategoria(nome="Juros", categoria_id=categorias["receita"], juros_irs=True)
    session.add(sub)
    session.commit()
    sub_id = sub.id
    url = f"/api/categorias/{categorias['receita']}/subcategorias/{sub_id}"

    r = client.put(url, json={"nome": "Juros da conta"})
    assert r.status_code == 200
    assert r.json()["juros_irs"] is True

    r = client.put(url, json={"nome": "Juros da conta", "juros_irs": False})
    assert r.status_code == 200
    session.expire_all()
    assert session.get(Subcategoria, sub_id).juros_irs is False


def test_categoria_que_deixa_de_ser_receita_perde_a_marca(client, session, categorias):
    """Receita com Juros (marcada) e Venda (sem marca) passa a despesa: as duas
    ficam sem marca. Voltar a receita não a devolve."""
    juros = Subcategoria(nome="Juros", categoria_id=categorias["receita"], juros_irs=True)
    venda = Subcategoria(nome="Venda", categoria_id=categorias["receita"])
    session.add_all([juros, venda])
    session.commit()
    ids = [juros.id, venda.id]
    url = f"/api/categorias/{categorias['receita']}"

    r = client.put(url, json={"nome": "Receita", "tipo": "despesa"})
    assert r.status_code == 200
    r = client.put(url, json={"nome": "Receita", "tipo": "receita"})
    assert r.status_code == 200

    session.expire_all()
    assert [session.get(Subcategoria, i).juros_irs for i in ids] == [False, False]


# ---------------------------------------------------------------------------
# Primeiro uso
# ---------------------------------------------------------------------------


def test_primeiro_uso_classifica_os_tipos_que_entram_no_irs(client, session):
    """Os 9 tipos iniciais, com a classificação escrita à mão:
    ETF em fundos (G20), Ações em ações (G01), Obrigações em obrigações (G10),
    Crypto em criptoativos; os outros (Ouro, Certificados de Aforro, Veículo,
    Imóvel, Outro) fora."""
    r = client.post("/api/configuracao/inicializar?com_categorias=false")
    assert r.status_code == 200

    session.expire_all()
    c = ClassificacaoFiscal
    fora = c.fora
    assert {t.nome: t.classificacao_fiscal for t in session.query(TipoAtivo).all()} == {
        "ETF": c.fundos,
        "Ações": c.acoes,
        "Obrigações": c.obrigacoes,
        "Crypto": c.criptoativos,
        "Ouro": fora,
        "Certificados de Aforro": fora,
        "Veículo": fora,
        "Imóvel": fora,
        "Outro": fora,
    }


@pytest.mark.parametrize("perfil", ["completo", "minimalista"])
def test_primeiro_uso_marca_so_receita_juros(client, session, perfil):
    """Nos dois perfis, Receita › Juros vem marcada, e é a única."""
    r = client.post("/api/configuracao/inicializar", params={"perfil": perfil})
    assert r.status_code == 200

    session.expire_all()
    marcadas = (
        session.query(Categoria.nome, Subcategoria.nome)
        .join(Subcategoria, Subcategoria.categoria_id == Categoria.id)
        .filter(Subcategoria.juros_irs == True)
        .all()
    )
    assert marcadas == [("Receita", "Juros")]

"""Testes dos números do panfleto (`calcular_panfleto` e `GET /api/estatisticas/panfleto`).

* O período são os últimos 12 meses completos antes de hoje: com hoje a
  25/10/2026, de outubro de 2025 a setembro de 2026. Com menos histórico,
  começa no mês da primeira transação. Sem nenhum mês completo, não há panfleto.
* As médias dividem pelos meses do período que têm transações, como as das
  Estatísticas, mesmo que só tenham transferências.
* A despesa normal deixa de fora as subcategorias extraordinárias, somadas à
  parte no período. Transferências e transações sem categoria não contam.
* A projeção soma a poupança por mês e, com rendimento, compõe os
  investimentos todos os meses; o que se investe não muda o património.

Os valores esperados são escritos à mão, com a conta no comentário.
"""

from datetime import date

from database import (
    Ativo,
    Categoria,
    ClasseDespesa,
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
from servicos.panfleto_serv import _projecao, calcular_panfleto

# Os últimos 12 meses completos vão de outubro de 2025 a setembro de 2026
HOJE = date(2026, 10, 25)

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def semear_conta(session, data_referencia=date(2024, 12, 31)):
    conta = Conta(nome="Ordem", saldo_referencia=0.0, data_referencia=data_referencia, ativa=True)
    session.add(conta)
    session.commit()
    return conta


def semear_categoria(session, nome, tipo, subcategorias=()):
    """Cria a categoria e as subcategorias, dadas como (nome, classe)."""
    categoria = Categoria(nome=nome, tipo=tipo)
    session.add(categoria)
    session.commit()
    subs = []
    for nome_sub, classe in subcategorias:
        sub = Subcategoria(nome=nome_sub, categoria_id=categoria.id, classe_despesa=classe)
        session.add(sub)
        subs.append(sub)
    session.commit()
    return categoria, subs


def semear(session, conta, data, valor, categoria=None, sub=None):
    session.add(
        Transacao(
            data=data,
            descricao="T",
            valor=valor,
            conta_id=conta.id,
            categoria_id=categoria.id if categoria else None,
            subcategoria_id=sub.id if sub else None,
        )
    )
    session.commit()


# ---------------------------------------------------------------------------
# Período
# ---------------------------------------------------------------------------


def test_sem_transacoes_nao_ha_panfleto(session, client):
    assert calcular_panfleto(session, HOJE) is None
    assert client.get("/api/estatisticas/panfleto").status_code == 404


def test_so_o_mes_em_curso_nao_chega(session):
    conta = semear_conta(session)
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    semear(session, conta, date(2026, 10, 1), 1000.0, salario)

    assert calcular_panfleto(session, HOJE) is None


def test_periodo_sao_os_ultimos_12_meses_completos(session):
    """Contam o primeiro dia (01/10/2025) e o último (30/09/2026); ficam de
    fora o dia antes (30/09/2025) e o mês em curso (01/10/2026). Dois meses
    com transações: receita (100 + 300) / 2 = 200."""
    conta = semear_conta(session)
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    semear(session, conta, date(2025, 9, 30), 1000.0, salario)
    semear(session, conta, date(2025, 10, 1), 100.0, salario)
    semear(session, conta, date(2026, 9, 30), 300.0, salario)
    semear(session, conta, date(2026, 10, 1), 5000.0, salario)

    r = calcular_panfleto(session, HOJE)

    assert r["periodo"] == {
        "de": {"ano": 2025, "mes": 10},
        "ate": {"ano": 2026, "mes": 9},
        "meses": 2,
    }
    assert r["mes"]["receita"] == 200.0
    assert r["gerado_em"] == "2026-10-25"


def test_com_menos_historico_comeca_na_primeira_transacao(session):
    conta = semear_conta(session)
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    semear(session, conta, date(2026, 7, 15), 100.0, salario)

    r = calcular_panfleto(session, HOJE)

    assert r["periodo"] == {
        "de": {"ano": 2026, "mes": 7},
        "ate": {"ano": 2026, "mes": 9},
        "meses": 1,
    }


def test_mes_so_com_transferencias_conta_nas_medias(session):
    """Julho só tem uma transferência, mas conta como mês: receita 900 / 2 = 450."""
    conta = semear_conta(session)
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    transferencia, _ = semear_categoria(session, "Entre contas", TipoCategoria.transferencia)
    semear(session, conta, date(2026, 7, 10), -500.0, transferencia)
    semear(session, conta, date(2026, 8, 10), 900.0, salario)

    r = calcular_panfleto(session, HOJE)

    assert r["periodo"]["meses"] == 2
    assert r["mes"]["receita"] == 450.0


# ---------------------------------------------------------------------------
# O mês normal e a despesa
# ---------------------------------------------------------------------------


def test_medias_do_mes_sem_as_extraordinarias(session):
    """Agosto e setembro de 2026, dois meses.

    * receita: (1000 + 1200) / 2 = 1100;
    * essencial (Renda): (300 + 300) / 2 = 300;
    * evitável (Restaurantes): (100 + 50 − 20 de reembolso) / 2 = 130 / 2 = 65;
    * sem classe (Diversos): 40 / 2 = 20;
    * despesa normal: 300 + 65 + 20 = 385;
    * extraordinárias (Carro): 5000 no total do período, fora da despesa;
    * investido: 200 + 400 = 600 no período.

    A transferência e a transação sem categoria não contam em nada.
    """
    conta = semear_conta(session)
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    casa, (renda,) = semear_categoria(
        session, "Casa", TipoCategoria.despesa, [("Renda", ClasseDespesa.essencial)]
    )
    lazer, (restaurantes, diversos) = semear_categoria(
        session,
        "Lazer",
        TipoCategoria.despesa,
        [("Restaurantes", ClasseDespesa.evitavel), ("Diversos", None)],
    )
    pontual, (carro,) = semear_categoria(
        session, "Pontual", TipoCategoria.despesa, [("Carro", ClasseDespesa.extraordinaria)]
    )
    investir, _ = semear_categoria(session, "Investir", TipoCategoria.investimento)
    transferencia, _ = semear_categoria(session, "Entre contas", TipoCategoria.transferencia)

    semear(session, conta, date(2026, 8, 1), 1000.0, salario)
    semear(session, conta, date(2026, 8, 2), -300.0, casa, renda)
    semear(session, conta, date(2026, 8, 3), -100.0, lazer, restaurantes)
    semear(session, conta, date(2026, 8, 4), -200.0, investir)
    semear(session, conta, date(2026, 8, 5), -500.0, transferencia)
    semear(session, conta, date(2026, 9, 1), 1200.0, salario)
    semear(session, conta, date(2026, 9, 2), -300.0, casa, renda)
    semear(session, conta, date(2026, 9, 3), -50.0, lazer, restaurantes)
    semear(session, conta, date(2026, 9, 4), 20.0, lazer, restaurantes)
    semear(session, conta, date(2026, 9, 5), -40.0, lazer, diversos)
    semear(session, conta, date(2026, 9, 6), -5000.0, pontual, carro)
    semear(session, conta, date(2026, 9, 7), -400.0, investir)
    semear(session, conta, date(2026, 9, 8), -77.0)

    r = calcular_panfleto(session, HOJE)

    assert r["periodo"]["meses"] == 2
    assert r["mes"] == {
        "receita": 1100.0,
        "despesa": 385.0,
        "essencial": 300.0,
        "evitavel": 65.0,
        "sem_classe": 20.0,
        "extraordinarias": 5000.0,
    }
    assert r["patrimonio"]["investido"] == 600.0
    assert r["despesas"] == {
        "top": [
            {"categoria": "Casa", "subcategoria": "Renda", "classe": "essencial", "mensal": 300.0},
            {
                "categoria": "Lazer",
                "subcategoria": "Restaurantes",
                "classe": "evitavel",
                "mensal": 65.0,
            },
            {"categoria": "Lazer", "subcategoria": "Diversos", "classe": None, "mensal": 20.0},
        ],
        "outras": {"quantas": 0, "mensal": 0.0},
    }


def test_top_7_subcategorias_e_as_outras_somadas(session):
    """Um mês: oito subcategorias de 80 a 10 € e 45 € de Saúde sem
    subcategoria. Ficam as 7 maiores (80, 70, 60, 50, 45, 40, 30); as outras
    duas somam 20 + 10 = 30."""
    conta = semear_conta(session)
    nomes = ["A", "B", "C", "D", "E", "F", "G", "H"]
    gastos, subs = semear_categoria(
        session, "Gastos", TipoCategoria.despesa, [(n, None) for n in nomes]
    )
    saude, _ = semear_categoria(session, "Saúde", TipoCategoria.despesa)
    for sub, valor in zip(subs, [80, 70, 60, 50, 40, 30, 20, 10]):
        semear(session, conta, date(2026, 9, 1), -float(valor), gastos, sub)
    semear(session, conta, date(2026, 9, 2), -45.0, saude)

    r = calcular_panfleto(session, HOJE)

    top = [(d["categoria"], d["subcategoria"], d["mensal"]) for d in r["despesas"]["top"]]
    assert top == [
        ("Gastos", "A", 80.0),
        ("Gastos", "B", 70.0),
        ("Gastos", "C", 60.0),
        ("Gastos", "D", 50.0),
        ("Saúde", "Sem subcategoria", 45.0),
        ("Gastos", "E", 40.0),
        ("Gastos", "F", 30.0),
    ]
    assert r["despesas"]["outras"] == {"quantas": 2, "mensal": 30.0}


# ---------------------------------------------------------------------------
# Património e projeção
# ---------------------------------------------------------------------------


def test_patrimonio_no_fim_do_periodo_e_projecao_so_poupanca(session):
    """+100 € em julho, agosto e setembro: 100, 200 e 300 no fim de cada mês,
    crescimento 100 por mês, todo poupança. Os 999 € de outubro (o mês em
    curso) não entram no património de hoje.

    Sem investimentos, as três taxas dão o mesmo: 300 + 100 × meses, ou seja
    300 hoje, 300 + 2400 = 2700 a 2 anos e 300 + 12 000 = 12 300 a 10 anos.
    """
    conta = semear_conta(session, data_referencia=date(2026, 6, 30))
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    for mes in (7, 8, 9):
        semear(session, conta, date(2026, mes, 10), 100.0, salario)
    semear(session, conta, date(2026, 10, 5), 999.0, salario)

    r = calcular_panfleto(session, HOJE)

    assert r["patrimonio"] == {
        "atual": 300.0,
        "liquidez": 300.0,
        "investimentos": 0.0,
        "bens": 0.0,
        "crescimento": 100.0,
        "poupanca": 100.0,
        "valorizacao": 0.0,
        "investido": 0.0,
    }
    assert [c["taxa"] for c in r["projecao"]] == [0, 4, 7]
    for cenario in r["projecao"]:
        assert len(cenario["valores"]) == 121
        assert [cenario["valores"][m] for m in (0, 24, 120)] == [300.0, 2700.0, 12300.0]


def test_projecao_soma_so_a_poupanca_e_nao_a_valorizacao(session):
    """Um bem comprado por 1000 € a 01/07/2026, avaliado em 1000, 1100 e 1200
    no fim de julho, agosto e setembro: o património cresce 100 por mês, todo
    valorização, e a poupança é 0. A projeção parte dos 1200 de hoje e não lhes
    soma nada: 1200 a 10 anos. Se somasse o crescimento, seriam
    1200 + 100 × 120 = 13 200."""
    conta = semear_conta(session, data_referencia=date(2026, 6, 30))
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    semear(session, conta, date(2026, 7, 10), 0.0, salario)
    tipo = TipoAtivo(nome="Bens", tem_unidades=False)
    session.add(tipo)
    session.commit()
    bem = Ativo(nome="Bem", tipo_id=tipo.id, contabilizacao=TipoContabilizacao.patrimonio)
    session.add(bem)
    session.commit()
    session.add(
        MovimentoAtivo(
            ativo_id=bem.id,
            tipo_movimento=TipoMovimento.compra,
            data=date(2026, 7, 1),
            valor_total=1000.0,
        )
    )
    for dia, preco in (
        (date(2026, 7, 31), 1000.0),
        (date(2026, 8, 31), 1100.0),
        (date(2026, 9, 30), 1200.0),
    ):
        session.add(PrecoAtivo(ativo_id=bem.id, data=dia, preco=preco))
    session.commit()

    r = calcular_panfleto(session, HOJE)

    assert (r["patrimonio"]["atual"], r["patrimonio"]["bens"]) == (1200.0, 1200.0)
    assert (r["patrimonio"]["crescimento"], r["patrimonio"]["poupanca"]) == (100.0, 0.0)
    assert r["projecao"][0]["valores"][120] == 1200.0


def test_menos_de_3_meses_sem_crescimento_nem_projecao(session):
    conta = semear_conta(session, data_referencia=date(2026, 7, 31))
    salario, _ = semear_categoria(session, "Salário", TipoCategoria.receita)
    semear(session, conta, date(2026, 8, 10), 100.0, salario)
    semear(session, conta, date(2026, 9, 10), 100.0, salario)

    r = calcular_panfleto(session, HOJE)

    assert r["patrimonio"]["crescimento"] is None
    assert r["projecao"] is None


def test_projecao_compoe_os_investimentos_todos_os_meses():
    """10 000 € investidos, sem poupança nem aporte. A taxa mensal composta 12
    vezes dá a anual: a 1 ano, 1000 + 10 000 × 4 % = 1400 e 1000 + 10 000 × 7 %
    = 1700; a 2 anos, 10 000 × (1,04² − 1) = 816 e 10 000 × (1,07² − 1) = 1449."""
    cenarios = {c["taxa"]: c["valores"] for c in _projecao(1000.0, 10000.0, 0.0, 0.0)}

    assert [cenarios[0][m] for m in (12, 24)] == [1000.0, 1000.0]
    assert [cenarios[4][m] for m in (12, 24)] == [1400.0, 1816.0]
    assert [cenarios[7][m] for m in (12, 24)] == [1700.0, 2449.0]


def test_o_que_se_investe_nao_muda_o_patrimonio():
    """Sem rendimento, investir 500 € por mês só passa dinheiro da conta para
    os investimentos: o património fica em 1000."""
    cenarios = {c["taxa"]: c["valores"] for c in _projecao(1000.0, 0.0, 0.0, 500.0)}

    assert cenarios[0][120] == 1000.0


def test_o_rendimento_do_mes_conta_antes_do_aporte():
    """Sem investimentos no início, o rendimento do primeiro mês é 0: o aporte
    de 1000 € só rende a partir do segundo mês. Com 7 %, a taxa mensal é
    1,07^(1/12) − 1 = 0,5654 %, e no fim do segundo mês o património é
    100 + 1000 × 0,005654 = 105,65."""
    cenarios = {c["taxa"]: c["valores"] for c in _projecao(100.0, 0.0, 0.0, 1000.0)}

    assert cenarios[7][1] == 100.0
    assert cenarios[7][2] == 105.65

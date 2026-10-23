"""Testes de `GET /api/contas/{id}/verificacao-saldo`.

O saldo calculado ao fim de cada dia (referência mais ou menos as transacções,
como em `saldo_conta_em`) compara-se com o saldo do banco no fim desse dia. Num
dia com vários saldos, o do fim do dia é o que não é o «saldo antes» (saldo
menos valor) de nenhuma outra transacção desse dia. A referência é um ponto de
controlo com diferença 0, salvo se o banco tiver saldo nesse dia.

Os valores esperados são calculados à mão, com a conta no docstring. As datas
são fixas: nenhum teste assenta na data de hoje.
"""

from datetime import date

import pytest

from database import Conta, Transacao


def semear_conta(session, saldo_referencia, data_referencia, nome="Conta X"):
    conta = Conta(
        nome=nome,
        saldo_referencia=saldo_referencia,
        data_referencia=data_referencia,
        ativa=True,
    )
    session.add(conta)
    session.commit()
    return conta


def semear(session, conta, linhas):
    """Cada linha é (data, descrição, valor, saldo)."""
    for data, descricao, valor, saldo in linhas:
        session.add(
            Transacao(data=data, descricao=descricao, valor=valor, saldo=saldo, conta_id=conta.id)
        )
    session.commit()


def verificar(client, conta):
    r = client.get(f"/api/contas/{conta.id}/verificacao-saldo")
    assert r.status_code == 200
    return r.json()


def test_tudo_certo(client, session):
    """Referência 1000 € a 01/01/2026.

    05/01: 1000 − 20 = 980, o banco diz 980 -> 0.
    10/01: 980 + 100 = 1080, o banco diz 1080 -> 0.
    Sem intervalos; o último saldo é o de 10/01, e a última transacção também.
    """
    conta = semear_conta(session, 1000.0, date(2026, 1, 1))
    semear(
        session,
        conta,
        [
            (date(2026, 1, 5), "Café", -20.0, 980.0),
            (date(2026, 1, 10), "Ordenado", 100.0, 1080.0),
        ],
    )

    assert verificar(client, conta) == {
        "conta_id": conta.id,
        "diferenca_atual": 0.0,
        "data_ultimo_saldo": "2026-01-10",
        "intervalos": [],
        "dias_ordem_incerta": [],
        "sugerir_saldo": False,
    }


def test_uma_transacao_em_falta(client, session):
    """No banco: 05/01 −20 -> 980; 07/01 −10 -> 970 (falta na BD); 10/01 +100
    -> 1070.

    Calculado: 05/01 980 (diferença 0); 10/01 1080, menos 1070 do banco -> +10.
    Um intervalo, ]05/01, 10/01], com +10.
    """
    conta = semear_conta(session, 1000.0, date(2026, 1, 1))
    semear(
        session,
        conta,
        [
            (date(2026, 1, 5), "Café", -20.0, 980.0),
            (date(2026, 1, 10), "Ordenado", 100.0, 1070.0),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == 10.0
    assert resultado["intervalos"] == [{"de": "2026-01-05", "ate": "2026-01-10", "variacao": 10.0}]


def test_dois_erros_dao_dois_intervalos(client, session):
    """Como no ActivoBank. Referência 1000 € a 01/05/2025.

    No banco: 12/05 −5 -> 995; 13/05 −3 -> 992 (na BD está −2,90); 10/06 −1 ->
    991; 11/06 −10 -> 981 (falta na BD); 12/06 −1 -> 980.
    Calculado: 12/05 995 (0); 13/05 992,10 (+0,10); 10/06 991,10 (+0,10);
    12/06 990,10 contra 980 (+10,10).
    Intervalos: ]12/05, 13/05] +0,10 e ]10/06, 12/06] +10,10 − 0,10 = +10,00.
    """
    conta = semear_conta(session, 1000.0, date(2025, 5, 1))
    semear(
        session,
        conta,
        [
            (date(2025, 5, 12), "A", -5.0, 995.0),
            (date(2025, 5, 13), "B", -2.9, 992.0),
            (date(2025, 6, 10), "C", -1.0, 991.0),
            (date(2025, 6, 12), "D", -1.0, 980.0),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == 10.1
    assert resultado["intervalos"] == [
        {"de": "2025-05-12", "ate": "2025-05-13", "variacao": 0.1},
        {"de": "2025-06-10", "ate": "2025-06-12", "variacao": 10.0},
    ]


# O dia do exemplo do plano: começa com X, e tem café −20, supermercado −30 e
# ordenado +100, gravados do mais recente para o mais antigo, como em alguns
# extractos. Cada caso é (entrada em falta no dia anterior, saldos do banco).
@pytest.mark.parametrize(
    "em_falta, diferenca",
    [
        # Falta uma entrada de 50: o banco começa o dia com 1050 e acaba com
        # 1100; o calculado acaba com 1000 − 20 − 30 + 100 = 1050 -> −50. A
        # menor diferença daria +20 (1050 contra o café, 1030).
        (50.0, -50.0),
        # Falta uma entrada de 70: o banco acaba com 1120 e o café fica com
        # 1050, igual ao calculado. A comparação com «algum saldo do dia» dava
        # o dia como certo; o do fim do dia é 1120 -> −70.
        (70.0, -70.0),
    ],
)
def test_o_saldo_do_fim_do_dia_vem_da_ordem_do_extracto(client, session, em_falta, diferenca):
    """Referência 1000 € a 28/02/2026; a entrada em falta é de 01/03; o dia é
    02/03. Os saldos antes são 1000 + em_falta, café e supermercado; o do
    ordenado não é o saldo antes de nenhuma, por isso é o do fim do dia."""
    inicio = 1000.0 + em_falta
    conta = semear_conta(session, 1000.0, date(2026, 2, 28))
    semear(
        session,
        conta,
        [
            (date(2026, 3, 2), "Ordenado", 100.0, inicio + 50.0),
            (date(2026, 3, 2), "Supermercado", -30.0, inicio - 50.0),
            (date(2026, 3, 2), "Café", -20.0, inicio - 20.0),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == diferenca
    assert resultado["intervalos"] == [
        {"de": "2026-02-28", "ate": "2026-03-02", "variacao": diferenca}
    ]
    assert resultado["dias_ordem_incerta"] == []


def test_dia_sem_ordem_reconstruivel_fica_incerto(client, session):
    """Referência 1000 € a 28/02/2026. Em 02/03, −20 com saldo 980 e uma de 0 €
    também com 980. Saldos antes: 1000 e 980; os saldos (980, 980) são ambos um
    saldo antes, por isso não há candidata: fica o mais próximo do calculado
    (980), diferença 0, e o dia é incerto."""
    conta = semear_conta(session, 1000.0, date(2026, 2, 28))
    semear(
        session,
        conta,
        [
            (date(2026, 3, 2), "Compra", -20.0, 980.0),
            (date(2026, 3, 2), "Comissão isenta", 0.0, 980.0),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == 0.0
    assert resultado["intervalos"] == []
    assert resultado["dias_ordem_incerta"] == ["2026-03-02"]


def test_dia_incerto_usa_o_saldo_mais_proximo(client, session):
    """Referência 980 € a 28/02/2026. Em 02/03, +10 com saldo 990 e −10 com
    saldo 980. Saldos antes: 980 e 990, que são os dois saldos: sem candidata.
    O calculado é 980 + 10 − 10 = 980; o mais próximo é 980 (e não 990, o
    primeiro gravado) -> diferença 0, dia incerto."""
    conta = semear_conta(session, 980.0, date(2026, 2, 28))
    semear(
        session,
        conta,
        [
            (date(2026, 3, 2), "Devolução", 10.0, 990.0),
            (date(2026, 3, 2), "Compra", -10.0, 980.0),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == 0.0
    assert resultado["dias_ordem_incerta"] == ["2026-03-02"]


def test_saldo_escrito_num_dia_com_outras_sem_saldo(client, session):
    """Uma conta sem saldo no extracto: o saldo 945 está escrito só na última
    transacção de 05/01/2026. Referência 1000 € a 01/01: 1000 − 20 − 30 = 950,
    menos 945 -> +5. O ponto é o de 05/01, com uma só candidata."""
    conta = semear_conta(session, 1000.0, date(2026, 1, 1))
    semear(
        session,
        conta,
        [
            (date(2026, 1, 5), "A", -20.0, None),
            (date(2026, 1, 5), "B", -30.0, 945.0),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["data_ultimo_saldo"] == "2026-01-05"
    assert resultado["diferenca_atual"] == 5.0
    assert resultado["intervalos"] == [{"de": "2026-01-01", "ate": "2026-01-05", "variacao": 5.0}]
    assert resultado["dias_ordem_incerta"] == []


def test_saldos_antes_da_referencia(client, session):
    """Referência 1000 € a 30/06/2026 (calcula-se para trás).

    20/06 −10: calculado 1000 (nada depois até 30/06), o banco diz 1000 -> 0.
    10/06 −10: calculado 1000 − (−10) = 1010, o banco diz 1015 -> −5 (falta uma
    saída de 5 entre 10/06 e 20/06).
    Pontos: 10/06 −5, 20/06 0, referência 30/06 0. Intervalos: até 10/06 −5,
    ]10/06, 20/06] +5. A diferença actual é a da referência, 0.
    """
    conta = semear_conta(session, 1000.0, date(2026, 6, 30))
    semear(
        session,
        conta,
        [
            (date(2026, 6, 10), "A", -10.0, 1015.0),
            (date(2026, 6, 20), "B", -10.0, 1000.0),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == 0.0
    assert resultado["data_ultimo_saldo"] == "2026-06-30"
    assert resultado["intervalos"] == [
        {"de": None, "ate": "2026-06-10", "variacao": -5.0},
        {"de": "2026-06-10", "ate": "2026-06-20", "variacao": 5.0},
    ]


def test_o_saldo_do_banco_no_dia_da_referencia_conta(client, session):
    """Referência 1000 € a 01/01/2026, e uma transacção desse dia com saldo 990.

    O calculado ao fim de 01/01 é a referência, 1000; o banco diz 990 -> +10. O
    ponto do banco substitui o da referência: um intervalo até 01/01, +10.
    """
    conta = semear_conta(session, 1000.0, date(2026, 1, 1))
    semear(session, conta, [(date(2026, 1, 1), "A", -20.0, 990.0)])

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == 10.0
    assert resultado["intervalos"] == [{"de": None, "ate": "2026-01-01", "variacao": 10.0}]


def test_conta_sem_saldos_sugere_escrever_um(client, session):
    """Sem saldos, o único ponto é a referência (01/01/2026), diferença 0. A
    última transacção é de 15/02: 45 dias depois, mais de 31 -> sugere."""
    conta = semear_conta(session, 1000.0, date(2026, 1, 1))
    semear(
        session,
        conta,
        [
            (date(2026, 1, 10), "A", -20.0, None),
            (date(2026, 2, 15), "B", -5.0, None),
        ],
    )

    assert verificar(client, conta) == {
        "conta_id": conta.id,
        "diferenca_atual": 0.0,
        "data_ultimo_saldo": "2026-01-01",
        "intervalos": [],
        "dias_ordem_incerta": [],
        "sugerir_saldo": True,
    }


@pytest.mark.parametrize(
    "ultima, sugerir",
    [
        # 10/02 − 10/01 = 31 dias: não é mais de 31
        (date(2026, 2, 10), False),
        # 11/02 − 10/01 = 32 dias
        (date(2026, 2, 11), True),
    ],
)
def test_saldo_antigo_conta_da_ultima_transacao(client, session, ultima, sugerir):
    """Último saldo a 10/01/2026; a última transacção, sem saldo, em `ultima`."""
    conta = semear_conta(session, 1000.0, date(2026, 1, 1))
    semear(
        session,
        conta,
        [
            (date(2026, 1, 10), "A", -20.0, 980.0),
            (ultima, "B", -5.0, None),
        ],
    )

    resultado = verificar(client, conta)

    assert resultado["data_ultimo_saldo"] == "2026-01-10"
    assert resultado["sugerir_saldo"] is sugerir


def test_so_conta_a_conta_pedida(client, session):
    """Outra conta tem um saldo errado no mesmo dia; a pedida bate certo:
    1000 − 20 = 980."""
    conta = semear_conta(session, 1000.0, date(2026, 1, 1))
    outra = semear_conta(session, 1000.0, date(2026, 1, 1), nome="Outra")
    semear(session, conta, [(date(2026, 1, 5), "A", -20.0, 980.0)])
    semear(session, outra, [(date(2026, 1, 5), "A", -20.0, 900.0)])

    resultado = verificar(client, conta)

    assert resultado["diferenca_atual"] == 0.0
    assert resultado["intervalos"] == []


def test_conta_inexistente_da_404(client):
    r = client.get("/api/contas/999/verificacao-saldo")

    assert r.status_code == 404

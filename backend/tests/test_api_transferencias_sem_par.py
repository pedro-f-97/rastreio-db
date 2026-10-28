"""Testes de `GET /api/transacoes/transferencias-sem-par`.

Uma transferência tem par quando há outra transferência noutra conta, com o
valor simétrico ao cêntimo e a data a 7 dias, no máximo. Cada uma só entra num
par, e os pares formam-se do mais próximo no tempo para o mais afastado, em
empate pelo mais antigo. Só contam as transacções de categorias do tipo
transferência.

Os valores esperados são calculados à mão, com a conta no docstring. As datas
são fixas: nenhum teste assenta na data de hoje.
"""

from datetime import date

import pytest

from database import Categoria, Conta, TipoCategoria, Transacao


@pytest.fixture
def base(session):
    """Três contas e uma categoria de cada tipo usado nos testes."""
    contas = {
        nome: Conta(nome=nome, saldo_referencia=0.0, data_referencia=date(2025, 1, 1))
        for nome in ("A", "B", "C")
    }
    categorias = {
        "transferencia": Categoria(nome="Transferência", tipo=TipoCategoria.transferencia),
        "despesa": Categoria(nome="Casa", tipo=TipoCategoria.despesa),
        "receita": Categoria(nome="Salário", tipo=TipoCategoria.receita),
    }
    session.add_all([*contas.values(), *categorias.values()])
    session.commit()

    def transacao(conta, dia, valor, tipo="transferencia", descricao="Transferência"):
        t = Transacao(
            data=dia,
            descricao=descricao,
            valor=valor,
            conta_id=contas[conta].id if conta else None,
            categoria_id=categorias[tipo].id if tipo else None,
        )
        session.add(t)
        session.commit()
        return t

    return transacao


def _sem_par(client):
    r = client.get("/api/transacoes/transferencias-sem-par")
    assert r.status_code == 200
    return r.json()


def _ids(resposta):
    return [t["id"] for t in resposta["transacoes"]]


def test_par_no_mesmo_dia_em_contas_diferentes(client, base):
    """A −100 e B +100 no mesmo dia: contas diferentes, simétricos, 0 dias.

    Ficam emparelhadas: nenhuma sem par, somas a zero.
    """
    base("A", date(2025, 3, 1), -100.0)
    base("B", date(2025, 3, 1), 100.0)

    assert _sem_par(client) == {"dias_par": 7, "entradas": 0.0, "saidas": 0.0, "transacoes": []}


def test_par_a_tres_dias_com_o_fim_do_mes_pelo_meio(client, base):
    """A −250 a 30/01 e B +250 a 02/02: 30/01 -> 02/02 são 3 dias (≤ 7).

    Ficam emparelhadas: a mudança de mês não conta.
    """
    base("A", date(2025, 1, 30), -250.0)
    base("B", date(2025, 2, 2), 250.0)

    assert _ids(_sem_par(client)) == []


def test_par_exactamente_a_sete_dias_ainda_emparelha(client, base):
    """A −80 a 01/03 e B +80 a 08/03: 7 dias, o limite, ainda emparelha."""
    base("A", date(2025, 3, 1), -80.0)
    base("B", date(2025, 3, 8), 80.0)

    assert _ids(_sem_par(client)) == []


def test_par_a_oito_dias_ja_fica_sem_par(client, base):
    """A −80 a 01/03 e B +80 a 09/03: 8 dias, acima do limite.

    As duas ficam sem par, por data:
      entradas = 80,00
      saidas   = -80,00
    """
    saida = base("A", date(2025, 3, 1), -80.0)
    entrada = base("B", date(2025, 3, 9), 80.0)

    r = _sem_par(client)

    assert r == {
        "dias_par": 7,
        "entradas": 80.0,
        "saidas": -80.0,
        "transacoes": [
            {
                "id": saida.id,
                "data": "2025-03-01",
                "descricao": "Transferência",
                "valor": -80.0,
                "conta_nome": "A",
            },
            {
                "id": entrada.id,
                "data": "2025-03-09",
                "descricao": "Transferência",
                "valor": 80.0,
                "conta_nome": "B",
            },
        ],
    }


def test_duas_transferencias_na_mesma_conta_nao_formam_par(client, base):
    """A −50 e A +50 no mesmo dia: a mesma conta, por isso sem par.

    entradas = 50,00, saidas = -50,00
    """
    saida = base("A", date(2025, 3, 1), -50.0)
    entrada = base("A", date(2025, 3, 1), 50.0)

    r = _sem_par(client)

    assert _ids(r) == [saida.id, entrada.id]
    assert (r["entradas"], r["saidas"]) == (50.0, -50.0)


def test_valores_que_diferem_um_centimo_nao_formam_par(client, base):
    """A −100,00 e B +99,99: |−100,00| ≠ |99,99|, por isso sem par.

    entradas = 99,99, saidas = -100,00
    """
    saida = base("A", date(2025, 3, 1), -100.0)
    entrada = base("B", date(2025, 3, 1), 99.99)

    r = _sem_par(client)

    assert _ids(r) == [saida.id, entrada.id]
    assert (r["entradas"], r["saidas"]) == (99.99, -100.0)


def test_duas_saidas_para_uma_entrada_deixam_a_mais_afastada_sem_par(client, base):
    """A −100 a 01/03, A −100 a 02/03 e B +100 a 03/03.

    Pares possíveis (as duas saídas estão na mesma conta, não emparelham):
      01/03 com 03/03 -> 2 dias
      02/03 com 03/03 -> 1 dia   <- o mais próximo, forma-se primeiro
    Fica sem par a saída de 01/03:
      entradas = 0, saidas = -100,00
    """
    afastada = base("A", date(2025, 3, 1), -100.0)
    base("A", date(2025, 3, 2), -100.0)
    base("B", date(2025, 3, 3), 100.0)

    r = _sem_par(client)

    assert _ids(r) == [afastada.id]
    assert (r["entradas"], r["saidas"]) == (0.0, -100.0)


def test_escolhe_o_par_mais_proximo_entre_dois_candidatos(client, base):
    """A −60 a 10/03; B +60 a 05/03 e C +60 a 12/03.

    Pares possíveis (as duas entradas têm o mesmo sinal, não emparelham):
      A com B -> 5 dias
      A com C -> 2 dias   <- o mais próximo
    Fica sem par a entrada de B:
      entradas = 60,00, saidas = 0
    """
    base("A", date(2025, 3, 10), -60.0)
    afastada = base("B", date(2025, 3, 5), 60.0)
    base("C", date(2025, 3, 12), 60.0)

    r = _sem_par(client)

    assert _ids(r) == [afastada.id]
    assert (r["entradas"], r["saidas"]) == (60.0, 0.0)


def test_em_empate_de_distancia_emparelha_o_mais_antigo(client, base):
    """A −100 a 05/03; B +100 a 03/03 e C +100 a 07/03.

    Pares possíveis, os dois a 2 dias:
      B (03/03) com A (05/03) -> começa a 03/03   <- o mais antigo
      A (05/03) com C (07/03) -> começa a 05/03
    Fica sem par a entrada de C:
      entradas = 100,00, saidas = 0
    """
    base("A", date(2025, 3, 5), -100.0)
    base("B", date(2025, 3, 3), 100.0)
    recente = base("C", date(2025, 3, 7), 100.0)

    r = _sem_par(client)

    assert _ids(r) == [recente.id]
    assert (r["entradas"], r["saidas"]) == (100.0, 0.0)


def test_so_contam_as_transferencias(client, base):
    """Uma transferência A −30 a 01/03, e no mesmo dia, na conta B, +30 numa
    despesa (reembolso), +30 numa receita e +30 sem categoria.

    Nenhuma das três entradas é transferência: não emparelham, e também não
    aparecem na lista. Fica só a transferência:
      entradas = 0, saidas = -30,00
    """
    transferencia = base("A", date(2025, 3, 1), -30.0)
    base("B", date(2025, 3, 1), 30.0, tipo="despesa")
    base("B", date(2025, 3, 1), 30.0, tipo="receita")
    base("B", date(2025, 3, 1), 30.0, tipo=None)

    r = _sem_par(client)

    assert _ids(r) == [transferencia.id]
    assert (r["entradas"], r["saidas"]) == (0.0, -30.0)


def test_centimos_que_o_float_nao_guarda_exactos_nao_se_confundem(client, base):
    """A −0,29 e B +0,28: diferem 1 cêntimo, por isso sem par.

    Em float, 0,29 × 100 = 28,999999999999996 e 0,28 × 100 = 28,000000000000004:
    cortadas as casas decimais, as duas davam 28 cêntimos e emparelhavam.
    Arredondadas ao cêntimo, são 29 e 28.
      entradas = 0,28, saidas = -0,29
    """
    saida = base("A", date(2025, 3, 1), -0.29)
    entrada = base("B", date(2025, 3, 1), 0.28)

    r = _sem_par(client)

    assert _ids(r) == [saida.id, entrada.id]
    assert (r["entradas"], r["saidas"]) == (0.28, -0.29)

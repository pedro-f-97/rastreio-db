"""Testes de caracterização dos totais mensais e da agregação por categoria.

Fixam o comportamento **actual** das duas funções privadas de
`backend/routers/estatisticas.py` que fazem a conta toda:

* `_calculate_totals` (linha 268) — o que entra em receitas, despesas e
  investimento, em cada mês;
* `_agregar_por_categoria` (linha 208) — o agrupamento por categoria e
  subcategoria que alimenta `GET /estatisticas/detalhe-mensal`.

São testes de função, não de API: nenhuma das duas toca na base de dados, e é
por isso que nenhum teste pede a `session` nem a `client`. O `poupanca` de
`resumo-mensal` (linha 35) fica de fora de propósito — é assunto para os testes
de API, mais tarde.

Nada aqui é corrigido. Onde o comportamento é questionável, fica marcado com
`# DEVIDA-TECNICA: Dn`, a remeter para `docs/divida-tecnica.md`. O `D20` ainda
não tem entrada no documento: fica à espera de um commit próprio, como o `D19`.

Os objectos que entram nas funções são `SimpleNamespace` com os mesmos nomes
de campo dos modelos, e o `tipo` é sempre o enum `TipoCategoria` — nunca uma
cadeia, porque o código compara com `==` contra o enum, e uma cadeia passaria
a todos os ramos sem chegar a nenhum.

Os quatro ramos, pela ordem em que são avaliados
------------------------------------------------
A chave do mês é criada nas linhas 277-278, **depois** dos dois filtros das
linhas 271-274 e **antes** da cadeia de ramos. Daí duas consequências que os
testes fixam: um mês só com transferências não aparece; um mês com uma
transação que não casa em ramo nenhum aparece, com os três cestos a zero.

| Ramo | Condição                                | Efeito                          |
| --- | --- | --- |
| A (281) | `receita`, não reembolsada, `valor > 0` | receitas += valor              |
| B (283) | `investimento`                          | investimento += valor, com o sinal que entra |
| C (285) | `valor < 0` e o tipo não é `receita`    | despesas += valor (negativo)    |
| D (287) | `valor > 0` e reembolsada               | despesas += valor (positivo)    |

São `elif`, um atrás do outro: o B chega antes do D, pelo que um investimento
marcado como reembolso nunca entra em despesas.

Convenções que estes testes fixam
--------------------------------
* O cesto `despesas` é uma **soma com sinal**: as despesas entram negativas e
  os reembolsos positivos, de modo que o total é a despesa líquida. É por isso
  que um reembolso de 120,00 entra como +120,0 e não como -120,0. A poupança,
  que não é calculada aqui mas sim em `resumo_mensal` (linha 35) por
  `receitas + despesas`, sai certa nos dois casos.
* `investimento` é um acumulador com sinal, e mais nada: uma compra negativa e
  uma venda positiva cancelam-se, e nunca tocam receitas nem despesas. O
  investimento é uma linha informativa à parte e não entra na poupança.
* `_calculate_totals` não arredonda nada e não devolve `poupanca` nem `saldo`.
  Devolve `{mês: {receitas, despesas, investimento}}` com os valores em euros,
  tal como entraram.
* `_agregar_por_categoria` devolve um **dicionário** indexado por
  `categoria_id`, com `total_centimos` em cêntimos inteiros, e as
  subcategorias noutro dicionário indexado por `subcategoria_id` — ou por `0`,
  com o nome `"Sem subcategoria"`, quando a transação não tem subcategoria. A
  função não filtra transferências: o filtro está na consulta que a alimenta
  (`_query_transacoes_mes`, linha 204), pelo que entra o que lhe derem.

Números escolhidos
------------------
Todos os valores são múltiplos de 0,25, exactamente representáveis em vírgula
flutuante, para que as comparações por igualdade sejam exactas e não dependam
de ruído binário nem de `pytest.approx`. Excepto o cenário do arredondamento
em cêntimos, em que o valor não é um múltiplo de 0,25 de propósito. As datas
são fixas em 2025: nenhum teste assenta na data de hoje.

Todos os valores esperados são calculados à mão e escritos como constantes, com
o cálculo no comentário de cada teste.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from database import TipoCategoria
from routers.estatisticas import _agregar_por_categoria, _calculate_totals


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

# Nomes das categorias como o `popular_bd.py` as semeia. O `tipo` é o enum
# real, nunca uma cadeia.
NOMES = {
    TipoCategoria.receita: "Receita",
    TipoCategoria.despesa: "Casa",
    TipoCategoria.investimento: "Investimento",
    TipoCategoria.transferencia: "Transferência",
}


def transacao(ano, mes, dia, tipo, valor, reembolso=False):
    """Transação com os mesmos nomes de campo que o modelo `Transacao`.

    `tipo=None` significa "sem categoria": é assim que se escreve a transação
    órfã, que a função tem de ignorar.
    """
    return SimpleNamespace(
        data=date(ano, mes, dia),
        valor=valor,
        reembolso=reembolso,
        categoria=(
            SimpleNamespace(tipo=tipo, nome=NOMES[tipo]) if tipo is not None else None
        ),
    )


def linha(categoria_id, categoria_nome, tipo, valor,
          subcategoria_id=None, subcategoria_nome=None):
    """Linha de agregação com os mesmos nomes de campo que a consulta projecta."""
    return SimpleNamespace(
        categoria_id=categoria_id,
        categoria_nome=categoria_nome,
        categoria_tipo=tipo,
        subcategoria_id=subcategoria_id,
        subcategoria_nome=subcategoria_nome,
        valor=valor,
    )


# ---------------------------------------------------------------------------
# Secção A — _calculate_totals: a que ramo cada transação cai
# ---------------------------------------------------------------------------

def test_receita_normal_entra_no_cesto_das_receitas():
    """Uma receita positiva e não reembolsada vai toda para receitas.

    Cálculo à mão:
      chave do mês = (2025, 3)
      ramo A: tipo receita, `not reembolso` verdadeiro, 1500,00 > 0
      receitas = 0 + 1500,00 = 1500,0
      os outros dois cestos ficam com o zero inicial da linha 278
    """
    resultado = _calculate_totals([
        transacao(2025, 3, 10, TipoCategoria.receita, 1500.00),
    ])

    assert resultado == {
        (2025, 3): {"receitas": 1500.0, "despesas": 0, "investimento": 0},
    }


def test_despesa_normal_entra_com_sinal_negativo():
    """Uma despesa normal entra em despesas com o valor tal e qual, negativo.

    Cálculo à mão:
      ramo A não pega: o tipo não é receita
      ramo B não pega: não é investimento
      ramo C: -250,50 < 0 e o tipo não é receita
      despesas = 0 + (-250,50) = -250,5
    """
    resultado = _calculate_totals([
        transacao(2025, 3, 5, TipoCategoria.despesa, -250.50),
    ])

    assert resultado == {
        (2025, 3): {"receitas": 0, "despesas": -250.5, "investimento": 0},
    }


def test_reembolso_entra_no_cesto_das_despesas_com_sinal_positivo():
    """O reembolso entra em despesas com sinal **positivo**.

    Cálculo à mão:
      ramo C não pega: 120,00 não é < 0
      ramo D: 120,00 > 0 e a marca de reembolso está ligada
      despesas = 0 + 120,00 = 120,0

    Não é um sinal trocado: o cesto é uma soma com sinal, e as despesas
    negativas com os reembolsos positivos dão a despesa líquida. É esse total
    que `resumo_mensal` (linha 35) soma às receitas para dar a poupança, pelo
    que um reembolso de 120,00 tem de entrar com + para a poupança descer.
    """
    resultado = _calculate_totals([
        transacao(2025, 5, 12, TipoCategoria.despesa, 120.00, reembolso=True),
    ])

    assert resultado == {
        (2025, 5): {"receitas": 0, "despesas": 120.0, "investimento": 0},
    }


def test_transferencia_e_ignorada_e_nao_cria_mes():
    """Uma transferência não é contada, nem faz o mês aparecer.

    Cálculo à mão:
      linha 273: o tipo é transferência, logo `continue` (linha 274)
      a chave (2025, 4) é criada na linha 277, depois do filtro
      resultado: dicionário vazio

    A diferença para os cenários em que o mês fica a zeros importa: ali a
    chave é criado, aqui não. No endpoint a diferença não se vê, porque
    `resumo_mensal` volta a acrescentar os meses em falta a zeros (linhas
    23-26); aqui vê-se.
    """
    resultado = _calculate_totals([
        transacao(2025, 4, 2, TipoCategoria.transferencia, -500.00),
    ])

    assert resultado == {}


def test_investimento_soma_compra_e_venda_no_mes():
    """Compra e venda de investimento somam no mesmo cesto, com sinal.

    Cálculo à mão:
      02-04: ramo B, investimento = 0 + (-1000,00) = -1000,0
      20-04: ramo B, investimento = -1000,0 + 1500,00 = 500,0
      receitas e despesas ficam a zero: um investimento nunca as toca
    """
    resultado = _calculate_totals([
        transacao(2025, 4, 2, TipoCategoria.investimento, -1000.00),
        transacao(2025, 4, 20, TipoCategoria.investimento, 1500.00),
    ])

    assert resultado == {
        (2025, 4): {"receitas": 0, "despesas": 0, "investimento": 500.0},
    }


def test_investimento_marcado_como_reembolso_continua_no_cesto_do_investimento():
    """O ramo B chega antes do D: a marca de reembolso não desvia o investimento.

    Cálculo à mão:
      ramo A não pega: o tipo não é receita
      ramo B pega antes de o D ser avaliado
      investimento = 0 + (-1000,00) = -1000,0
      despesas = 0, porque o ramo D nunca é alcançado
    """
    resultado = _calculate_totals([
        transacao(2025, 4, 2, TipoCategoria.investimento, -1000.00, reembolso=True),
    ])

    assert resultado == {
        (2025, 4): {"receitas": 0, "despesas": 0, "investimento": -1000.0},
    }


def test_receita_negativa_desaparece_dos_totais():
    # DEVIDA-TECNICA: D4
    """Uma receita negativa não cai em ramo nenhum, e o mês fecha sem ela.

    Cálculo à mão:
      -300,00, tipo receita, sem reembolso:
        ramo A: `valor > 0` falha
        ramo B: não é investimento
        ramo C: `valor < 0` é verdadeiro, mas exclui explicitamente receitas
        ramo D: `valor > 0` falha
      1500,00, tipo receita, sem reembolso:
        ramo A: receitas = 0 + 1500,00 = 1500,0

    O -300,00 não está em nenhum cesto. Se fosse contado como despesa, o mês
    fecharia com receitas 1500,0 e despesas -300,0, e a poupança (que não é
    calculada aqui) em 1200,0 em vez de 1500,0.
    """
    resultado = _calculate_totals([
        transacao(2025, 3, 10, TipoCategoria.receita, -300.00),
        transacao(2025, 3, 15, TipoCategoria.receita, 1500.00),
    ])

    assert resultado == {
        (2025, 3): {"receitas": 1500.0, "despesas": 0, "investimento": 0},
    }


def test_despesa_positiva_sem_marca_de_reembolso_desaparece():
    # DEVIDA-TECNICA: D20
    """Uma despesa positiva sem a marca de reembolso não cai em ramo nenhum.

    Mesma raiz que a D4, pelo outro lado: a linha 284 exige `valor < 0` e a
    linha 286 exige a marca de reembolso, e entre as duas não há nada que
    apanhe este caso.

    Cálculo à mão:
      -45,50: ramo C, despesas = 0 + (-45,50) = -45,5
      +30,00, sem a marca de reembolso:
        ramo A não pega: o tipo não é receita
        ramo B não pega: não é investimento
        ramo C não pega: 30,00 não é < 0
        ramo D não pega: a marca está desligada
      despesas = -45,5, e fica -45,5

    Comportamento actual: o valor desaparece e o mês fecha com as despesas de
    antes. Comportamento esperado: contar na soma de despesas, ou seja
    -45,5 + 30,00 = -15,5. A diferença na poupança é de 30,00.

    A decisão de negócio (Pedro) é que o correcto é uma despesa positiva estar
    marcada como reembolso; mas, como os valores seguem o sinal, a conta fica
    certa mesmo sem a marca, e por isso o valor não pode ser ignorado. Este
    teste fixa o comportamento actual, não o desejado.
    """
    resultado = _calculate_totals([
        transacao(2025, 6, 3, TipoCategoria.despesa, -45.50),
        transacao(2025, 6, 18, TipoCategoria.despesa, 30.00),
    ])

    assert resultado == {
        (2025, 6): {"receitas": 0, "despesas": -45.5, "investimento": 0},
    }


@pytest.mark.parametrize(
    "tipo",
    [TipoCategoria.despesa, TipoCategoria.receita],
    ids=["despesa", "receita"],
)
def test_valor_zero_cria_o_mes_mas_nao_soma(tipo):
    """Um valor zero não entra em cesto nenhum, mas o mês fica criado.

    Cálculo à mão (vale para os dois tipos):
      ramo A: só pega em receitas com `valor > 0`, e 0,0 não é > 0
      ramo B: só pega em investimentos
      ramo C: exige `valor < 0`
      ramo D: exige `valor > 0`
      os três cestos ficam com o zero inicial da linha 278
    """
    resultado = _calculate_totals([
        transacao(2025, 5, 20, tipo, 0.0),
    ])

    assert resultado == {
        (2025, 5): {"receitas": 0, "despesas": 0, "investimento": 0},
    }


def test_varias_transacoes_no_mesmo_mes_somam_ao_mesmo_cesto():
    """Tudo o que é do mesmo mês vai para a mesma chave, por ordem de chegada.

    Cálculo à mão, mês de 2025-06:
      receitas     = 0 + 1500,00                    =  1500,00
      despesas     = 0 + (-45,50)                  =   -45,50
                   = -45,50 + (-1200,25)           = -1245,75
                   = -1245,75 + 30,00 (reembolso) = -1215,75
      investimento = 0 + (-500,00)                 =  -500,00

    E o mês seguinte, 2025-07, que tem de ter o seu cesto:
      despesas = 0 + (-800,00) = -800,0
    """
    resultado = _calculate_totals([
        transacao(2025, 6, 2, TipoCategoria.receita, 1500.00),
        transacao(2025, 6, 3, TipoCategoria.despesa, -45.50),
        transacao(2025, 6, 10, TipoCategoria.despesa, -1200.25),
        transacao(2025, 6, 18, TipoCategoria.despesa, 30.00, reembolso=True),
        transacao(2025, 6, 25, TipoCategoria.investimento, -500.00),
        transacao(2025, 7, 1, TipoCategoria.despesa, -800.00),
    ])

    assert resultado == {
        (2025, 6): {"receitas": 1500.0, "despesas": -1215.75, "investimento": -500.0},
        (2025, 7): {"receitas": 0, "despesas": -800.0, "investimento": 0},
    }


def test_transacao_sem_categoria_e_ignorada_e_nao_cria_mes():
    """Uma transação sem categoria é descartada antes de se criar a chave.

    Cálculo à mão:
      linha 271: `not t.categoria` é verdadeiro, logo `continue` (linha 272)
      a chave (2025, 7) nunca chega a ser criada
      resultado: dicionário vazio
    """
    resultado = _calculate_totals([
        transacao(2025, 7, 9, None, -50.00),
    ])

    assert resultado == {}


# ---------------------------------------------------------------------------
# Secção B — _agregar_por_categoria: o dicionário que alimenta o detalhe mensal
# ---------------------------------------------------------------------------

def test_agrega_duas_categorias_e_as_respectivas_subcategorias():
    """Duas categorias, três subcategorias e uma linha sem subcategoria.

    Cálculo à mão, em cêntimos inteiros (`round(valor x 100)`, linha 228):

      linha 1, casa / renda,        -800,00 -> -80000
      linha 2, casa / renda,        -200,00 -> -20000
      linha 3, casa / supermercado, -150,25 -> -15025
      linha 4, casa / sem subcategoria, -50,00 -> -5000
      linha 5, receita / salário,  1500,00 -> 150000
      linha 6, investimento / ações, -1000,00 -> -100000

      casa         = -80000 - 20000 - 15025 - 5000 = -120025
        renda       = -80000 - 20000              = -100000
        supermercado                               =  -15025
        sem subcategoria                           =   -5000
        a soma das três          -100000 -15025 -5000 = -120025
      receita     = 150000
        salário    = 150000
      investimento = -100000
        ações      = -100000

    A chave da subcategoria ausente é `0` e o nome é o texto literal da linha
    224. O `categoria_tipo` fica o enum em bruto: quem o converte em texto é
    `detalhe_mensal`, na linha 244.
    """
    agregado = _agregar_por_categoria([
        linha(1, "Casa", TipoCategoria.despesa, -800.00, 10, "Renda"),
        linha(1, "Casa", TipoCategoria.despesa, -200.00, 10, "Renda"),
        linha(1, "Casa", TipoCategoria.despesa, -150.25, 11, "Supermercado"),
        linha(1, "Casa", TipoCategoria.despesa, -50.00),
        linha(2, "Receita", TipoCategoria.receita, 1500.00, 20, "Salário"),
        linha(3, "Investimento", TipoCategoria.investimento, -1000.00, 30, "Ações"),
    ])

    assert agregado == {
        1: {
            "categoria_id": 1,
            "categoria_nome": "Casa",
            "categoria_tipo": TipoCategoria.despesa,
            "total_centimos": -120025,
            "subcategorias": {
                10: {"subcategoria_nome": "Renda", "total_centimos": -100000},
                11: {"subcategoria_nome": "Supermercado", "total_centimos": -15025},
                0: {"subcategoria_nome": "Sem subcategoria", "total_centimos": -5000},
            },
        },
        2: {
            "categoria_id": 2,
            "categoria_nome": "Receita",
            "categoria_tipo": TipoCategoria.receita,
            "total_centimos": 150000,
            "subcategorias": {
                20: {"subcategoria_nome": "Salário", "total_centimos": 150000},
            },
        },
        3: {
            "categoria_id": 3,
            "categoria_nome": "Investimento",
            "categoria_tipo": TipoCategoria.investimento,
            "total_centimos": -100000,
            "subcategorias": {
                30: {"subcategoria_nome": "Ações", "total_centimos": -100000},
            },
        },
    }


def test_arredondamento_em_centimos_perde_meio_centimo():
    # DEVIDA-TECNICA: D11
    """Metade de um cêntimo perde-se na conversão para cêntimos inteiros.

    Cálculo à mão:
      0,125 é exactamente 1/8 em vírgula flutuante, e 0,125 x 100 = 12,5
      exactamente, sem ruído nenhum
      round(12,5) = 12, porque o `round` do Python arredonda a par e 12 é par
      total_centimos = 12, e o chamador divide por 100 e apresenta 0,12
      (`detalhe_mensal`, linha 245)

    Com 13 cêntimos, por arredondamento para cima, seriam 0,13. A diferença é
    de meio cêntimo, e o valor guardado na base de dados é fiel — a perda é
    só na apresentação.

    Este resultado vai mudar quando a moeda passar a `Numeric` (ver
    `DEVIDA-TECNICA: D11`): os testes de arredondamento passam a valer outra
    coisa, e é o que se espera que aconteça.
    """
    agregado = _agregar_por_categoria([
        linha(1, "Casa", TipoCategoria.despesa, 0.125, 10, "Renda"),
    ])

    assert agregado[1]["total_centimos"] == 12
    assert agregado[1]["subcategorias"][10]["total_centimos"] == 12

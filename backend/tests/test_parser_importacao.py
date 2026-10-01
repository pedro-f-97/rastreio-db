"""Testes de caracterização do parser de importação de extratos.

Fixam o comportamento **actual** de `parser_importacao.py`: como é lido um
valor (`_parse_valor`), como é lida uma data (`_parse_data`) e como é lido um
ficheiro inteiro (`parse_ficheiro`). Servem para que mexer no parser não mude
nada sem dar conta: se um destes testes falhar, a mudança foi de propósito e
tem de ser justificada.

Nada aqui é corrigido. Onde o comportamento é questionável, fica marcado com
`# DEVIDA-TECNICA: Dn`, a remeter para `docs/divida-tecnica.md`.

Todos os valores esperados são calculados à mão e escritos como constantes. O
cálculo está no comentário de cada caso, dentro das tabelas do `parametrize` ou
imediatamente acima da afirmação. Nenhum teste assenta na data de hoje: as datas
são fixas. O perfil é um `SimpleNamespace` com os mesmos nomes de campo de
`PerfilImportacao` e os dois campos de enumeração são os enums reais
(`TipoFicheiro`, `ModoValor`), que é o que o router lhe passa.

O símbolo de moeda dos testes é o cifrão, e não o euro, só para manter o
ficheiro em caracteres latinos. O comportamento é o mesmo: `_parse_valor` não
reconhece símbolo nenhum.

Convenções que estes testes fixam
--------------------------------
* `separador_decimal` decide o que é o ponto: com `","` os pontos são lidos
  como separadores de milhares e apagados; com `"."` são as vírgulas. A função
  não tem forma de distinguir um do outro (ver `DEVIDA-TECNICA: D12d`).
* `_parse_valor` não arredonda. Onde o valor sai directamente de `float(texto)`
  — quase sempre — a comparação é por `==` exacta, porque o literal escrito no
  teste e o literal interpretado pelo `float` são a mesma dupla. Só a secção E,
  onde há uma subtracção entre duas colunas, usa `pytest.approx` com meio
  cêntimo de tolerância.
* Célula vazia não é a mesma coisa em todo o lado. Em `coluna_unica` não há
  guarda nenhuma, e uma célula vazia dá erro. Em `duas_colunas`, no `fee` e no
  `saldo` a guarda é `raw not in (None, "", "None")` e a célula vazia vale zero
  — e o texto `None`, escrito por um humano ou por um exportador, conta como
  vazio.
* `total_linhas` conta as linhas que deram transacção ou erro. Linhas vazias e
  linhas de cabeçalho não contam. O `linha` que vai no erro é o número da linha
  do ficheiro, não o índice dentro do que foi lido.
* `_ler_linhas_csv` usa o `csv.reader` sem `delimiter`, pelo que a vírgula é o
  único separador aceite num CSV (ver `DEVIDA-TECNICA: D19`).
* `openpyxl` é uma dependência de produção, não de teste: está em
  `backend/requirements.txt`. Estes testes geram um `.xlsx` verdadeiro com ele.

Nota sobre `DEVIDA-TECNICA: D19` — o caso do CSV delimitado por ponto-e-vírgula
está registado em `docs/divida-tecnica.md`.
"""

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from database import ModoValor, TipoFicheiro
from parser_importacao import (
    ErroParsing,
    _parse_data,
    _parse_valor,
    parse_ficheiro,
)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def perfil(**campos):
    """Perfil de importação com os mesmos nomes de campo do modelo real.

    Os valores por omissão servem o cenário mais comum do extrato português:
    CSV, vírgula decimal, uma coluna de valor e uma data por linha.
    """
    valores = {
        "tipo_ficheiro": TipoFicheiro.csv,
        "linha_inicio_dados": 2,
        "coluna_data": 0,
        "formato_data": "%d/%m/%Y",
        "coluna_descricao": 1,
        "modo_valor": ModoValor.coluna_unica,
        "coluna_valor": 2,
        "coluna_debito": None,
        "coluna_credito": None,
        "separador_decimal": ",",
        "tem_saldo": False,
        "coluna_saldo": None,
        "coluna_fee": None,
    }
    valores.update(campos)
    return SimpleNamespace(**valores)


def escrever_csv(caminho, linhas, codificacao="utf-8-sig"):
    """Escreve um CSV verdadeiro no disco e devolve o caminho.

    Por omissão escreve em `utf-8-sig`, que é como o Excel exporta em português:
    com a marca de ordem de bytes no princípio do ficheiro.
    """
    caminho.write_text("".join(linha + "\n" for linha in linhas), encoding=codificacao)
    return caminho


def escrever_xlsx(caminho, linhas):
    """Escreve um livro de Excel verdadeiro no disco e devolve o caminho."""
    livro = Workbook()
    folha = livro.active
    for linha in linhas:
        folha.append(linha)
    livro.save(caminho)
    return caminho


# Extrato de banco em CSV. Os valores com vírgula decimal têm de vir entre
# aspas, porque a vírgula é também o separador de colunas do ficheiro.
CSV_EXTRATO = (
    "Data,Descrição,Valor",
    '31/01/2026,Supermercado,"-45,60"',
    '02/02/2026,Salário,"1500,00"',
    "",  # linha completamente vazia
    '05/02/2026,Transferência,"1.234,56"',
    "07/02/2026,Café,",  # valor vazio: dá erro
)

# Extrato com débito e crédito em colunas separadas.
CSV_DEBITO_CREDITO = (
    "Data,Descrição,Débito,Crédito",
    '31/01/2026,Transferência,"45,60","1500,00"',
    "01/02/2026,Compras,,150,00",  # débito vazio
    "02/02/2026,Taxa,20,00,",  # crédito vazio
)

# Extrato com comissão, que o banco exporta na coluna à direita do valor.
CSV_COM_COMISSAO = (
    "Data,Descrição,Valor,Comissão",
    '31/01/2026,Compra de ações,"-50,00","1,50"',
    '01/02/2026,Compra de ações,"-50,00","-1,50"',
    '02/02/2026,Transferência,"20,00",',  # comissão vazia
)


# ---------------------------------------------------------------------------
# Secção A — _parse_valor: separador decimal, milhares e valores negativos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "entrada, separador_decimal, esperado, calculo",
    [
        ("1500,00", ",", 1500.0,
         'vírgula decimal vira ponto: "1500,00" -> "1500.00"'),
        ("-45,60", ",", -45.6,
         'o sinal sobrevive à troca: "-45,60" -> "-45.60"'),
        ("1500.00", ".", 1500.0,
         'não há vírgula para apagar, o texto fica como está: "1500.00"'),
        ("-45.60", ".", -45.6,
         'o mesmo com o ponto decimal: "-45.60"'),
        ("1.234,56", ",", 1234.56,
         'ponto de milhar apagado: "1.234,56" -> "1234,56" -> "1234.56"'),
        ("1,234.56", ".", 1234.56,
         'vírgula de milhar apagada: "1,234.56" -> "1234.56"'),
        ("-1.234,56", ",", -1234.56,
         'milhar e sinal: "-1.234,56" -> "-1234,56" -> "-1234.56"'),
        ("1 234,56", ",", 1234.56,
         'espaço de milhar apagado: "1 234,56" -> "1234,56" -> "1234.56"'),
        ("1\xa0234,56", ",", 1234.56,
         'o espaço não separável (código 160) também é apagado, '
         'pelo mesmo caminho que o espaço normal'),
        (1500, ".", 1500.0,
         "número já vem número: float(1500) = 1500.0"),
        (45.6789, ".", 45.6789,
         "número não é arredondado a cêntimos: 45.6789 fica 45.6789"),
    ],
)
def test_valor_lido_com_o_separador_do_perfil(entrada, separador_decimal, esperado, calculo):
    obtido = _parse_valor(entrada, separador_decimal)
    assert obtido == esperado, (
        f"{calculo}. Esperado {esperado}, veio {obtido}"
    )


# ---------------------------------------------------------------------------
# Secção B — _parse_valor: o que falha com ErroParsing
# ---------------------------------------------------------------------------

# DEVIDA-TECNICA: D12d (parênteses de contabilidade e símbolos de moeda não
# são suportados; pelo menos a falha é visível, ao contrário dos milhares).
@pytest.mark.parametrize(
    "entrada, separador_decimal, mensagem, nota",
    [
        (None, ",", "valor em falta",
         "falta o valor: a guarda de `None` corre antes de qualquer texto"),
        ("", ".", "valor inválido: ''",
         'texto vazio: float("") não é um número'),
        ("   ", ".", "valor inválido: '   '",
         "só espaços: o texto é aparado para análise mas a mensagem repete o "
         "original, com os espaços"),
        ("(123,45)", ",", "valor inválido: '(123,45)'",
         'parênteses de contabilidade: "(123,45)" -> "(123.45)" e o float falha'),
        ("1.234,56 $", ",", "valor inválido: '1.234,56 $'",
         'símbolo de moeda no fim: "1.234,56$" ainda não é um número'),
        ("$45.60", ".", "valor inválido: '$45.60'",
         'símbolo de moeda à frente: "$45.60" também não é um número'),
        ("N/A", ".", "valor inválido: 'N/A'",
         "texto que nem é número nem vazio"),
    ],
)
def test_valor_que_falha_levanta_erro_de_parsing(entrada, separador_decimal, mensagem, nota):
    with pytest.raises(ErroParsing) as erro:
        _parse_valor(entrada, separador_decimal)

    obtido = str(erro.value)
    assert obtido == mensagem, f"{nota}. Esperado {mensagem!r}, veio {obtido!r}"


# ---------------------------------------------------------------------------
# Secção C — milhares ambíguos: o valor lido mil vezes mais pequeno, em silêncio
# ---------------------------------------------------------------------------

def test_milhares_sem_milhares_viram_decimal():
    """Um valor de mil euros em ponto entra como um euro e meio.

    DEVIDA-TECNICA: D12d
    """
    # O ficheiro queria dizer 1234 (1.234 x 1000). O perfil diz que o ponto é
    # decimal, e o parser acredita-lhe: devolve 1.234, que é o valor verdadeiro
    # dividido por mil. Nem erro, nem aviso, nem nada em `erros`: a importação
    # parece ter corrido bem.
    assert _parse_valor("1.234", ".") == 1.234


def test_milhares_ambiguos_em_valor_com_centimos():
    """`1.234,56` com perfil em ponto perde as duas casas e a vírgula.

    DEVIDA-TECNICA: D12d
    """
    # "1.234,56" -> tira a vírgula como se fosse milhar -> "1.23456", que é
    # 1234,56 dividido por 1000 (1.234,56 x 1000 = 1234,56).
    assert _parse_valor("1.234,56", ".") == 1.23456


def test_o_mesmo_texto_com_as_duas_configuracoes_difere_num_factor_de_mil():
    """A diferença entre o perfil certo e o perfil errado é um factor de mil.

    DEVIDA-TECNICA: D12d
    """
    com_virgula = _parse_valor("1.234,56", ",")  # 1.234,56 -> 1234,56 -> 1234.56
    com_ponto = _parse_valor("1.234,56", ".")    # 1.234,56 -> 1.23456

    assert com_virgula == 1234.56
    assert com_ponto == 1.23456
    # 1234,56 / 1,23456 = 1000. As duas leituras são ambas plausíveis à primeira
    # vista e nenhuma das duas levanta dúvida: a diferença é um factor de mil.


def test_ponto_decimal_comido_como_milhar():
    """Com perfil em vírgula, um ponto decimal é lido como separador de milhar.

    DEVIDA-TECNICA: D12d
    """
    # "45.60" -> "4560" = 4560,0. O valor verdadeiro é 45,60, e 45,60 x 100 =
    # 4560,00: o ponto some e o valor sai multiplicado por cem.
    assert _parse_valor("45.60", ",") == 4560.0


# ---------------------------------------------------------------------------
# Secção D — _parse_data: os formatos do perfil e o que não é data
# ---------------------------------------------------------------------------

# Os quatro formatos são os que o frontend oferece em
# `frontend/src/pages/Importacao.jsx:8-13`. Todos os quatro casos de baixo são a
# mesma data escrita de quatro maneiras.
@pytest.mark.parametrize(
    "texto, formato_data, data_esperada",
    [
        ("31/01/2026", "%d/%m/%Y", date(2026, 1, 31)),
        ("2026-01-31", "%Y-%m-%d", date(2026, 1, 31)),
        ("2026/01/31", "%Y/%m/%d", date(2026, 1, 31)),
        ("31-01-2026", "%d-%m-%Y", date(2026, 1, 31)),
        ("  31/01/2026  ", "%d/%m/%Y", date(2026, 1, 31)),
    ],
)
def test_data_lida_no_formato_do_perfil(texto, formato_data, data_esperada):
    obtido = _parse_data(texto, formato_data)
    assert obtido == data_esperada, (
        f"Esperado {data_esperada}, veio {obtido}"
    )


@pytest.mark.parametrize(
    "celula, data_esperada",
    [
        (datetime(2026, 1, 31, 0, 0), date(2026, 1, 31)),
        (datetime(2026, 1, 31, 23, 59, 59), date(2026, 1, 31)),
    ],
)
def test_data_que_jam_vem_como_objecto_ignora_o_formato_do_perfil(celula, data_esperada):
    """Uma data que o Excel traz como objecto `datetime` não passa por `strptime`.

    O ramo `hasattr(raw, "date")` chama o método e pronto: o `formato_data` do
    perfil não é consultado. É o que permite ler um `.xlsx` em que a coluna da
    data está formatada como data, e não como texto. A hora, se a houver, é
    deitada fora: o que interessa é o dia.
    """
    obtido = _parse_data(celula, "%d/%m/%Y")
    assert obtido == data_esperada, (
        f"Esperado {data_esperada}, veio {obtido}"
    )


@pytest.mark.parametrize(
    "entrada, formato_data, mensagem, nota",
    [
        (None, "%d/%m/%Y", "data em falta",
         "falta a data: a guarda de `None` corre antes de tudo o resto"),
        ("31/02/2026", "%d/%m/%Y",
         "data inválida: '31/02/2026' (formato esperado: %d/%m/%Y)",
         "dia 31 de fevereiro: o `strptime` recusa e a linha dá erro"),
        ("2026-01-31", "%d/%m/%Y",
         "data inválida: '2026-01-31' (formato esperado: %d/%m/%Y)",
         "formato trocado no perfil: a data está escrita ao contrário do que o "
         "perfil espera"),
        ("31/01/2026", "%Y-%m-%d",
         "data inválida: '31/01/2026' (formato esperado: %Y-%m-%d)",
         "o mesmo erro pelo outro lado: formato do perfil que não bate com a "
         "coluna"),
        (date(2026, 1, 31), "%d/%m/%Y",
         "data inválida: '2026-01-31' (formato esperado: %d/%m/%Y)",
         "o ramo dos objectos é `hasattr(raw, \"date\")`, e um `datetime.date` "
         "não tem método `date()` — só o `datetime.datetime` tem. Uma data pura "
         "cai por isso no `strptime` e falha. Com o formato `%Y-%m-%d` passava, "
         "por coincidência, porque `str()` de uma data sai em ISO"),
    ],
)
def test_data_que_falha_levanta_erro_de_parsing(entrada, formato_data, mensagem, nota):
    with pytest.raises(ErroParsing) as erro:
        _parse_data(entrada, formato_data)

    obtido = str(erro.value)
    assert obtido == mensagem, f"{nota}. Esperado {mensagem!r}, veio {obtido!r}"


# ---------------------------------------------------------------------------
# Secção E — parse_ficheiro com um CSV verdadeiro
# ---------------------------------------------------------------------------

def test_csv_lido_a_partir_da_segunda_linha(tmp_path):
    """Uma linha por transacção, uma linha vazia saltada e uma linha com erro."""
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_EXTRATO)
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(linha_inicio_dados=2))

    assert resultado["transacoes"] == [
        {"data": date(2026, 1, 31), "descricao": "Supermercado",
         "valor": -45.6, "saldo": None},
        {"data": date(2026, 2, 2), "descricao": "Salário",
         "valor": 1500.0, "saldo": None},
        {"data": date(2026, 2, 5), "descricao": "Transferência",
         "valor": 1234.56, "saldo": None},
    ]

    # A linha 4 do ficheiro está vazia e é saltada sem contagem nenhuma; a linha
    # 6 tem valor vazio, que em `coluna_unica` não é protegido por guarda
    # nenhuma e dá erro. O número de linha do erro é o do ficheiro.
    assert resultado["erros"] == [{"linha": 6, "erro": "valor inválido: ''"}]
    # 3 transacções + 1 erro. A linha vazia não entra na contagem.
    assert resultado["total_linhas"] == 4


def test_csv_lido_a_partir_da_terceira_linha_perde_a_segunda(tmp_path):
    """A linha 2 do ficheiro nunca chega a ser lida."""
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_EXTRATO)
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(linha_inicio_dados=3))

    # Só entram as linhas 3 a 6: a compra de 31/01/2026 (linha 2) desaparece.
    assert [t["data"] for t in resultado["transacoes"]] == [
        date(2026, 2, 2), date(2026, 2, 5),
    ]
    assert [t["valor"] for t in resultado["transacoes"]] == [1500.0, 1234.56]
    # O erro continua a ser reportado na linha 6: a linha 4, vazia, conta para
    # a numeração mesmo não produzindo transacção.
    assert resultado["erros"] == [{"linha": 6, "erro": "valor inválido: ''"}]
    assert resultado["total_linhas"] == 3


def test_csv_com_marca_de_ordem_dos_bytes(tmp_path):
    """A marca de ordem de bytes do Excel não fica colada à primeira data."""
    caminho = escrever_csv(tmp_path / "com_marca.csv", ('31/01/2026,Supermercado,"-45,60"',))
    # `linha_inicio_dados=1` põe a marca no princípio da primeira célula lida.
    # Se o ficheiro fosse decodificado sem a tirar, a data seria
    # "«marca»31/01/2026" e a linha dava erro.
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(linha_inicio_dados=1))

    assert resultado["transacoes"] == [
        {"data": date(2026, 1, 31), "descricao": "Supermercado",
         "valor": -45.6, "saldo": None},
    ]
    assert resultado["erros"] == []
    assert resultado["total_linhas"] == 1


def test_csv_duas_colunas_credito_menos_debito(tmp_path):
    """No modo de duas colunas, o valor é o crédito menos o débito."""
    caminho = escrever_csv(tmp_path / "duas_colunas.csv", CSV_DEBITO_CREDITO)
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        modo_valor=ModoValor.duas_colunas,
        coluna_valor=None,
        coluna_debito=2,
        coluna_credito=3,
    ))

    valores = [t["valor"] for t in resultado["transacoes"]]
    # Linha 2: 1500,00 - 45,60 = 1454,40
    # Linha 3: débito vazio vale 0,00 -> 150,00 - 0,00 = 150,00
    # Linha 4: crédito vazio vale 0,00 -> 0,00 - 20,00 = -20,00
    # É a única subtração da suite, e por isso a única com meio cêntimo de
    # tolerância: os dois valores vêm de `float(texto)` e a subtração é feita
    # em vírgula flutuante.
    assert valores[0] == pytest.approx(1454.40, abs=0.005)
    assert valores[1] == pytest.approx(150.00, abs=0.005)
    assert valores[2] == pytest.approx(-20.00, abs=0.005)

    assert [t["data"] for t in resultado["transacoes"]] == [
        date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2),
    ]
    assert resultado["erros"] == []
    assert resultado["total_linhas"] == 3


def test_csv_duas_colunas_trata_o_texto_none_como_celula_vazia(tmp_path):
    """O texto `None` escrito na célula conta como célula vazia."""
    caminho = escrever_csv(
        tmp_path / "none.csv",
        ("Data,Descrição,Débito,Crédito", '31/01/2026,Anulação,None,"150,00"'),
    )
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        modo_valor=ModoValor.duas_colunas,
        coluna_valor=None,
        coluna_debito=2,
        coluna_credito=3,
    ))

    # A guarda é `raw not in (None, "", "None")`: o texto `None` escrito por um
    # exportador vale 0,00, tal como uma célula verdadeiramente vazia.
    # Crédito 150,00 - débito 0,00 = 150,00
    assert [t["valor"] for t in resultado["transacoes"]] == [150.0]
    assert resultado["erros"] == []
    assert resultado["total_linhas"] == 1


def test_linha_mais_curta_que_as_colunas_do_perfil(tmp_path):
    """Uma coluna apontada para lá do fim da linha dá uma célula em falta."""
    caminho = escrever_csv(tmp_path / "curta.csv", ("Descrição,Valor", 'Supermercado,"-45,60"'))
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        linha_inicio_dados=2,
        coluna_data=2,       # a linha só tem duas colunas
        coluna_descricao=0,
        coluna_valor=1,
    ))

    assert resultado["transacoes"] == []
    assert resultado["erros"] == [{"linha": 2, "erro": "data em falta"}]
    assert resultado["total_linhas"] == 1


def test_ficheiro_so_com_linhas_vazias(tmp_path):
    """Um ficheiro sem uma única célula com conteúdo não dá nada."""
    caminho = escrever_csv(tmp_path / "vazio.csv", ("Data,Descrição,Valor", "", ""))
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(linha_inicio_dados=2))

    assert resultado == {"transacoes": [], "total_linhas": 0, "erros": []}


def test_csv_delimitado_por_ponto_e_virgula_e_lido_como_uma_coluna(tmp_path):
    """Um CSV com ponto-e-vírgula é lido como se tivesse uma coluna só.

    DEVIDA-TECNICA: D19
    """
    caminho = escrever_csv(
        tmp_path / "pontos_e_virgulas.csv",
        ("Data;Descrição;Valor", "31/01/2026;Supermercado;-45.60"),
    )
    resultado = parse_ficheiro(
        caminho.read_bytes(),
        perfil(linha_inicio_dados=2, separador_decimal="."),
    )

    # `_ler_linhas_csv` chama o `csv.reader` sem `delimiter`, e o separador por
    # omissão é a vírgula. Cada linha do ficheiro tem zero vírgulas, logo vem
    # uma única célula com a linha inteira dentro, e a data nem sequer é
    # parecida com uma data. A importação inteira falha linha a linha.
    assert resultado["transacoes"] == []
    assert resultado["erros"] == [{
        "linha": 2,
        "erro": "data inválida: '31/01/2026;Supermercado;-45.60' "
                "(formato esperado: %d/%m/%Y)",
    }]
    assert resultado["total_linhas"] == 1


# ---------------------------------------------------------------------------
# Secção F — parse_ficheiro com um XLSX verdadeiro
# ---------------------------------------------------------------------------

def test_xlsx_lido_a_partir_da_segunda_linha_com_saldo(tmp_path):
    """Valores e saldos em colunas de verdade, com datas de verdade."""
    caminho = escrever_xlsx(tmp_path / "extrato.xlsx", [
        ("Data", "Descrição", "Valor", "Saldo"),
        (date(2026, 1, 31), "Supermercado", -45.6, 1000.0),
        (date(2026, 2, 2), "Salário", 1500.0, 2500.0),
    ])
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        tipo_ficheiro=TipoFicheiro.xlsx,
        linha_inicio_dados=2,
        separador_decimal=".",  # irrelevante: as células chegam como números
        coluna_valor=2,
        coluna_saldo=3,
        tem_saldo=True,
    ))

    # As datas são lidas pelo ramo `hasattr(raw, "date")`: o `formato_data` do
    # perfil não é consultado. Os valores chegam como números e saem sem
    # qualquer conversão. Os saldos também: 1000,00 e 2500,00.
    assert resultado["transacoes"] == [
        {"data": date(2026, 1, 31), "descricao": "Supermercado",
         "valor": -45.6, "saldo": 1000.0},
        {"data": date(2026, 2, 2), "descricao": "Salário",
         "valor": 1500.0, "saldo": 2500.0},
    ]
    assert resultado["erros"] == []
    assert resultado["total_linhas"] == 2


def test_xlsx_com_data_invalida_na_terceira_linha(tmp_path):
    """Uma data escrita à mão no meio de datas de verdade dá erro só nessa linha."""
    caminho = escrever_xlsx(tmp_path / "extrato_com_data_invalida.xlsx", [
        ("Data", "Descrição", "Valor"),
        (date(2026, 1, 31), "Supermercado", -45.6),
        ("31/02/2026", "Café", -3.2),  # texto: dia 31 de fevereiro
        (date(2026, 2, 2), "Salário", 1500.0),
    ])
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        tipo_ficheiro=TipoFicheiro.xlsx,
        linha_inicio_dados=2,
        separador_decimal=".",
    ))

    # As linhas 2 e 4 passam; a linha 3 dá erro e nada mais. O erro não
    # interrompe a leitura: o ficheiro é lido até ao fim.
    assert [t["data"] for t in resultado["transacoes"]] == [
        date(2026, 1, 31), date(2026, 2, 2),
    ]
    assert resultado["erros"] == [{
        "linha": 3,
        "erro": "data inválida: '31/02/2026' (formato esperado: %d/%m/%Y)",
    }]
    # 2 transacções + 1 erro
    assert resultado["total_linhas"] == 3


# ---------------------------------------------------------------------------
# Secção G — a comissão (coluna fee) e o sinal com que é somada
# ---------------------------------------------------------------------------

def test_comissao_positiva_reduz_a_saida(tmp_path):
    """Uma comissão positiva, somada como vem, empurra o valor para zero.

    DEVIDA-TECNICA: D12e
    """
    caminho = escrever_csv(tmp_path / "comissao.csv", CSV_COM_COMISSAO)
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        linha_inicio_dados=2,
        coluna_fee=3,
    ))

    # Linha 2 do ficheiro: -50,00 + 1,50 = -48,50. Uma comissão de 1,50 numa
    # compra faz a compra parecer mais barata em 1,50.
    assert resultado["transacoes"][0]["valor"] == -48.5
    assert resultado["erros"] == []
    assert resultado["total_linhas"] == 3


def test_comissao_negativa_aumenta_a_saida(tmp_path):
    """Uma comissão negativa, somada como vem, aumenta a saída.

    DEVIDA-TECNICA: D12e
    """
    caminho = escrever_csv(tmp_path / "comissao.csv", CSV_COM_COMISSAO)
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        linha_inicio_dados=2,
        coluna_fee=3,
    ))

    # Linha 3 do ficheiro: -50,00 + (-1,50) = -51,50. Uma comissão de 1,50 numa
    # compra faz a compra parecer mais cara em 1,50.
    assert resultado["transacoes"][1]["valor"] == -51.5
    assert resultado["erros"] == []
    assert resultado["total_linhas"] == 3


def test_comissao_vazia_e_ignorada(tmp_path):
    """Uma célula de comissão vazia não mexe no valor.

    DEVIDA-TECNICA: D12e
    """
    caminho = escrever_csv(tmp_path / "comissao.csv", CSV_COM_COMISSAO)
    resultado = parse_ficheiro(caminho.read_bytes(), perfil(
        linha_inicio_dados=2,
        coluna_fee=3,
    ))

    # Linha 4 do ficheiro: a comissão está vazia, a guarda
    # `raw not in (None, "", "None")` não deixa entrar nada, e o valor fica
    # 20,00 + nada = 20,00.
    assert resultado["transacoes"][2]["valor"] == 20.0
    assert [t["descricao"] for t in resultado["transacoes"]] == [
        "Compra de ações", "Compra de ações", "Transferência",
    ]
    assert resultado["erros"] == []
    assert resultado["total_linhas"] == 3

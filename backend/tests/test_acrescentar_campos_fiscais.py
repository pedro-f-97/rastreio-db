"""Testes de `acrescentar_campos_fiscais`.

Uma BD de antes do relatório do IRS não tem `tipos_ativo.classificacao_fiscal`,
`ativos.pais`, `contas.pais` nem `subcategorias.juros_irs`. A função
acrescenta-as no arranque e depois de um restauro: os países ficam PT, nenhuma
subcategoria fica marcada como juros, e os tipos ficam fora do IRS, menos os
que têm os nomes que o primeiro uso cria e que entram no relatório (ETF, Ações
e Obrigações como valores mobiliários, Crypto como criptoativos).

A BD antiga é criada com o DDL da versão anterior, escrito à mão. Todos os
ficheiros ficam em `tmp_path`; a função recebe o caminho, e nenhum destes
testes usa a `engine` do módulo.
"""

import hashlib
import sqlite3

from sqlalchemy import create_engine

from database import Base, acrescentar_campos_fiscais

# O DDL das quatro tabelas antes dos campos fiscais (e o de `categorias`, a que
# as subcategorias apontam)
DDL_ANTIGO = [
    """CREATE TABLE tipos_ativo (
    id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    tem_unidades BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (nome)
)""",
    """CREATE TABLE ativos (
    id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    tipo_id INTEGER NOT NULL,
    simbolo VARCHAR(20),
    moeda VARCHAR(10) NOT NULL,
    notas VARCHAR(500),
    contabilizacao VARCHAR(12) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(tipo_id) REFERENCES tipos_ativo (id),
    UNIQUE (simbolo)
)""",
    """CREATE TABLE contas (
    id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    saldo_referencia FLOAT NOT NULL,
    data_referencia DATE NOT NULL,
    ativa BOOLEAN NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (nome)
)""",
    """CREATE TABLE categorias (
    id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    tipo VARCHAR(13) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (nome)
)""",
    """CREATE TABLE subcategorias (
    id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    trata_patrimonio BOOLEAN NOT NULL,
    categoria_id INTEGER NOT NULL,
    classe_despesa VARCHAR(14),
    PRIMARY KEY (id),
    FOREIGN KEY(categoria_id) REFERENCES categorias (id)
)""",
]

# IDs não seguidos, para que um ID renumerado se note
TIPOS = [
    (2, "ETF", 1),
    (4, "Ações", 1),
    (5, "Obrigações", 1),
    (8, "Crypto", 1),
    (9, "Ouro", 1),
    (12, "Arte", 0),
]
ATIVOS = [
    (3, "Vanguard All-World", 2, "VWCE", "EUR", None, "investimento"),
    (7, "Quadro", 12, None, "EUR", "na sala", "patrimonio"),
]
CONTAS = [
    (1, "Conta à ordem", 1500.0, "2025-01-01", 1),
    (6, "Trade Republic", 0.0, "2025-01-01", 1),
]
CATEGORIAS = [(1, "Receita", "receita"), (3, "Casa", "despesa")]
SUBCATEGORIAS = [
    (10, "Juros", 0, 1, None),
    (11, "Renda", 0, 3, "essencial"),
]

# O que cada linha ganha, pela ordem das colunas acrescentadas no fim
TIPOS_MIGRADOS = [
    (2, "ETF", 1, "valores_mobiliarios"),
    (4, "Ações", 1, "valores_mobiliarios"),
    (5, "Obrigações", 1, "valores_mobiliarios"),
    (8, "Crypto", 1, "criptoativos"),
    (9, "Ouro", 1, "fora"),
    (12, "Arte", 0, "fora"),
]
ATIVOS_MIGRADOS = [linha + ("PT",) for linha in ATIVOS]
CONTAS_MIGRADAS = [linha + ("PT",) for linha in CONTAS]
SUBCATEGORIAS_MIGRADAS = [linha + (0,) for linha in SUBCATEGORIAS]

TABELAS = ("tipos_ativo", "ativos", "contas", "subcategorias")


def criar_bd_antiga(caminho):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        for ddl in DDL_ANTIGO:
            con.execute(ddl)
        for tabela, semente in (
            ("tipos_ativo", TIPOS),
            ("ativos", ATIVOS),
            ("contas", CONTAS),
            ("categorias", CATEGORIAS),
            ("subcategorias", SUBCATEGORIAS),
        ):
            marcas = ", ".join("?" * len(semente[0]))
            con.executemany(f"INSERT INTO {tabela} VALUES ({marcas})", semente)
    finally:
        con.close()


def criar_bd_nova(caminho):
    motor = create_engine(f"sqlite:///{caminho}")
    try:
        Base.metadata.create_all(bind=motor)
    finally:
        motor.dispose()


def info_colunas(caminho, tabela):
    """(nome, tipo, not null, valor por omissão, pk) de cada coluna."""
    con = sqlite3.connect(caminho)
    try:
        return [linha[1:] for linha in con.execute(f"PRAGMA table_info({tabela})")]
    finally:
        con.close()


def linhas(caminho, tabela):
    con = sqlite3.connect(caminho)
    try:
        return con.execute(f"SELECT * FROM {tabela} ORDER BY id").fetchall()
    finally:
        con.close()


def executar(caminho, sql):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(sql)
    finally:
        con.close()


def md5(caminho):
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def test_acrescenta_as_colunas_e_preserva_as_linhas(tmp_path):
    """Cada tabela ganha a sua coluna no fim, e as linhas os mesmos IDs e valores.

    Cálculo à mão do que cada linha ganha:
      tipos_ativo:   ETF, Ações e Obrigações -> valores_mobiliarios;
                     Crypto -> criptoativos; Ouro e Arte -> fora
      ativos:        os 2 -> PT
      contas:        as 2 -> PT
      subcategorias: as 2 -> 0 (sem marca de juros, mesmo a que se chama Juros)
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    assert acrescentar_campos_fiscais(str(caminho)) is True

    assert [c[0] for c in info_colunas(caminho, "tipos_ativo")][-1] == "classificacao_fiscal"
    assert [c[0] for c in info_colunas(caminho, "ativos")][-1] == "pais"
    assert [c[0] for c in info_colunas(caminho, "contas")][-1] == "pais"
    assert [c[0] for c in info_colunas(caminho, "subcategorias")][-1] == "juros_irs"
    assert linhas(caminho, "tipos_ativo") == TIPOS_MIGRADOS
    assert linhas(caminho, "ativos") == ATIVOS_MIGRADOS
    assert linhas(caminho, "contas") == CONTAS_MIGRADAS
    assert linhas(caminho, "subcategorias") == SUBCATEGORIAS_MIGRADAS


def test_as_colunas_migradas_sao_iguais_as_do_modelo(tmp_path):
    """Uma BD migrada fica com as mesmas colunas, tipos, restrições e valores por
    omissão que uma BD criada pelo modelo, nas quatro tabelas.

    Cálculo à mão das colunas novas:
      classificacao_fiscal VARCHAR(19), NOT NULL, DEFAULT 'fora'
        (o nome mais comprido do enum, `valores_mobiliarios`, tem 19 letras)
      pais VARCHAR(2), NOT NULL, DEFAULT 'PT' (nos ativos e nas contas)
      juros_irs BOOLEAN, NOT NULL, DEFAULT 0
    """
    antiga = tmp_path / "antiga.db"
    nova = tmp_path / "nova.db"
    criar_bd_antiga(antiga)
    criar_bd_nova(nova)

    acrescentar_campos_fiscais(str(antiga))

    assert info_colunas(antiga, "tipos_ativo")[-1] == (
        "classificacao_fiscal",
        "VARCHAR(19)",
        1,
        "'fora'",
        0,
    )
    assert info_colunas(antiga, "ativos")[-1] == ("pais", "VARCHAR(2)", 1, "'PT'", 0)
    assert info_colunas(antiga, "contas")[-1] == ("pais", "VARCHAR(2)", 1, "'PT'", 0)
    assert info_colunas(antiga, "subcategorias")[-1] == ("juros_irs", "BOOLEAN", 1, "0", 0)
    for tabela in TABELAS:
        assert info_colunas(antiga, tabela) == info_colunas(nova, tabela)


def test_segunda_chamada_nao_escreve(tmp_path):
    """Idempotente: com as colunas, devolve False e o ficheiro fica igual."""
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    acrescentar_campos_fiscais(str(caminho))
    antes = md5(caminho)

    assert acrescentar_campos_fiscais(str(caminho)) is False
    assert md5(caminho) == antes


def test_segunda_chamada_nao_desfaz_a_classificacao_escolhida(tmp_path):
    """A classificação pelo nome só se escreve quando a coluna é acrescentada.

    Cálculo à mão: depois da migração, o ETF (id 2) passa a fora, à mão. Uma
    segunda chamada não acrescenta nada e não volta a classificar: o ETF
    continua fora.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    acrescentar_campos_fiscais(str(caminho))
    executar(caminho, "UPDATE tipos_ativo SET classificacao_fiscal = 'fora' WHERE id = 2")

    assert acrescentar_campos_fiscais(str(caminho)) is False
    assert linhas(caminho, "tipos_ativo")[0] == (2, "ETF", 1, "fora")


def test_acrescenta_so_as_colunas_que_faltam(tmp_path):
    """Com `contas.pais` já lá (escolhido DE na conta 6), acrescenta as outras
    três e não toca na que existe.

    Cálculo à mão: devolve True, porque acrescentou 3; as contas continuam com
    PT e DE; os tipos, os ativos e as subcategorias ficam como no primeiro teste.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    executar(caminho, "ALTER TABLE contas ADD COLUMN pais VARCHAR(2) NOT NULL DEFAULT 'PT'")
    executar(caminho, "UPDATE contas SET pais = 'DE' WHERE id = 6")

    assert acrescentar_campos_fiscais(str(caminho)) is True

    assert linhas(caminho, "contas") == [CONTAS[0] + ("PT",), CONTAS[1] + ("DE",)]
    assert linhas(caminho, "tipos_ativo") == TIPOS_MIGRADOS
    assert linhas(caminho, "ativos") == ATIVOS_MIGRADOS
    assert linhas(caminho, "subcategorias") == SUBCATEGORIAS_MIGRADAS


def test_bd_criada_pelo_modelo_nao_e_tocada(tmp_path):
    """Uma BD nova já tem as colunas: nada a fazer, ficheiro igual."""
    caminho = tmp_path / "nova.db"
    criar_bd_nova(caminho)
    antes = md5(caminho)

    assert acrescentar_campos_fiscais(str(caminho)) is False
    assert md5(caminho) == antes


def test_ficheiro_sem_as_tabelas_nao_e_tocado(tmp_path):
    """Sem as tabelas (um ficheiro que não é do Rastreio-DB), não escreve."""
    caminho = tmp_path / "outra.db"
    executar(caminho, "CREATE TABLE outra (id INTEGER)")
    antes = md5(caminho)

    assert acrescentar_campos_fiscais(str(caminho)) is False
    assert md5(caminho) == antes

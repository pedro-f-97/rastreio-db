"""Testes de `acrescentar_classe_despesa`.

Uma BD de antes da classificação das despesas não tem
`subcategorias.classe_despesa`. A função acrescenta-a no arranque e depois de um
restauro, vazia (sem classificação) nas subcategorias que já lá estão.

A BD antiga é criada com o DDL de `subcategorias` da versão anterior, escrito à
mão. Todos os ficheiros ficam em `tmp_path`; a função recebe o caminho, e
nenhum destes testes usa a `engine` do módulo.
"""

import hashlib
import sqlite3

from sqlalchemy import create_engine

from database import Base, acrescentar_classe_despesa

# O DDL de `subcategorias` antes da classificação, sem `classe_despesa`
DDL_ANTIGO = """CREATE TABLE subcategorias (
    id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    trata_patrimonio BOOLEAN NOT NULL,
    categoria_id INTEGER NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(categoria_id) REFERENCES categorias (id)
)"""

# Duas subcategorias com IDs não seguidos
SEMENTE = [
    (2, "Seguro", 0, 1),
    (7, "Compra Twingo", 1, 1),
]
# As mesmas linhas com a 5.ª coluna (`classe_despesa`) a NULL
COM_CLASSE_DESPESA = [linha + (None,) for linha in SEMENTE]


def criar_bd_antiga(caminho):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(DDL_ANTIGO)
        con.executemany("INSERT INTO subcategorias VALUES (?, ?, ?, ?)", SEMENTE)
    finally:
        con.close()


def criar_bd_nova(caminho):
    motor = create_engine(f"sqlite:///{caminho}")
    try:
        Base.metadata.create_all(bind=motor)
    finally:
        motor.dispose()


def info_colunas(caminho):
    """(nome, tipo, not null, valor por omissão, pk) de cada coluna."""
    con = sqlite3.connect(caminho)
    try:
        return [linha[1:] for linha in con.execute("PRAGMA table_info(subcategorias)")]
    finally:
        con.close()


def linhas(caminho):
    con = sqlite3.connect(caminho)
    try:
        return con.execute("SELECT * FROM subcategorias ORDER BY id").fetchall()
    finally:
        con.close()


def md5(caminho):
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def test_acrescenta_a_coluna_e_preserva_as_linhas(tmp_path):
    """A coluna entra no fim; as 2 subcategorias ficam com os mesmos IDs e
    valores, e com `classe_despesa` a NULL.

    Cálculo à mão: as 4 colunas do DDL antigo mais `classe_despesa` dão 5, e
    cada linha ganha só um 5.º valor, None.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    assert acrescentar_classe_despesa(str(caminho)) is True

    assert [c[0] for c in info_colunas(caminho)] == [
        "id",
        "nome",
        "trata_patrimonio",
        "categoria_id",
        "classe_despesa",
    ]
    assert linhas(caminho) == COM_CLASSE_DESPESA


def test_a_coluna_migrada_e_igual_a_do_modelo(tmp_path):
    """Uma BD migrada fica com as mesmas colunas, tipos e restrições que uma BD
    criada pelo modelo: `classe_despesa VARCHAR(14)`, que pode ser NULL.

    Cálculo à mão: o nome mais comprido do enum, `extraordinaria`, tem 14 letras.
    """
    antiga = tmp_path / "antiga.db"
    nova = tmp_path / "nova.db"
    criar_bd_antiga(antiga)
    criar_bd_nova(nova)

    acrescentar_classe_despesa(str(antiga))

    assert info_colunas(antiga)[-1] == ("classe_despesa", "VARCHAR(14)", 0, None, 0)
    assert info_colunas(antiga) == info_colunas(nova)


def test_segunda_chamada_nao_escreve(tmp_path):
    """Idempotente: com a coluna, devolve False e o ficheiro fica igual."""
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    acrescentar_classe_despesa(str(caminho))
    antes = md5(caminho)

    assert acrescentar_classe_despesa(str(caminho)) is False
    assert md5(caminho) == antes


def test_bd_criada_pelo_modelo_nao_e_tocada(tmp_path):
    """Uma BD nova já tem a coluna: nada a fazer, ficheiro igual."""
    caminho = tmp_path / "nova.db"
    criar_bd_nova(caminho)
    antes = md5(caminho)

    assert acrescentar_classe_despesa(str(caminho)) is False
    assert md5(caminho) == antes


def test_ficheiro_sem_a_tabela_nao_e_tocado(tmp_path):
    """Sem `subcategorias` (um ficheiro que não é do Rastreio-DB), não escreve."""
    caminho = tmp_path / "outra.db"
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute("CREATE TABLE outra (id INTEGER)")
    finally:
        con.close()
    antes = md5(caminho)

    assert acrescentar_classe_despesa(str(caminho)) is False
    assert md5(caminho) == antes

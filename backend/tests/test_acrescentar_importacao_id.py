"""Testes de `acrescentar_importacao_id`.

Uma BD de antes do histórico de importações não tem `transacoes.importacao_id`.
A função acrescenta-a no arranque e depois de um restauro, vazia nas
transacções que já lá estão.

A BD antiga é criada com o DDL de `transacoes` da versão anterior, escrito à
mão. Todos os ficheiros ficam em `tmp_path`; a função recebe o caminho, e
nenhum destes testes usa a `engine` do módulo.
"""

import hashlib
import sqlite3

from sqlalchemy import create_engine

from database import Base, acrescentar_importacao_id

# O DDL de `transacoes` depois da remoção de `reembolso`, sem `importacao_id`
DDL_ANTIGO = """CREATE TABLE transacoes (
    id INTEGER NOT NULL,
    data DATE NOT NULL,
    descricao VARCHAR(255) NOT NULL,
    valor FLOAT NOT NULL,
    saldo FLOAT,
    notas VARCHAR(500),
    categoria_id INTEGER,
    subcategoria_id INTEGER,
    conta_id INTEGER,
    PRIMARY KEY (id)
)"""

# Duas transacções com IDs não seguidos
SEMENTE = [
    (3, "2025-03-18", "Reembolso seguros", 50.0, None, "nota", None, None, 1),
    (8, "2025-03-20", "Renda", -300.0, 900.0, None, None, None, 1),
]
# As mesmas linhas com a 10.ª coluna (`importacao_id`) a NULL
COM_IMPORTACAO_ID = [linha + (None,) for linha in SEMENTE]


def criar_bd_antiga(caminho):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(DDL_ANTIGO)
        con.executemany("INSERT INTO transacoes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", SEMENTE)
    finally:
        con.close()


def colunas(caminho):
    con = sqlite3.connect(caminho)
    try:
        return [linha[1] for linha in con.execute("PRAGMA table_info(transacoes)")]
    finally:
        con.close()


def linhas(caminho):
    con = sqlite3.connect(caminho)
    try:
        return con.execute("SELECT * FROM transacoes ORDER BY id").fetchall()
    finally:
        con.close()


def chaves_estrangeiras(caminho):
    con = sqlite3.connect(caminho)
    try:
        return [
            (linha[3], linha[2], linha[4])
            for linha in con.execute("PRAGMA foreign_key_list(transacoes)")
        ]
    finally:
        con.close()


def md5(caminho):
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def test_acrescenta_a_coluna_e_preserva_as_linhas(tmp_path):
    """A coluna entra no fim; as 2 transacções ficam com os mesmos IDs e
    valores, e com `importacao_id` a NULL.

    Cálculo à mão: as 9 colunas do DDL antigo mais `importacao_id` dão 10, e
    cada linha ganha só um 10.º valor, None.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    assert acrescentar_importacao_id(str(caminho)) is True

    assert colunas(caminho) == [
        "id",
        "data",
        "descricao",
        "valor",
        "saldo",
        "notas",
        "categoria_id",
        "subcategoria_id",
        "conta_id",
        "importacao_id",
    ]
    assert linhas(caminho) == COM_IMPORTACAO_ID


def test_a_coluna_aponta_para_importacoes(tmp_path):
    """A coluna é uma chave estrangeira para `importacoes.id`, como no modelo.

    Cálculo à mão: o DDL antigo não tem chaves; a única é a acrescentada.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    acrescentar_importacao_id(str(caminho))

    assert chaves_estrangeiras(caminho) == [("importacao_id", "importacoes", "id")]


def test_segunda_chamada_nao_escreve(tmp_path):
    """Idempotente: com a coluna, devolve False e o ficheiro fica igual."""
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    acrescentar_importacao_id(str(caminho))
    antes = md5(caminho)

    assert acrescentar_importacao_id(str(caminho)) is False
    assert md5(caminho) == antes


def test_bd_criada_pelo_modelo_nao_e_tocada(tmp_path):
    """Uma BD nova já tem a coluna: nada a fazer, ficheiro igual."""
    caminho = tmp_path / "nova.db"
    motor = create_engine(f"sqlite:///{caminho}")
    try:
        Base.metadata.create_all(bind=motor)
    finally:
        motor.dispose()
    antes = md5(caminho)

    assert "importacao_id" in colunas(caminho)
    assert acrescentar_importacao_id(str(caminho)) is False
    assert md5(caminho) == antes

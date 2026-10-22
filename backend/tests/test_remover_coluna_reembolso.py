"""Testes de `remover_coluna_reembolso`.

A marca de reembolso foi retirada do modelo. Numa BD antiga, a coluna
`transacoes.reembolso` é `NOT NULL` sem valor por omissão: enquanto lá estiver,
uma transacção gravada pelo modelo (que já não a preenche) é recusada. A função
apaga-a no arranque e depois de um restauro.

A BD antiga é criada com o DDL que a BD real tem, escrito à mão. Todos os
ficheiros ficam em `tmp_path`; a função recebe o caminho, e nenhum destes testes
usa a `engine` do módulo.
"""

import hashlib
import sqlite3

from sqlalchemy import create_engine

from database import Base, remover_coluna_reembolso

# O DDL de `transacoes` numa BD de antes do 4.3, tal como o SQLite o guarda
DDL_ANTIGO = """CREATE TABLE transacoes (
    id INTEGER NOT NULL,
    data DATE NOT NULL,
    descricao VARCHAR(255) NOT NULL,
    valor FLOAT NOT NULL,
    saldo FLOAT,
    reembolso BOOLEAN NOT NULL,
    notas VARCHAR(500),
    categoria_id INTEGER,
    subcategoria_id INTEGER,
    conta_id INTEGER,
    PRIMARY KEY (id)
)"""

# Duas transacções com IDs não seguidos, uma marcada como reembolso
SEMENTE = [
    (3, "2025-03-18", "Reembolso seguros", 50.0, None, 1, "nota", None, None, 1),
    (8, "2025-03-20", "Renda", -300.0, 900.0, 0, None, None, None, 1),
]
# As mesmas linhas sem a 6.ª coluna (`reembolso`), pela ordem de `SELECT *`
SEM_REEMBOLSO = [
    (3, "2025-03-18", "Reembolso seguros", 50.0, None, "nota", None, None, 1),
    (8, "2025-03-20", "Renda", -300.0, 900.0, None, None, None, 1),
]


def criar_bd_antiga(caminho):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(DDL_ANTIGO)
        con.executemany("INSERT INTO transacoes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", SEMENTE)
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


def inserir_sem_reembolso(caminho):
    """O INSERT que o modelo passa a fazer: sem a coluna `reembolso`."""
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(
            "INSERT INTO transacoes (id, data, descricao, valor) "
            "VALUES (9, '2025-03-25', 'Café', -0.8)"
        )
    finally:
        con.close()


def md5(caminho):
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def test_bd_antiga_recusa_uma_transacao_sem_reembolso(tmp_path):
    """O motivo da função: com a coluna, o INSERT do modelo novo falha."""
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    try:
        inserir_sem_reembolso(caminho)
    except sqlite3.IntegrityError as erro:
        assert str(erro) == "NOT NULL constraint failed: transacoes.reembolso"
    else:
        raise AssertionError("o INSERT sem reembolso devia ter falhado")


def test_remove_a_coluna_e_preserva_as_linhas(tmp_path):
    """A coluna sai; as 2 transacções ficam com os mesmos IDs e valores.

    Cálculo à mão: as 10 colunas do DDL antigo menos `reembolso` dão 9, e cada
    linha perde só o 6.º valor (1 e 0). Depois, o INSERT sem `reembolso` passa:
    3 transacções.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    assert remover_coluna_reembolso(str(caminho)) is True

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
    ]
    assert linhas(caminho) == SEM_REEMBOLSO
    inserir_sem_reembolso(caminho)
    assert len(linhas(caminho)) == 3


def test_segunda_chamada_nao_escreve(tmp_path):
    """Idempotente: sem a coluna, devolve False e o ficheiro fica igual."""
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    remover_coluna_reembolso(str(caminho))
    antes = md5(caminho)

    assert remover_coluna_reembolso(str(caminho)) is False
    assert md5(caminho) == antes


def test_bd_criada_pelo_modelo_nao_e_tocada(tmp_path):
    """Uma BD nova já não tem a coluna: nada a fazer, ficheiro igual."""
    caminho = tmp_path / "nova.db"
    motor = create_engine(f"sqlite:///{caminho}")
    try:
        Base.metadata.create_all(bind=motor)
    finally:
        motor.dispose()
    antes = md5(caminho)

    assert "reembolso" not in colunas(caminho)
    assert remover_coluna_reembolso(str(caminho)) is False
    assert md5(caminho) == antes

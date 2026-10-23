"""Testes de `acrescentar_transacao_manual`.

Uma BD de antes das transacções manuais não tem `transacoes.manual`. A função
acrescenta-a no arranque e depois de um restauro, a 0 (importada) nas
transacções que já lá estão.

A BD antiga é criada com o DDL de `transacoes` da versão anterior, escrito à
mão. Todos os ficheiros ficam em `tmp_path`; a função recebe o caminho, e
nenhum destes testes usa a `engine` do módulo.
"""

import hashlib
import sqlite3

from sqlalchemy import create_engine

from database import Base, acrescentar_transacao_manual

# O DDL de `transacoes` antes das transacções manuais, sem `manual`
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
    importacao_id INTEGER,
    PRIMARY KEY (id)
)"""

# Duas transacções com IDs não seguidos, uma de antes do histórico de importações
SEMENTE = [
    (3, "2025-05-13", "Compra", -12.5, None, "nota", None, None, 1, None),
    (8, "2025-06-11", "Transferência", -10.0, 990.0, None, None, None, 1, 4),
]
# As mesmas linhas com a 11.ª coluna (`manual`) a 0
COM_MANUAL = [linha + (0,) for linha in SEMENTE]


def criar_bd_antiga(caminho):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(DDL_ANTIGO)
        con.executemany("INSERT INTO transacoes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", SEMENTE)
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
        return [linha[1:] for linha in con.execute("PRAGMA table_info(transacoes)")]
    finally:
        con.close()


def linhas(caminho):
    con = sqlite3.connect(caminho)
    try:
        return con.execute("SELECT * FROM transacoes ORDER BY id").fetchall()
    finally:
        con.close()


def md5(caminho):
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def test_acrescenta_a_coluna_e_preserva_as_linhas(tmp_path):
    """A coluna entra no fim; as 2 transacções ficam com os mesmos IDs e
    valores, e com `manual` a 0.

    Cálculo à mão: as 10 colunas do DDL antigo mais `manual` dão 11, e cada
    linha ganha só um 11.º valor, 0.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    assert acrescentar_transacao_manual(str(caminho)) is True

    assert [c[0] for c in info_colunas(caminho)][-2:] == ["importacao_id", "manual"]
    assert len(info_colunas(caminho)) == 11
    assert linhas(caminho) == COM_MANUAL


def test_a_coluna_migrada_e_igual_a_do_modelo(tmp_path):
    """Uma BD migrada fica com as mesmas colunas, tipos e restrições que uma BD
    criada pelo modelo: `manual BOOLEAN DEFAULT 0 NOT NULL`."""
    antiga = tmp_path / "antiga.db"
    nova = tmp_path / "nova.db"
    criar_bd_antiga(antiga)
    criar_bd_nova(nova)

    acrescentar_transacao_manual(str(antiga))

    assert info_colunas(antiga)[-1] == ("manual", "BOOLEAN", 1, "0", 0)
    assert info_colunas(antiga) == info_colunas(nova)


def test_segunda_chamada_nao_escreve(tmp_path):
    """Idempotente: com a coluna, devolve False e o ficheiro fica igual."""
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    acrescentar_transacao_manual(str(caminho))
    antes = md5(caminho)

    assert acrescentar_transacao_manual(str(caminho)) is False
    assert md5(caminho) == antes


def test_bd_criada_pelo_modelo_nao_e_tocada(tmp_path):
    """Uma BD nova já tem a coluna: nada a fazer, ficheiro igual."""
    caminho = tmp_path / "nova.db"
    criar_bd_nova(caminho)
    antes = md5(caminho)

    assert acrescentar_transacao_manual(str(caminho)) is False
    assert md5(caminho) == antes


def test_ficheiro_sem_a_tabela_nao_e_tocado(tmp_path):
    """Sem `transacoes` (um ficheiro que não é do Rastreio-DB), não escreve."""
    caminho = tmp_path / "outra.db"
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute("CREATE TABLE outra (id INTEGER)")
    finally:
        con.close()
    antes = md5(caminho)

    assert acrescentar_transacao_manual(str(caminho)) is False
    assert md5(caminho) == antes

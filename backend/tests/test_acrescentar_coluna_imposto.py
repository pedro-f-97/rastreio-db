"""Testes de `acrescentar_coluna_imposto`.

Uma BD de antes da coluna de imposto não tem `perfis_importacao.coluna_imposto`.
A função acrescenta-a no arranque e depois de um restauro, a NULL (sem coluna
de imposto) nos perfis que já lá estão.

A BD antiga é criada com o DDL de `perfis_importacao` da versão anterior,
escrito à mão. Todos os ficheiros ficam em `tmp_path`; a função recebe o
caminho, e nenhum destes testes usa a `engine` do módulo.
"""

import hashlib
import sqlite3

from sqlalchemy import create_engine

from database import Base, acrescentar_coluna_imposto

# O DDL de `perfis_importacao` antes da coluna de imposto
DDL_ANTIGO = """CREATE TABLE perfis_importacao (
    id INTEGER NOT NULL,
    nome VARCHAR(100) NOT NULL,
    tipo_ficheiro VARCHAR(4) NOT NULL,
    linha_inicio_dados INTEGER NOT NULL,
    coluna_data INTEGER NOT NULL,
    formato_data VARCHAR(50) NOT NULL,
    coluna_descricao INTEGER NOT NULL,
    modo_valor VARCHAR(12) NOT NULL,
    coluna_valor INTEGER,
    coluna_debito INTEGER,
    coluna_credito INTEGER,
    separador_decimal VARCHAR(1) NOT NULL,
    tem_saldo BOOLEAN NOT NULL,
    coluna_saldo INTEGER,
    coluna_fee INTEGER,
    conta_id INTEGER,
    PRIMARY KEY (id),
    UNIQUE (nome),
    FOREIGN KEY(conta_id) REFERENCES contas (id)
)"""

# Dois perfis com IDs não seguidos, um deles com comissão, como o da TR
SEMENTE = [
    (
        2,
        "ActivoBank",
        "xlsx",
        9,
        0,
        "%Y-%m-%d",
        2,
        "coluna_unica",
        3,
        None,
        None,
        ".",
        1,
        4,
        None,
        1,
    ),
    (
        5,
        "TradeRepublic",
        "csv",
        2,
        1,
        "%Y-%m-%d",
        17,
        "coluna_unica",
        10,
        None,
        None,
        ".",
        0,
        None,
        11,
        2,
    ),
]
# As mesmas linhas com a 17.ª coluna (`coluna_imposto`) a NULL
COM_IMPOSTO = [linha + (None,) for linha in SEMENTE]


def criar_bd_antiga(caminho):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(DDL_ANTIGO)
        con.executemany(f"INSERT INTO perfis_importacao VALUES ({', '.join('?' * 16)})", SEMENTE)
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
        return [linha[1:] for linha in con.execute("PRAGMA table_info(perfis_importacao)")]
    finally:
        con.close()


def linhas(caminho):
    con = sqlite3.connect(caminho)
    try:
        return con.execute("SELECT * FROM perfis_importacao ORDER BY id").fetchall()
    finally:
        con.close()


def md5(caminho):
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def test_acrescenta_a_coluna_e_preserva_as_linhas(tmp_path):
    """A coluna entra no fim; os 2 perfis ficam com os mesmos IDs e valores, e
    com `coluna_imposto` a NULL.

    Cálculo à mão: as 16 colunas do DDL antigo mais `coluna_imposto` dão 17, e
    cada linha ganha só um 17.º valor, NULL.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)

    assert acrescentar_coluna_imposto(str(caminho)) is True

    assert [c[0] for c in info_colunas(caminho)][-2:] == ["conta_id", "coluna_imposto"]
    assert len(info_colunas(caminho)) == 17
    assert linhas(caminho) == COM_IMPOSTO


def test_a_coluna_migrada_e_igual_a_do_modelo(tmp_path):
    """Uma BD migrada fica com as mesmas colunas, tipos e restrições que uma BD
    criada pelo modelo: `coluna_imposto INTEGER`, que pode ser NULL."""
    antiga = tmp_path / "antiga.db"
    nova = tmp_path / "nova.db"
    criar_bd_antiga(antiga)
    criar_bd_nova(nova)

    acrescentar_coluna_imposto(str(antiga))

    assert info_colunas(antiga)[-1] == ("coluna_imposto", "INTEGER", 0, None, 0)
    assert info_colunas(antiga) == info_colunas(nova)


def test_segunda_chamada_nao_escreve(tmp_path):
    """Idempotente: com a coluna, devolve False e o ficheiro fica igual."""
    caminho = tmp_path / "antiga.db"
    criar_bd_antiga(caminho)
    acrescentar_coluna_imposto(str(caminho))
    antes = md5(caminho)

    assert acrescentar_coluna_imposto(str(caminho)) is False
    assert md5(caminho) == antes


def test_bd_criada_pelo_modelo_nao_e_tocada(tmp_path):
    """Uma BD nova já tem a coluna: nada a fazer, ficheiro igual."""
    caminho = tmp_path / "nova.db"
    criar_bd_nova(caminho)
    antes = md5(caminho)

    assert acrescentar_coluna_imposto(str(caminho)) is False
    assert md5(caminho) == antes


def test_ficheiro_sem_a_tabela_nao_e_tocado(tmp_path):
    """Sem `perfis_importacao` (um ficheiro que não é do Rastreio-DB), não escreve."""
    caminho = tmp_path / "outra.db"
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute("CREATE TABLE outra (id INTEGER)")
    finally:
        con.close()
    antes = md5(caminho)

    assert acrescentar_coluna_imposto(str(caminho)) is False
    assert md5(caminho) == antes

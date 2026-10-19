"""Testes de `reparar_fk_ativos` (D1a).

A BD partida é criada pela fixture `criar_bd_com_fk_partida` (conftest), que
reproduz a migração que a partiu. Todos os ficheiros ficam em `tmp_path`; a
função recebe o caminho, e nenhum destes testes usa a `engine` do módulo.

Os valores esperados estão escritos à mão, a partir da semente da fixture:
3 preços (5 e 9 do ativo 3, 12 do ativo 7) e 2 movimentos (2 do ativo 3, 8 do
ativo 7).
"""

import sqlite3
from contextlib import contextmanager

import pytest

import database
from database import Base, reparar_fk_ativos

# A semente da fixture, linha a linha, como o sqlite3 a devolve (datas em
# texto, valores em float).
PRECOS = [
    (5, 3, "2024-01-31", 10.5),
    (9, 3, "2024-02-29", 11.25),
    (12, 7, "2024-01-31", 2.0),
]
MOVIMENTOS = [
    (2, 3, None, "compra", "2024-01-10", 4.0, 10.0, 1.5, 41.5, None),
    (8, 7, None, "compra", "2024-01-15", 10.0, 2.0, 0.0, 20.0, "nota"),
]


@contextmanager
def ligar(caminho, chaves=False):
    """Ligação em autocommit, fechada à saída (o `with` do sqlite3 não fecha)."""
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        if chaves:
            con.execute("PRAGMA foreign_keys = ON")
        yield con
    finally:
        con.close()


def ddl(caminho, tabela):
    with ligar(caminho) as con:
        return con.execute(
            "SELECT sql FROM sqlite_master WHERE name = ?", (tabela,)
        ).fetchone()[0]


def linhas(caminho, tabela):
    with ligar(caminho) as con:
        return con.execute(f"SELECT * FROM {tabela} ORDER BY id").fetchall()


def violacoes(caminho):
    with ligar(caminho) as con:
        return con.execute("PRAGMA foreign_key_check").fetchall()


@pytest.fixture
def bd_partida(tmp_path, criar_bd_com_fk_partida):
    caminho = tmp_path / "partida.db"
    criar_bd_com_fk_partida(caminho)
    return caminho


def test_a_fixture_reproduz_o_schema_partido(bd_partida):
    """Pré-condição: sem isto, os outros testes não provam nada.

    Cálculo à mão: as duas tabelas apontam para `ativos_old`, que não existe,
    logo cada linha delas é uma violação: 3 preços + 2 movimentos = 5. Com a
    pragma ligada, acrescentar um preço falha a procurar a tabela fantasma —
    é o erro registado na D1a.
    """
    assert 'REFERENCES "ativos_old"' in ddl(bd_partida, "precos_ativo")
    assert 'REFERENCES "ativos_old"' in ddl(bd_partida, "movimentos_ativo")
    assert len(violacoes(bd_partida)) == 5

    with ligar(bd_partida, chaves=True) as con:
        with pytest.raises(sqlite3.OperationalError, match="no such table: main.ativos_old"):
            con.execute("INSERT INTO precos_ativo VALUES (20, 7, '2024-02-29', 2.5)")


def test_reparar_corrige_as_referencias_e_preserva_os_dados(bd_partida):
    """As duas tabelas passam a apontar para `ativos`, com as mesmas linhas.

    Cálculo à mão: devolve as duas tabelas, pela ordem de
    `TABELAS_COM_FK_PARA_ATIVOS_OLD`; nenhum DDL menciona `ativos_old`; as
    linhas são as da semente, com os mesmos IDs; e não fica nenhuma violação.
    """
    assert reparar_fk_ativos(str(bd_partida)) == ["precos_ativo", "movimentos_ativo"]

    for tabela in ("precos_ativo", "movimentos_ativo"):
        assert "ativos_old" not in ddl(bd_partida, tabela)
        assert "REFERENCES ativos" in ddl(bd_partida, tabela)
    assert linhas(bd_partida, "precos_ativo") == PRECOS
    assert linhas(bd_partida, "movimentos_ativo") == MOVIMENTOS
    assert violacoes(bd_partida) == []
    with ligar(bd_partida) as con:
        assert con.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


def test_reparar_mantem_a_unicidade_de_ativo_e_data(bd_partida):
    """O DDL é o da própria tabela: a `uq_preco_ativo_data` não se perde.

    Cálculo à mão: o ativo 3 já tem preço em 2024-01-31 (id 5), logo um
    segundo preço nessa data é recusado.
    """
    reparar_fk_ativos(str(bd_partida))

    with ligar(bd_partida) as con:
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            con.execute("INSERT INTO precos_ativo VALUES (20, 3, '2024-01-31', 1.0)")


def test_com_a_pragma_ligada_a_bd_reparada_protege_os_ativos(bd_partida):
    """O que a D1a impedia passa a funcionar.

    Cálculo à mão, com `PRAGMA foreign_keys = ON`:
      * um preço novo para o ativo 7, que existe, entra;
      * um preço para o ativo 99, que não existe, é recusado;
      * apagar o ativo 7, que tem o preço 12 e o movimento 8, é recusado.
    Antes da reparação, este último `DELETE` passava e deixava órfãos (D1a).
    """
    reparar_fk_ativos(str(bd_partida))

    with ligar(bd_partida, chaves=True) as con:
        con.execute("INSERT INTO precos_ativo VALUES (20, 7, '2024-02-29', 2.5)")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            con.execute("INSERT INTO precos_ativo VALUES (21, 99, '2024-02-29', 1.0)")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            con.execute("DELETE FROM ativos WHERE id = 7")


def test_reparar_duas_vezes_nao_escreve_na_segunda(bd_partida):
    """Idempotente: a segunda chamada não encontra `ativos_old` e não toca no ficheiro."""
    reparar_fk_ativos(str(bd_partida))
    bytes_depois_da_primeira = bd_partida.read_bytes()

    assert reparar_fk_ativos(str(bd_partida)) == []
    assert bd_partida.read_bytes() == bytes_depois_da_primeira


def test_bd_criada_pelo_modelo_nao_e_tocada(tmp_path):
    """Uma BD nova já tem o schema certo: nada a reparar, nenhum byte muda."""
    from sqlalchemy import create_engine

    caminho = tmp_path / "nova.db"
    engine = create_engine(f"sqlite:///{caminho}")
    Base.metadata.create_all(bind=engine)
    engine.dispose()
    bytes_antes = caminho.read_bytes()

    assert reparar_fk_ativos(str(caminho)) == []
    assert caminho.read_bytes() == bytes_antes


def test_falha_a_meio_nao_deixa_nada_feito(bd_partida, monkeypatch):
    """Se a segunda tabela falhar, a primeira, já recriada, volta atrás.

    A falha é provocada depois de `movimentos_ativo` ser recriada, quando
    `precos_ativo` já o foi na mesma transacção. Cálculo à mão: a excepção
    chega a quem chamou, os dois DDL ficam byte a byte como antes, as linhas
    são as da semente, e as 5 violações continuam lá.
    """
    ddl_precos = ddl(bd_partida, "precos_ativo")
    ddl_movimentos = ddl(bd_partida, "movimentos_ativo")
    recriar_real = database._recriar_com_fk_para_ativos

    def recriar_e_falhar_na_segunda(con, nome, sql):
        recriar_real(con, nome, sql)
        if nome == "movimentos_ativo":
            raise RuntimeError("falha simulada")

    monkeypatch.setattr(database, "_recriar_com_fk_para_ativos", recriar_e_falhar_na_segunda)

    with pytest.raises(RuntimeError, match="falha simulada"):
        reparar_fk_ativos(str(bd_partida))

    assert ddl(bd_partida, "precos_ativo") == ddl_precos
    assert ddl(bd_partida, "movimentos_ativo") == ddl_movimentos
    assert linhas(bd_partida, "precos_ativo") == PRECOS
    assert linhas(bd_partida, "movimentos_ativo") == MOVIMENTOS
    assert len(violacoes(bd_partida)) == 5


def test_ativos_old_noutra_tabela_e_recusado_sem_mexer_em_nada(bd_partida):
    """Só se sabe reparar as duas tabelas conhecidas; outra é erro, antes de escrever.

    Cálculo à mão: com uma terceira tabela a apontar para `ativos_old`, a
    função levanta a nomeá-la, e as duas tabelas conhecidas ficam por reparar.
    """
    with ligar(bd_partida) as con:
        con.execute("CREATE TABLE outra (id INTEGER PRIMARY KEY, "
                    "ativo_id INTEGER REFERENCES ativos_old(id))")
    ddl_precos = ddl(bd_partida, "precos_ativo")

    with pytest.raises(RuntimeError, match=r"\['outra'\]"):
        reparar_fk_ativos(str(bd_partida))

    assert ddl(bd_partida, "precos_ativo") == ddl_precos

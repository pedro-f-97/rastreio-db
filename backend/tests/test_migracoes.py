"""Testes de `aplicar_migracoes` e de `colunas_em_falta`.

A BD guarda em `PRAGMA user_version` a última migração que levou. As migrações
verdadeiras são trocadas por funções falsas com `monkeypatch`, que registam
quando correm, para que os testes não dependam do que cada uma faz (isso está
em `test_reparar_fk_ativos.py` e `test_remover_coluna_reembolso.py`).

Todos os ficheiros ficam em `tmp_path`; as funções recebem o caminho, e nenhum
destes testes usa a `engine` do módulo.
"""

import hashlib
import sqlite3

import pytest
from sqlalchemy import create_engine

import database
from database import Base, aplicar_migracoes, colunas_em_falta


def versao(caminho):
    con = sqlite3.connect(caminho)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


def marcar(caminho, numero):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(f"PRAGMA user_version = {numero}")
    finally:
        con.close()


def criar_bd_do_modelo(caminho):
    motor = create_engine(f"sqlite:///{caminho}")
    try:
        Base.metadata.create_all(bind=motor)
    finally:
        motor.dispose()


def md5(caminho):
    return hashlib.md5(caminho.read_bytes()).hexdigest()


@pytest.fixture
def tres_migracoes(monkeypatch):
    """Três migrações falsas; devolve a lista onde cada uma regista o seu número.

    A 1 e a 3 dizem que mudaram alguma coisa, a 2 que não.
    """
    corridas = []

    def migracao(numero, mudou):
        def correr(caminho):
            corridas.append(numero)
            return mudou

        return correr

    monkeypatch.setattr(
        database,
        "MIGRACOES",
        (
            ("um", migracao(1, True)),
            ("dois", migracao(2, False)),
            ("três", migracao(3, True)),
        ),
    )
    return corridas


def test_as_migracoes_verdadeiras_sao_tres():
    """A ordem das migrações que já saíram não pode mudar.

    Cálculo à mão: a 1 é a reparação das chaves para `ativos_old`, a 2 a remoção
    de `transacoes.reembolso`, a 3 a coluna `transacoes.importacao_id`. Uma BD
    na versão 3 já levou as três.
    """
    assert [funcao for _, funcao in database.MIGRACOES] == [
        database.reparar_fk_ativos,
        database.remover_coluna_reembolso,
        database.acrescentar_importacao_id,
    ]


def test_bd_na_versao_zero_corre_todas_por_ordem(tmp_path, tres_migracoes):
    """Uma BD sem versão (todas as de antes do 1.1) corre as três, por ordem.

    Cálculo à mão: correm 1, 2 e 3; só a 1 e a 3 dizem que mudaram, e a versão
    fica em 3.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_do_modelo(caminho)
    assert versao(caminho) == 0

    assert aplicar_migracoes(str(caminho)) == ["um", "três"]
    assert tres_migracoes == [1, 2, 3]
    assert versao(caminho) == 3


def test_bd_na_versao_um_so_corre_as_seguintes(tmp_path, tres_migracoes):
    """Cálculo à mão: na versão 1, faltam a 2 e a 3; a versão fica em 3."""
    caminho = tmp_path / "v1.db"
    criar_bd_do_modelo(caminho)
    marcar(caminho, 1)

    assert aplicar_migracoes(str(caminho)) == ["três"]
    assert tres_migracoes == [2, 3]
    assert versao(caminho) == 3


def test_bd_na_ultima_versao_nao_e_tocada(tmp_path, tres_migracoes):
    """Cálculo à mão: na versão 3 não falta nenhuma; o ficheiro fica igual."""
    caminho = tmp_path / "v3.db"
    criar_bd_do_modelo(caminho)
    marcar(caminho, 3)
    antes = md5(caminho)

    assert aplicar_migracoes(str(caminho)) == []
    assert tres_migracoes == []
    assert md5(caminho) == antes


def test_bd_de_uma_versao_mais_recente_nao_e_tocada(tmp_path, tres_migracoes):
    """Um backup de uma aplicação mais nova (versão 5 com 3 migrações).

    Fixa o comportamento actual: nada corre e a versão não desce, mas também
    não há aviso. Se faltar alguma coluna, quem a apanha é `colunas_em_falta`.
    """
    caminho = tmp_path / "v5.db"
    criar_bd_do_modelo(caminho)
    marcar(caminho, 5)

    assert aplicar_migracoes(str(caminho)) == []
    assert tres_migracoes == []
    assert versao(caminho) == 5


def test_uma_migracao_que_falha_para_as_seguintes(tmp_path, monkeypatch):
    """A 2 falha: a BD fica na versão 1 e a 3 não corre.

    Na chamada seguinte, com a 2 já corrigida, recomeça na 2.
    """
    corridas = []
    falhar = [True]

    def um(caminho):
        corridas.append(1)
        return True

    def dois(caminho):
        corridas.append(2)
        if falhar[0]:
            raise RuntimeError("falhou (simulado)")
        return True

    def tres(caminho):
        corridas.append(3)
        return True

    monkeypatch.setattr(database, "MIGRACOES", (("um", um), ("dois", dois), ("três", tres)))
    caminho = tmp_path / "antiga.db"
    criar_bd_do_modelo(caminho)

    with pytest.raises(RuntimeError, match="falhou"):
        aplicar_migracoes(str(caminho))
    assert corridas == [1, 2]
    assert versao(caminho) == 1

    falhar[0] = False
    assert aplicar_migracoes(str(caminho)) == ["dois", "três"]
    assert corridas == [1, 2, 2, 3]
    assert versao(caminho) == 3


def test_bd_do_modelo_nao_tem_nada_em_falta(tmp_path):
    caminho = tmp_path / "nova.db"
    criar_bd_do_modelo(caminho)

    assert colunas_em_falta(str(caminho)) == []


def test_colunas_e_tabelas_em_falta_sao_nomeadas(tmp_path):
    """Cálculo à mão: sem `perfis_importacao.coluna_fee` e sem `configuracao`.

    Uma coluna a mais (`contas.extra`) não conta.
    """
    caminho = tmp_path / "antiga.db"
    criar_bd_do_modelo(caminho)
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute("ALTER TABLE perfis_importacao DROP COLUMN coluna_fee")
        con.execute("DROP TABLE configuracao")
        con.execute("ALTER TABLE contas ADD COLUMN extra TEXT")
    finally:
        con.close()

    assert sorted(colunas_em_falta(str(caminho))) == [
        "configuracao",
        "perfis_importacao.coluna_fee",
    ]


def test_colunas_em_falta_nao_escreve(tmp_path):
    """Só leitura: o ficheiro fica igual, mesmo com coisas em falta."""
    caminho = tmp_path / "antiga.db"
    criar_bd_do_modelo(caminho)
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute("DROP TABLE configuracao")
    finally:
        con.close()
    antes = md5(caminho)

    assert colunas_em_falta(str(caminho)) == ["configuracao"]
    assert md5(caminho) == antes

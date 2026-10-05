"""
Testes para POST /api/backups/importar.

Cobrem o bug B1 original (um ficheiro inválido era aceite com 200 e
destruía a BD em silêncio) e a correção atual. O último teste documenta
uma fresta residual conhecida e ainda por corrigir: a validação confirma
os NOMES das tabelas mas não as colunas — ver relatório de análise.
"""
import io
import os
import sqlite3
from datetime import date

import pytest
from database import DB_PATH, Conta


def _sqlite_bytes(tabelas: dict[str, str]) -> bytes:
    """Constrói um ficheiro SQLite em memória e devolve os bytes.

    `tabelas` é {nome_tabela: definição_de_colunas}, ex.
    {"contas": "id INTEGER PRIMARY KEY, nome TEXT"}.
    """
    caminho_tmp = os.path.join(
        os.environ["RASTREIO_DB_DIR"], f"_fixture_{abs(hash(frozenset(tabelas))) }.db"
    )
    if os.path.exists(caminho_tmp):
        os.remove(caminho_tmp)
    con = sqlite3.connect(caminho_tmp)
    for nome, colunas in tabelas.items():
        con.execute(f"CREATE TABLE {nome} ({colunas})")
    con.commit()
    con.close()
    with open(caminho_tmp, "rb") as f:
        conteudo = f.read()
    os.remove(caminho_tmp)
    return conteudo


TABELAS_MINIMAS_VALIDAS = {
    "transacoes": "id INTEGER PRIMARY KEY, data TEXT, descricao TEXT, valor REAL",
    "categorias": "id INTEGER PRIMARY KEY, nome TEXT, tipo TEXT",
    "contas": "id INTEGER PRIMARY KEY, nome TEXT, saldo_referencia REAL, "
              "data_referencia TEXT, ativa INTEGER",
}


def test_ficheiro_nao_sqlite_e_rejeitado_sem_perder_dados(client, db_session):
    db_session.add(Conta(nome="Conta Real", saldo_referencia=100, data_referencia=date(2024, 1, 1)))
    db_session.commit()

    lixo = io.BytesIO(b"isto nao e uma base de dados sqlite")
    r = client.post("/api/backups/importar", files={"file": ("backup.db", lixo, "application/octet-stream")})

    assert r.status_code == 400
    assert "SQLite" in r.json()["detail"]
    assert not os.path.exists(DB_PATH + ".anterior")
    assert not os.path.exists(DB_PATH + ".tmp")

    contas = db_session.query(Conta).all()
    assert [c.nome for c in contas] == ["Conta Real"]


def test_sqlite_valido_mas_sem_tabelas_esperadas_e_rejeitado(client, db_session):
    db_session.add(Conta(nome="Conta Real", saldo_referencia=100, data_referencia=date(2024, 1, 1)))
    db_session.commit()

    conteudo = _sqlite_bytes({"lixo": "id INTEGER"})
    r = client.post("/api/backups/importar", files={"file": ("backup.db", io.BytesIO(conteudo), "application/octet-stream")})

    assert r.status_code == 400
    assert "tabelas" in r.json()["detail"].lower()

    contas = db_session.query(Conta).all()
    assert [c.nome for c in contas] == ["Conta Real"]


def test_backup_valido_round_trip_preserva_dados(client, db_session):
    db_session.add(Conta(nome="Conta Real", saldo_referencia=100, data_referencia=date(2024, 1, 1)))
    db_session.commit()

    exportado = client.get("/api/backups/exportar")
    assert exportado.status_code == 200

    r = client.post(
        "/api/backups/importar",
        files={"file": ("good.db", io.BytesIO(exportado.content), "application/octet-stream")},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert not os.path.exists(DB_PATH + ".anterior")

    contas = db_session.query(Conta).all()
    assert [c.nome for c in contas] == ["Conta Real"]


@pytest.mark.xfail(
    reason="B1 residual conhecido: a validação confirma apenas os NOMES das "
    "tabelas (TABELAS_ESPERADAS), não as colunas. Um .db com as tabelas "
    "certas mas esquema incompleto passa a validação e só rebenta no "
    "primeiro pedido real, já sem .anterior para recuar. Ver relatório de "
    "análise, secção B1. Quando for corrigido (ex. substituir os "
    "SELECT COUNT(*) da verificação pós-swap por um SELECT às colunas "
    "concretas), remover este xfail — o teste passa a confirmar a correção.",
    strict=True,
)
def test_sqlite_com_tabelas_certas_mas_colunas_erradas_e_rejeitado(client, db_session):
    db_session.add(Conta(nome="Conta Real", saldo_referencia=100, data_referencia=date(2024, 1, 1)))
    db_session.commit()

    # Tabelas com os nomes certos, mas sem as colunas que a app espera.
    conteudo = _sqlite_bytes({
        "transacoes": "id INTEGER PRIMARY KEY",
        "categorias": "id INTEGER PRIMARY KEY",
        "contas": "id INTEGER PRIMARY KEY",
    })
    r = client.post(
        "/api/backups/importar",
        files={"file": ("backup_incompleto.db", io.BytesIO(conteudo), "application/octet-stream")},
    )
    # Comportamento desejado: rejeitar com 400 antes de trocar a BD.
    assert r.status_code == 400

"""Configuração partilhada dos testes.

A prioridade absoluta deste ficheiro é uma só: **os testes nunca podem tocar
na base de dados real** (`backend/dados/rastreio.db`), que é a que está em
produção e não está versionada.

Como isso é garantido
---------------------
`database.py` resolve o caminho da BD **no momento do import** (linha 34) a
partir da variável de ambiente `RASTREIO_DB_DIR`, e constrói a `engine` à mão
na linha 88. Importar o módulo já fixa o destino. Por isso:

1. Este módulo corre antes de qualquer teste e define `RASTREIO_DB_DIR` para um
   directório temporário fora do repositório, ainda antes de o `database` ser
   importado por quem quer que seja.
2. `test_bd_real_nao_e_tocada` (ver test_seguranca_bd.py) falha de propósito
   se alguém algum dia inverter esta ordem, ou se a variável deixar de ser
   respeitada. É a rede que torna o resto dos testes seguros por construção.

Sobre o `main`
--------------
Os testes de API **não** importam `main`. Fazê-lo cria ficheiros de log em
`~/.rastreio-db/` e pode redirigir `sys.stdout`/`sys.stderr` (ver
`main.py:41` e `main.py:113`), o que engoliria a saída do pytest. A app de
testes é montada aqui a partir dos módulos de `routers/`, e um teste
específico garante que a lista de routers não diverge da de `main.ROUTERS`.
"""

import atexit
import os
import shutil
import tempfile

# --- temporally estável: tem de acontecer ANTES de qualquer import de
# --- database / routers / schemas, porque o caminho da BD é fixado no import.
_TMP_DIR = tempfile.mkdtemp(prefix="rastreio-test-")
os.environ["RASTREIO_DB_DIR"] = _TMP_DIR

# O log de arranque vai para o mesmo sítio temporário, por via de HOME /
# LOCALAPPDATA. Só relevante se algum teste importar main (ver test_seguranca_bd.py).
os.environ["HOME"] = _TMP_DIR
os.environ["LOCALAPPDATA"] = _TMP_DIR
os.environ["USERPROFILE"] = _TMP_DIR  # equivalente no Windows

# Um pytest interrompido (Ctrl+C, um assert que rebenta) não pode deixar lixo
# em /tmp: cada corrida cria um directório novo.
atexit.register(shutil.rmtree, _TMP_DIR, ignore_errors=True)

import pytest  # noqa: E402  (tem de vir depois do setup de ambiente acima)

# ---------------------------------------------------------------------------
# Sessões de teste
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """Sessão SQLAlchemy sobre uma BD SQLite in-memory, isolada por teste.

    Uma engine nova por teste garante que nenhum estado vaza entre testes.
    `StaticPool` é obrigatório: sem ele, cada conexão da pool abriria o seu
    próprio banco in-memory e as tabelas criadas numa sumiriam na seguinte.
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import database  # noqa: F401  — importa todos os modelos antes do create_all
    from database import Base, ligar_chaves_estrangeiras

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Como a engine da app: os testes vêem as chaves estrangeiras forçadas (D1)
    event.listen(engine, "connect", ligar_chaves_estrangeiras)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    db = Session()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# App de teste
# ---------------------------------------------------------------------------

# A mesma lista de routers que `main.py` monta, e que
# test_app_de_testes_cobre_os_mesmos_routers_que_o_main obriga a manter igual.
from routers import (  # noqa: E402
    backups,
    categorias,
    configuracao,
    contas,
    estatisticas,
    importacao,
    patrimonio,
    perfis_importacao,
    regras,
    tipos_ativo,
    transacoes,
)

ROUTERS = (
    categorias.router,
    transacoes.router,
    regras.router,
    importacao.router,
    estatisticas.router,
    backups.router,
    configuracao.router,
    perfis_importacao.router,
    patrimonio.router,
    contas.router,
    tipos_ativo.router,
)


@pytest.fixture
def client(session):
    """TestClient sobre a BD in-memory da fixture `session`.

    A app é montada aqui, e não importada de `main`, por causa dos efeitos
    colaterais de import descritos no topo deste ficheiro. O lifespan não é
    usado: `Base.metadata.create_all` já corre na fixture `session`, e chamar
    `criar_tabelas()` aqui voltaria a tocar no sistema de ficheiros real.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from database import get_db

    app = FastAPI()
    for router in ROUTERS:
        app.include_router(router, prefix="/api")

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# BD com o schema partido da D1a
# ---------------------------------------------------------------------------


@pytest.fixture
def criar_bd_com_fk_partida():
    """Devolve uma função que cria, num caminho, uma BD com o schema da D1a.

    O schema não é escrito à mão: é reproduzido como aconteceu na BD real.
    Cria-se o modelo actual, semeiam-se dados, e repete-se o que
    `old/migrar_tipos_ativo.py` fez a `ativos` — RENAME para `ativos_old`,
    tabela nova, cópia, DROP. O SQLite (>= 3.26) reescreve no RENAME as chaves
    de `precos_ativo` e `movimentos_ativo` para `ativos_old`, e o DROP deixa-as
    assim. Os testes confirmam esse estado antes de o reparar.

    Os IDs não são seguidos (ativos 3 e 7, preços 5, 9 e 12, movimentos 2 e
    8), para que um ID renumerado na cópia se note.
    """
    import sqlite3

    from sqlalchemy import create_engine
    from sqlalchemy.dialects import sqlite as dialecto_sqlite
    from sqlalchemy.schema import CreateTable

    from database import (
        Ativo,
        Base,
        TipoContabilizacao,
        TipoMovimento,
    )

    def criar(caminho):
        engine = create_engine(f"sqlite:///{caminho}")
        Base.metadata.create_all(bind=engine)
        engine.dispose()

        compra = TipoMovimento.compra.name
        investimento = TipoContabilizacao.investimento.name
        con = sqlite3.connect(caminho, autocommit=True)
        try:
            con.execute("INSERT INTO tipos_ativo VALUES (1, 'Ações', 1)")
            con.executemany(
                "INSERT INTO ativos VALUES (?, ?, 1, ?, 'EUR', NULL, ?)",
                [(3, "Alfa", "ALF", investimento), (7, "Beta", "BET", investimento)],
            )
            con.executemany(
                "INSERT INTO precos_ativo VALUES (?, ?, ?, ?)",
                [
                    (5, 3, "2024-01-31", 10.5),
                    (9, 3, "2024-02-29", 11.25),
                    (12, 7, "2024-01-31", 2.0),
                ],
            )
            con.executemany(
                "INSERT INTO movimentos_ativo VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (2, 3, compra, "2024-01-10", 4.0, 10.0, 1.5, 41.5, None),
                    (8, 7, compra, "2024-01-15", 10.0, 2.0, 0.0, 20.0, "nota"),
                ],
            )

            # O que old/migrar_tipos_ativo.py fez, passo a passo.
            con.execute("ALTER TABLE ativos RENAME TO ativos_old")
            con.execute(
                str(CreateTable(Ativo.__table__).compile(dialect=dialecto_sqlite.dialect()))
            )
            con.execute("INSERT INTO ativos SELECT * FROM ativos_old")
            con.execute("DROP TABLE ativos_old")
        finally:
            con.close()

    return criar

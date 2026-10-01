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
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from database import Base
    import database  # noqa: F401  — importa todos os modelos antes do create_all

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


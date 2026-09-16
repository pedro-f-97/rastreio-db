"""
Configuração partilhada pelos testes.

IMPORTANTE: RASTREIO_DB_DIR tem de ser definida ANTES do primeiro import de
`database` (ou de qualquer módulo que o importe, como `main`), porque
`database.py` resolve o caminho da BD ao nível do módulo. Por isso a
variável é definida aqui, no topo do ficheiro, antes de qualquer import da
app — nunca a mover para dentro de uma fixture.

Cada teste corre contra uma BD SQLite temporária e isolada (uma pasta nova
por sessão de testes, esquema recriado a cada teste). Nunca toca na BD real
de desenvolvimento (backend/dados/rastreio.db).
"""
import os
import shutil
import sys
import tempfile

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="rastreio-db-tests-")
os.environ["RASTREIO_DB_DIR"] = _TMP_DIR

# Garante que 'backend/' está no sys.path mesmo que o pytest seja invocado
# de outro diretório (o pytest.ini com pythonpath=. já trata disto em
# pytest >= 7, isto é só um cinto-e-suspensórios).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402  (import tem de vir depois do RASTREIO_DB_DIR)
from database import Base, SessionLocal, engine, garantir_pasta_dados  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# A pasta 'dados/' só é criada por garantir_pasta_dados() (nunca ao nível do
# módulo — ver B4). Como os fixtures abaixo tocam na BD antes de o
# TestClient disparar o lifespan da app, garantimos aqui que a pasta existe.
garantir_pasta_dados()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture()
def db_session():
    """BD limpa para cada teste: recria o esquema do zero antes de cada um.

    Devolve uma sessão que o teste usa para semear dados (contas, ativos,
    transações, ...) antes de fazer pedidos através do fixture `client`.
    Os pedidos HTTP abrem as suas próprias sessões (via get_db), mas como
    apontam para o mesmo ficheiro/engine, veem os dados aqui semeados desde
    que tenham sido commitados.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """TestClient ligado à BD limpa de db_session."""
    with TestClient(main.app) as c:
        yield c

"""Testes da verificação de origem (`backend/seguranca.py`, achado 7.1).

Uma escrita (POST, PUT, PATCH, DELETE) com um `Origin` que não seja o da
aplicação é recusada com 403 antes de chegar à rota. Leituras e pedidos sem
`Origin` passam.

A app é montada aqui, e não importada de `main` (ver `conftest.py`). As origens
permitidas são as mesmas que `main.py` monta em dev: as duas formas de chegar à
porta 9742 e o Vite em 9743.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import Configuracao, get_db
from routers import configuracao
from seguranca import criar_verificacao_origem

ORIGENS_PERMITIDAS = {
    "http://localhost:9742",
    "http://127.0.0.1:9742",
    "http://localhost:9743",
}
SITE_ALHEIO = "https://site-malicioso.example"


def _app_minima(chamadas):
    """Uma rota por método, que conta quantas vezes correu."""
    app = FastAPI()
    app.middleware("http")(criar_verificacao_origem(ORIGENS_PERMITIDAS))

    @app.api_route("/rota", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def rota():
        chamadas.append(1)
        return {"ok": True}

    return app


@pytest.fixture
def chamadas():
    return []


@pytest.fixture
def cliente_minimo(chamadas):
    with TestClient(_app_minima(chamadas)) as c:
        yield c


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_escrita_de_outro_site_e_recusada(cliente_minimo, chamadas, metodo):
    resposta = cliente_minimo.request(metodo, "/rota", headers={"Origin": SITE_ALHEIO})

    assert resposta.status_code == 403
    assert resposta.json() == {"detail": "Pedido recusado: vem de outro site."}
    assert chamadas == []  # a rota nunca correu


def test_origem_null_e_recusada(cliente_minimo, chamadas):
    # Um iframe com sandbox ou um ficheiro local mandam `Origin: null`
    resposta = cliente_minimo.post("/rota", headers={"Origin": "null"})

    assert resposta.status_code == 403
    assert chamadas == []


def test_mesmo_anfitriao_noutra_porta_e_recusado(cliente_minimo, chamadas):
    resposta = cliente_minimo.post("/rota", headers={"Origin": "http://localhost:8080"})

    assert resposta.status_code == 403
    assert chamadas == []


@pytest.mark.parametrize("origem", sorted(ORIGENS_PERMITIDAS))
def test_escrita_da_propria_aplicacao_passa(cliente_minimo, chamadas, origem):
    resposta = cliente_minimo.post("/rota", headers={"Origin": origem})

    assert resposta.status_code == 200
    assert chamadas == [1]


def test_escrita_sem_origin_passa(cliente_minimo, chamadas):
    # curl e os testes não mandam `Origin`; um browser manda sempre num POST
    resposta = cliente_minimo.post("/rota")

    assert resposta.status_code == 200
    assert chamadas == [1]


def test_leitura_de_outro_site_passa(cliente_minimo, chamadas):
    # Só as escritas são verificadas; a leitura é o achado 7.2
    resposta = cliente_minimo.get("/rota", headers={"Origin": SITE_ALHEIO})

    assert resposta.status_code == 200
    assert chamadas == [1]


def test_inicializar_vindo_de_outro_site_nao_escreve_na_bd(session):
    """O caso real do achado: `POST /api/configuracao/inicializar` sem corpo."""
    app = FastAPI()
    app.middleware("http")(criar_verificacao_origem(ORIGENS_PERMITIDAS))
    app.include_router(configuracao.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: session

    with TestClient(app) as c:
        resposta = c.post("/api/configuracao/inicializar", headers={"Origin": SITE_ALHEIO})

    assert resposta.status_code == 403
    session.expire_all()
    assert session.query(Configuracao).count() == 0  # BD vazia: nada foi criado

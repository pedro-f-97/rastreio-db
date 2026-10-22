"""Testes da lista de anfitriões permitidos (`backend/seguranca.py`).

Com DNS rebinding, um site alheio passa a apontar para 127.0.0.1 e o browser
deixa-o ler as respostas; o único sinal é o `Host` do pedido, que traz o nome
desse site. `TrustedHostMiddleware` com `ANFITRIOES_PERMITIDOS` recusa-o com 400
antes de chegar à rota. A porta do `Host` não conta.

A app é montada aqui, e não importada de `main` (ver `conftest.py`), com o
mesmo middleware e a mesma lista que `main.py` usa.
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient

from seguranca import ANFITRIOES_PERMITIDOS


@pytest.fixture
def chamadas():
    return []


@pytest.fixture
def cliente(chamadas):
    app = FastAPI()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ANFITRIOES_PERMITIDOS)

    @app.api_route("/rota", methods=["GET", "POST"])
    def rota():
        chamadas.append(1)
        return {"ok": True}

    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize(
    "anfitriao",
    [
        "site-malicioso.example:9742",
        "localhost.site-malicioso.example:9742",  # começa por «localhost», mas é outro nome
        "127.0.0.1.site-malicioso.example",
        "0.0.0.0:9742",
    ],
)
def test_leitura_com_host_alheio_e_recusada(cliente, chamadas, anfitriao):
    resposta = cliente.get("/rota", headers={"Host": anfitriao})

    assert resposta.status_code == 400
    assert resposta.text == "Invalid host header"
    assert chamadas == []  # a rota nunca correu


def test_escrita_com_host_alheio_e_recusada(cliente, chamadas):
    resposta = cliente.post("/rota", headers={"Host": "site-malicioso.example:9742"})

    assert resposta.status_code == 400
    assert chamadas == []


@pytest.mark.parametrize(
    "anfitriao",
    [
        "localhost:9742",  # a app no executável
        "127.0.0.1:9742",
        "localhost:9743",  # o Vite em dev, se o pedido passar pelo proxy
        "localhost",
    ],
)
def test_host_da_propria_maquina_passa(cliente, chamadas, anfitriao):
    resposta = cliente.get("/rota", headers={"Host": anfitriao})

    assert resposta.status_code == 200
    assert chamadas == [1]

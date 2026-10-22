"""Testes da janela de controlo (`backend/tray.py`).

A janela é tkinter e não se abre nos testes: `tkinter` é substituído em
`sys.modules` por um `MagicMock`, e o `mainloop()` falso devolve logo. Os
botões ficam registados nas chamadas a `tk.Button`, e o comando do botão
"Abrir no browser" é chamado à mão.

O `main` não é importado (ver `conftest.py`). A ligação entre `main.PORTA` e a
tray é verificada lendo `main.py` com `ast`, sem o executar.
"""

import ast
import json
import os
import socket
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock

import tray


def _comando_do_botao(tk_falso, texto):
    for chamada in tk_falso.Button.call_args_list:
        if chamada.kwargs.get("text") == texto:
            return chamada.kwargs["command"]
    raise AssertionError(f"Botão {texto!r} não foi criado")


def test_abrir_no_browser_usa_a_porta_recebida(monkeypatch):
    """O botão "Abrir no browser" abre `http://localhost:<porta>` com a porta passada.

    Antes da correcção, a tray tinha `9742` escrito à mão, duplicado de `main.PORTA`.
    Com a porta 12345 (diferente de 9742, de propósito), o URL esperado é
    `http://localhost:12345`. Força-se o ramo Linux (`xdg-open`), em que o URL
    é o segundo elemento da lista passada ao `subprocess.Popen`.
    """
    tk_falso = MagicMock()
    tk_falso.TclError = Exception
    tk_falso.Tk.return_value.winfo_screenwidth.return_value = 1920
    tk_falso.Tk.return_value.winfo_screenheight.return_value = 1080
    monkeypatch.setitem(sys.modules, "tkinter", tk_falso)

    abertos = []
    monkeypatch.setattr(tray.sys, "platform", "linux")
    monkeypatch.setattr(tray.subprocess, "Popen", lambda args, **kwargs: abertos.append(args))

    tray.iniciar_tray(lambda: None, 12345)
    _comando_do_botao(tk_falso, "Abrir no browser")()

    assert abertos == [["xdg-open", "http://localhost:12345"]]


def test_main_passa_a_porta_a_tray():
    """`main.py` chama `iniciar_tray(parar_servidor, PORTA)`.

    Lido com `ast` para não importar o `main`. Há uma só chamada a
    `iniciar_tray`, e o segundo argumento é o nome `PORTA`, a mesma constante
    que o uvicorn usa.
    """
    caminho = os.path.join(os.path.dirname(tray.__file__), "main.py")
    with open(caminho, encoding="utf-8") as f:
        arvore = ast.parse(f.read())

    chamadas = [
        n
        for n in ast.walk(arvore)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "iniciar_tray"
    ]

    assert len(chamadas) == 1
    assert [ast.unparse(a) for a in chamadas[0].args] == ["parar_servidor", "PORTA"]


# ---------------------------------------------------------------------------
# Quem está na porta antes de arrancar (achado 7.3)
# ---------------------------------------------------------------------------


def _porta_livre():
    """Uma porta que o sistema acabou de dar como livre."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _servidor_que_responde(estado, corpo):
    """Um servidor HTTP local, numa porta livre, que responde sempre `estado` e `corpo`."""

    class Resposta(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(estado)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *args):
            pass

    servidor = HTTPServer(("127.0.0.1", 0), Resposta)
    fio = threading.Thread(target=servidor.serve_forever, daemon=True)
    fio.start()
    try:
        yield servidor.server_address[1]
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_porta_sem_ninguem_esta_livre():
    """Sem nada à escuta, a ligação é recusada: "livre"."""
    assert tray.quem_esta_na_porta(_porta_livre()) == "livre"


def test_porta_com_o_rastreio_e_outra_instancia():
    """Um servidor que responde ao `/api/configuracao/estado` como o Rastreio-DB.

    Cálculo à mão: o corpo tem exactamente as chaves `inicializado` e
    `tour_visto`, as do router `configuracao.estado` -> "rastreio".
    """
    corpo = json.dumps({"inicializado": True, "tour_visto": False}).encode()
    with _servidor_que_responde(200, corpo) as porta:
        assert tray.quem_esta_na_porta(porta) == "rastreio"


def test_porta_com_outro_programa():
    """Outro programa na porta: um 404, ou um 200 com outro JSON -> "outro"."""
    with _servidor_que_responde(404, b"{}") as porta:
        assert tray.quem_esta_na_porta(porta) == "outro"
    with _servidor_que_responde(200, b'{"inicializado": true}') as porta:
        assert tray.quem_esta_na_porta(porta) == "outro"


def test_main_verifica_a_porta_antes_do_preflight():
    """`_main` pergunta quem está em `PORTA` antes de chamar `_preflight`.

    Lido com `ast` para não importar o `main`: no corpo de `_main`, a chamada a
    `quem_esta_na_porta(PORTA)` vem antes da chamada a `_preflight()`, para uma
    segunda instância não tocar na BD da primeira.
    """
    caminho = os.path.join(os.path.dirname(tray.__file__), "main.py")
    with open(caminho, encoding="utf-8") as f:
        arvore = ast.parse(f.read())
    funcao = next(
        n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef) and n.name == "_main"
    )
    chamadas = [
        ast.unparse(n)
        for n in ast.walk(funcao)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in ("quem_esta_na_porta", "_preflight")
    ]

    assert chamadas[:2] == ["quem_esta_na_porta(PORTA)", "_preflight()"]

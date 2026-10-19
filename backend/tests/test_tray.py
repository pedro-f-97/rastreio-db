"""Testes da janela de controlo (`backend/tray.py`).

A janela é tkinter e não se abre nos testes: `tkinter` é substituído em
`sys.modules` por um `MagicMock`, e o `mainloop()` falso devolve logo. Os
botões ficam registados nas chamadas a `tk.Button`, e o comando do botão
"Abrir no browser" é chamado à mão.

O `main` não é importado (ver `conftest.py`). A ligação entre `main.PORTA` e a
tray é verificada lendo `main.py` com `ast`, sem o executar.
"""

import ast
import os
import sys
from unittest.mock import MagicMock

import tray


def _comando_do_botao(tk_falso, texto):
    for chamada in tk_falso.Button.call_args_list:
        if chamada.kwargs.get("text") == texto:
            return chamada.kwargs["command"]
    raise AssertionError(f"Botão {texto!r} não foi criado")


def test_abrir_no_browser_usa_a_porta_recebida(monkeypatch):
    """O botão "Abrir no browser" abre `http://localhost:<porta>` com a porta passada.

    Era a D12i: a tray tinha `9742` escrito à mão, duplicado de `main.PORTA`.
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

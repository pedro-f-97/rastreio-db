# backend/main.py
import os
import sys
import threading
import traceback
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from database import BASE_DIR, criar_tabelas
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from routers import (
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
from starlette.exceptions import HTTPException as StarletteHTTPException

# ---------------------------------------------------------------------------
# Arranque: logging e streams
# ---------------------------------------------------------------------------
# Em --windowed (Windows), sys.stdout/stderr podem ser None. Antes fazíamos
# `open(os.devnull, "w")` — o que descartava silenciosamente TODA a informação
# de erro. Agora redireccionamos para um ficheiro de log, para que haja sempre
# rasto do que aconteceu (ver B4).

def _caminho_log() -> str | None:
    """Encontra um sítio com permissão de escrita para o log de arranque."""
    candidatos = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidatos.append(os.path.join(local, "rastreio-db", "arranque.log"))
    home = os.path.expanduser("~")
    if home and home != "~":
        candidatos.append(os.path.join(home, ".rastreio-db", "arranque.log"))
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
    candidatos.append(os.path.join(tmp, "rastreio-db-arranque.log"))

    for caminho in candidatos:
        try:
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            with open(caminho, "a", encoding="utf-8"):
                pass
            return caminho
        except Exception:
            continue
    return None


LOG_ARRANQUE = _caminho_log()


def _log(mensagem: str) -> None:
    """Escreve no ficheiro de log e, se houver, também em stderr. Nunca rebenta."""
    linha = f"[{datetime.now().isoformat(timespec='seconds')}] {mensagem}\n"
    if LOG_ARRANQUE:
        try:
            with open(LOG_ARRANQUE, "a", encoding="utf-8") as f:
                f.write(linha)
        except Exception:
            pass
    try:
        if sys.stderr is not None:
            sys.stderr.write(linha)
            sys.stderr.flush()
    except Exception:
        pass


def _configurar_streams() -> None:
    """Se stdout/stderr forem None (--windowed), redirecciona para o log.
    Caso contrário, deixa-os como estão (consola normal)."""
    if LOG_ARRANQUE is None:
        # último recurso: devnull para não rebentar nos prints
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")
        return

    if sys.stdout is None:
        try:
            sys.stdout = open(LOG_ARRANQUE, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stdout = open(os.devnull, "w")

    if sys.stderr is None:
        try:
            sys.stderr = open(LOG_ARRANQUE, "a", encoding="utf-8", buffering=1)
        except Exception:
            sys.stderr = open(os.devnull, "w")

    # Em consola, garantir line buffering para o traceback não aparecer
    # depois de prints já emitidos (bug do B4).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)  # type: ignore[union-attr]
        except Exception:
            pass


_configurar_streams()


IS_FROZEN = getattr(sys, "frozen", False)

# --- Pasta do frontend ---
if IS_FROZEN:
    PASTA_FRONTEND = os.path.join(getattr(sys, "_MEIPASS", BASE_DIR), "frontend_dist")
else:
    PASTA_FRONTEND = os.path.join(BASE_DIR, "frontend_dist")


# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # criar_tabelas é idempotente. Em dev (uvicorn main:app) é o que garante
    # que as tabelas existem; no __main__ já foi chamado antes de arrancar
    # o servidor, pelo que aqui é no-op.
    criar_tabelas()
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request, exc):
    if (
        exc.status_code == 404
        and not request.url.path.startswith("/api")
    ):
        return FileResponse(
            os.path.join(PASTA_FRONTEND, "index.html"),
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


if not IS_FROZEN:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:9743"],
        allow_methods=["*"],
        allow_headers=["*"],
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

for router in ROUTERS:
    app.include_router(router, prefix="/api")


@app.get("/")
async def servir_index():
    caminho = os.path.join(PASTA_FRONTEND, "index.html")
    return FileResponse(caminho, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })


if os.path.exists(PASTA_FRONTEND):
    app.mount("/", StaticFiles(directory=PASTA_FRONTEND, html=True), name="frontend")


# ---------------------------------------------------------------------------
# Ponto de entrada (executável)
# ---------------------------------------------------------------------------

PORTA = 9742


def _preflight() -> None:
    """Tudo o que pode falhar antes de arrancar threads. Fora do __main__
    para poder ser chamado de testes."""
    # 1) garantir pasta de dados (permite detectar PermissionError cedo)
    from database import anunciar_bd_ativa, garantir_pasta_dados
    try:
        garantir_pasta_dados()
    except RuntimeError as e:
        _log(f"Erro fatal na pasta de dados:\n{e}")
        sys.exit(2)
    anunciar_bd_ativa()

    # 2) criar tabelas ANTES de arrancar o uvicorn, para o erro não se perder
    #    dentro da thread daemon do lifespan.
    from database import Base, engine
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        _log(f"Erro a criar tabelas: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        sys.exit(3)


def _main() -> None:
    _preflight()

    servidor = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=PORTA, log_level="warning", log_config=None,
    ))

    def iniciar_servidor():
        import asyncio
        try:
            asyncio.run(servidor.serve())
        except Exception as e:
            # Se o servidor rebentar depois de arrancar, registar.
            _log(f"Servidor caiu: {type(e).__name__}: {e}\n{traceback.format_exc()}")

    def parar_servidor():
        servidor.should_exit = True

    def abrir_browser():
        import time, webbrowser
        time.sleep(1.5)
        try:
            webbrowser.open(f"http://localhost:{PORTA}")
        except Exception as e:
            _log(f"Não foi possível abrir o browser: {e}")

    t_servidor = threading.Thread(target=iniciar_servidor, daemon=True)
    t_servidor.start()

    threading.Thread(target=abrir_browser, daemon=True).start()

    # Tray na thread principal (obrigatório no Linux/Windows). Se falhar,
    # degradar em vez de crashar — o servidor continua a correr e o
    # utilizador pode aceder pelo browser.
    try:
        from tray import iniciar_tray
        iniciar_tray(parar_servidor)
        # Se chegámos aqui, a tray fechou-se (o utilizador fez quit no ícone).
        # O servidor deve terminar também.
        parar_servidor()
    except Exception as e:
        _log(f"Tray indisponível: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        msg = (
            f"Tray indisponível ({type(e).__name__}: {e}).\n"
            "A correr sem ícone. Prime Ctrl+C neste terminal para terminar."
        )
        try:
            print(msg, file=sys.stderr, flush=True)
        except Exception:
            pass

    # Bloquear enquanto o servidor corre (caso a tray não exista ou tenha
    # terminado). Em daemon threads, o join é o que mantém o processo vivo.
    try:
        t_servidor.join()
    except KeyboardInterrupt:
        _log("Ctrl+C recebido. A terminar...")
        parar_servidor()


if __name__ == "__main__":
    try:
        _main()
    except SystemExit:
        raise
    except BaseException as e:
        _log(f"Exceção não tratada no arranque: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        sys.exit(1)
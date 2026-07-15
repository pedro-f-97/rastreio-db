import os
import sys
import threading
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import BASE_DIR, criar_tabelas
from routers import categorias, transacoes, regras, importacao, estatisticas, backups, configuracao, perfis_importacao, patrimonio, contas

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# --- Pasta do frontend ---
if getattr(sys, 'frozen', False):
    PASTA_FRONTEND = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), "frontend_dist")
else:
    PASTA_FRONTEND = os.path.join(BASE_DIR, "frontend_dist")

# --- App FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_tabelas()
    yield

app = FastAPI(lifespan=lifespan)

if not getattr(sys, 'frozen', False):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:9743"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(categorias.router, prefix="/api")
app.include_router(transacoes.router, prefix="/api")
app.include_router(regras.router, prefix="/api")
app.include_router(importacao.router, prefix="/api")
app.include_router(estatisticas.router, prefix="/api")
app.include_router(backups.router, prefix="/api")
app.include_router(configuracao.router, prefix="/api")
app.include_router(perfis_importacao.router, prefix="/api")
app.include_router(patrimonio.router, prefix="/api")
app.include_router(contas.router, prefix="/api")

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

# --- Ponto de entrada (executável) ---
if __name__ == "__main__":
    PORTA = 9742

    servidor = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=PORTA, log_level="warning", log_config=None
    ))

    def iniciar_servidor():
        import asyncio
        asyncio.run(servidor.serve())

    def parar_servidor():
        servidor.should_exit = True

    def abrir_browser():
        import time, webbrowser
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{PORTA}")

    # Uvicorn numa thread separada
    t_servidor = threading.Thread(target=iniciar_servidor, daemon=True)
    t_servidor.start()

    # Browser numa thread separada
    threading.Thread(target=abrir_browser, daemon=True).start()

    # Tray na thread principal (obrigatório no Linux/Windows)
    from tray import iniciar_tray
    iniciar_tray(parar_servidor)
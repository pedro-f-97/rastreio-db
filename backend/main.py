import os
import threading
import webbrowser
import sys
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import BASE_DIR
from routers import categorias, transacoes, regras, importacao, estatisticas, backups

# Determina a pasta dos ficheiros estáticos
if getattr(sys, 'frozen', False):
    PASTA_FRONTEND = os.path.join(getattr(sys, '_MEIPASS', BASE_DIR), "frontend_dist")
else:
    PASTA_FRONTEND = os.path.join(BASE_DIR, "frontend_dist")

def abrir_browser():
    import time
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

@asynccontextmanager
async def lifespan(app: FastAPI):
    if getattr(sys, 'frozen', False):
        threading.Thread(target=abrir_browser, daemon=True).start()
    yield

app = FastAPI(lifespan=lifespan)

if not getattr(sys, 'frozen', False):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(categorias.router, prefix="/api")
app.include_router(transacoes.router, prefix="/api")
app.include_router(regras.router, prefix="/api")
app.include_router(importacao.router, prefix="/api")
app.include_router(estatisticas.router, prefix="/api")
app.include_router(backups.router, prefix="/api")

if os.path.exists(PASTA_FRONTEND):
    app.mount("/", StaticFiles(directory=PASTA_FRONTEND, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import categorias, transacoes, regras, importacao, estatisticas, backups

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(categorias.router)
app.include_router(transacoes.router)
app.include_router(regras.router)
app.include_router(importacao.router)
app.include_router(estatisticas.router)
app.include_router(backups.router)
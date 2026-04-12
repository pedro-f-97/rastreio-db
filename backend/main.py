from fastapi import FastAPI
from database import criar_tabelas
from routers import categorias, transacoes, regras, importacao

app = FastAPI()

criar_tabelas()

app.include_router(categorias.router)
app.include_router(transacoes.router)
app.include_router(regras.router)
app.include_router(importacao.router)

@app.get("/health")
def health():
    return {"status": "ok"}
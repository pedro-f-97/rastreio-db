from fastapi import FastAPI
from database import criar_tabelas

app = FastAPI()

criar_tabelas()

@app.get("/health")
def health():
    return {"status": "ok"}
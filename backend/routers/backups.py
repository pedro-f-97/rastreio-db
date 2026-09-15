# backend/routers/backups.py
import os
import shutil
import sqlite3

from database import DB_PATH, engine
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text

router = APIRouter(prefix="/backups", tags=["backups"])

TABELAS_ESPERADAS = {"transacoes", "categorias", "contas"}


@router.get("/exportar")
def exportar_backup():
    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))

    return FileResponse(
        path=DB_PATH,
        filename="rastreio_backup.db",
        media_type="application/octet-stream",
    )


def _validar_sqlite(path: str) -> set[str]:
    """Confirma que o ficheiro é SQLite, está íntegro, e devolve as tabelas."""
    con = sqlite3.connect(path)  # abre lazy, erros surgem no primeiro execute
    try:
        row = con.execute("PRAGMA integrity_check;").fetchone()
        if not row or row[0] != "ok":
            raise HTTPException(400, "Base de dados corrompida (integrity_check).")

        tabelas = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    except sqlite3.DatabaseError as e:
        raise HTTPException(400, f"O ficheiro não é uma base de dados SQLite válida: {e}")
    finally:
        con.close()

    return tabelas


@router.post("/importar")
async def importar_backup(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Ficheiro inválido")

    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Ficheiro vazio")

    temp_path = DB_PATH + ".tmp"
    anterior_path = DB_PATH + ".anterior"

    # limpar restos de tentativas anteriores
    for p in (temp_path, anterior_path):
        if os.path.exists(p):
            os.remove(p)

    # 1) Escrever e validar ANTES de tocar no DB atual
    with open(temp_path, "wb") as f:
        f.write(conteudo)
        f.flush()
        os.fsync(f.fileno())

    try:
        tabelas = _validar_sqlite(temp_path)
    except HTTPException:
        os.remove(temp_path)
        raise

    faltam = TABELAS_ESPERADAS - tabelas
    if faltam:
        os.remove(temp_path)
        raise HTTPException(
            status_code=400,
            detail=f"Estrutura inesperada. Faltam tabelas: {sorted(faltam)}",
        )

    # 2) Só agora mexemos no DB real
    engine.dispose()

    try:
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, anterior_path)

        # WAL/SHM pertencem ao DB antigo — têm de sair antes do replace
        for extra in (DB_PATH + "-wal", DB_PATH + "-shm"):
            if os.path.exists(extra):
                os.remove(extra)

        os.replace(temp_path, DB_PATH)

        # 3) Verificação pós-swap: reabrir e fazer SELECTs reais
        with engine.connect() as conn:
            for t in TABELAS_ESPERADAS:
                conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()

    except Exception as e:
        # rollback
        engine.dispose()
        try:
            if os.path.exists(anterior_path):
                shutil.copy2(anterior_path, DB_PATH)
                os.remove(anterior_path)
            for extra in (DB_PATH + "-wal", DB_PATH + "-shm"):
                if os.path.exists(extra):
                    os.remove(extra)
        except Exception:
            # rollback também falhou — pelo menos não esconder o erro original
            pass
        raise HTTPException(status_code=500, detail=f"Falha ao restaurar: {e}")

    # 4) Só depois de tudo confirmado é que apagamos o .anterior
    if os.path.exists(anterior_path):
        os.remove(anterior_path)

    return {"ok": True, "mensagem": "Base de dados restaurada"}
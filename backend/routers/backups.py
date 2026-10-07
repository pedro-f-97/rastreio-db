# backend/routers/backups.py
import os
import shutil
import sqlite3
from pathlib import Path

from database import Base, DB_PATH, engine
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text

router = APIRouter(prefix="/backups", tags=["backups"])

# A lista de tabelas validadas deriva do modelo (D6): um backup a que falte
# qualquer tabela do modelo é rejeitado.
TABELAS_ESPERADAS = {tabela.name for tabela in Base.metadata.sorted_tables}

# Mensagem única para qualquer problema de estrutura — tabela ou coluna em
# falta. Não diz o que falta: é propositado (D6).
MENSAGEM_ESTRUTURA = (
    "O ficheiro não corresponde a um backup válido do Rastreio-DB"
)


def _limpar_wal_shm(db_path: str) -> None:
    """Remove ficheiros WAL/SHM do DB e do .tmp, se existirem."""
    for extra in (
        db_path + "-wal",
        db_path + "-shm",
        db_path + ".tmp-shm",
        db_path + ".tmp-wal",
    ):
        if os.path.exists(extra):
            os.remove(extra)


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


def _validar_estrutura(path: str) -> None:
    """Confirma que `path` tem todas as tabelas e colunas do modelo.

    Só leitura: o ficheiro é aberto com `mode=ro` (URI), portanto nunca há
    escrita à toa. Tabelas e colunas a mais são aceites; qualquer falta levanta
    HTTPException 400 com a mensagem genérica (D6).
    """
    try:
        con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
        try:
            linhas = con.execute(
                "SELECT m.name, p.name FROM sqlite_master AS m "
                "JOIN pragma_table_info(m.name) AS p WHERE m.type = 'table'"
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        raise HTTPException(status_code=400, detail=MENSAGEM_ESTRUTURA)

    reais: dict[str, set[str]] = {}
    for nome_tabela, nome_coluna in linhas:
        reais.setdefault(nome_tabela, set()).add(nome_coluna)

    if TABELAS_ESPERADAS - reais.keys():
        raise HTTPException(status_code=400, detail=MENSAGEM_ESTRUTURA)

    for tabela in Base.metadata.sorted_tables:
        if {coluna.name for coluna in tabela.columns} - reais[tabela.name]:
            raise HTTPException(status_code=400, detail=MENSAGEM_ESTRUTURA)


@router.post("/importar")
async def importar_backup(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Ficheiro inválido")

    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Ficheiro vazio")

    temp_path = DB_PATH + ".tmp"
    anterior_path = DB_PATH + ".anterior"

    # limpar só o temporário: o `.anterior` fica no disco até um restauro que
    # passe a validação o substituir (D6)
    if os.path.exists(temp_path):
        os.remove(temp_path)

    # 1) Escrever e validar ANTES de tocar no DB atual
    with open(temp_path, "wb") as f:
        f.write(conteudo)
        f.flush()
        os.fsync(f.fileno())

    try:
        _validar_sqlite(temp_path)
        _validar_estrutura(temp_path)
    except HTTPException:
        os.remove(temp_path)
        raise

    # 2) Só agora mexemos no DB real
    engine.dispose()

    try:
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, anterior_path)

        # Limpar WAL/SHM antes de mover
        _limpar_wal_shm(DB_PATH)
        os.replace(temp_path, DB_PATH)

        # 3) Verificação pós-troca: a MESMA validação sobre a BD trocada
        _validar_estrutura(DB_PATH)

    except Exception as e:
        # rollback
        engine.dispose()
        try:
            if os.path.exists(anterior_path):
                shutil.copy2(anterior_path, DB_PATH)
            _limpar_wal_shm(DB_PATH)
        except Exception:
            # rollback também falhou — pelo menos não esconder o erro original
            pass
        _limpar_wal_shm(DB_PATH)
        raise HTTPException(status_code=500, detail=f"Falha ao restaurar: {e}")

    # 4) O `.anterior` fica no disco: é substituído no restauro seguinte (D6)
    return {"ok": True, "mensagem": "Base de dados restaurada"}

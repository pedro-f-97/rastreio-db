# backend/routers/backups.py
import os
import shutil
import sqlite3

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text

from database import DB_PATH, aplicar_migracoes, colunas_em_falta, engine

router = APIRouter(prefix="/backups", tags=["backups"])

# Mensagens para um problema de estrutura (tabela ou coluna em falta). Não
# dizem o que falta, só se o ficheiro parece um backup do Rastreio-DB: as três
# tabelas de sempre presentes indicam um backup de uma versão anterior que as
# migrações já não cobrem; sem elas, o ficheiro não é um backup do Rastreio-DB.
MENSAGEM_ESTRUTURA = "O ficheiro não corresponde a um backup válido do Rastreio-DB"
MENSAGEM_VERSAO_ANTERIOR = (
    "Este backup é de uma versão anterior do Rastreio-DB e já não pode ser "
    "actualizado para esta versão. A base de dados actual não foi alterada."
)
TABELAS_DE_SEMPRE = {"transacoes", "categorias", "contas"}


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

        tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    except sqlite3.DatabaseError as e:
        raise HTTPException(400, f"O ficheiro não é uma base de dados SQLite válida: {e}")
    finally:
        con.close()

    return tabelas


def _validar_estrutura(path: str) -> None:
    """Confirma que `path` tem todas as tabelas e colunas do modelo.

    É a mesma verificação do arranque (`colunas_em_falta`), só de leitura.
    Tabelas e colunas a mais são aceites; qualquer falta levanta HTTPException
    400, com a mensagem de versão anterior se as três tabelas de sempre lá
    estiverem, e com a genérica se não.
    """
    try:
        em_falta = colunas_em_falta(path)
    except sqlite3.Error:
        raise HTTPException(status_code=400, detail=MENSAGEM_ESTRUTURA)
    if em_falta:
        # `em_falta` traz as tabelas em falta pelo nome, sem ponto
        if TABELAS_DE_SEMPRE.isdisjoint(em_falta):
            raise HTTPException(status_code=400, detail=MENSAGEM_VERSAO_ANTERIOR)
        raise HTTPException(status_code=400, detail=MENSAGEM_ESTRUTURA)


@router.post("/importar")
async def importar_backup(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".db"):
        raise HTTPException(status_code=400, detail="Ficheiro inválido")

    conteudo = await file.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Ficheiro vazio")

    temp_path = DB_PATH + ".tmp"
    anterior_path = DB_PATH + ".anterior"

    # limpar só o temporário: o `.anterior` fica no disco até um restauro que
    # passe a validação o substituir
    if os.path.exists(temp_path):
        os.remove(temp_path)

    # 1) Escrever e validar ANTES de tocar no DB atual
    with open(temp_path, "wb") as f:
        f.write(conteudo)
        f.flush()
        os.fsync(f.fileno())

    try:
        _validar_sqlite(temp_path)
        # Um backup de uma versão anterior é actualizado antes de ser validado,
        # no temporário: se uma migração falhar, a BD actual não foi tocada
        aplicar_migracoes(temp_path)
        _validar_estrutura(temp_path)
    except HTTPException:
        os.remove(temp_path)
        raise
    except Exception as e:
        os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Falha ao restaurar: {e}")

    # 2) Só agora mexemos no DB real
    engine.dispose()

    anterior_tmp = anterior_path + ".tmp"
    anterior_pronto = False
    try:
        if os.path.exists(DB_PATH):
            # Copiar ao lado e renomear: o `.anterior` só é substituído quando
            # a cópia nova está completa
            shutil.copy2(DB_PATH, anterior_tmp)
            os.replace(anterior_tmp, anterior_path)
            anterior_pronto = True

        # Limpar WAL/SHM antes de mover
        _limpar_wal_shm(DB_PATH)
        os.replace(temp_path, DB_PATH)

        # 3) Verificação pós-troca: a MESMA validação sobre a BD trocada
        _validar_estrutura(DB_PATH)

    except Exception as e:
        # rollback
        engine.dispose()
        try:
            # Só o `.anterior` deste pedido serve para repor: se a cópia falhou,
            # a BD ainda não foi tocada e um `.anterior` antigo apagaria dados
            if anterior_pronto:
                shutil.copy2(anterior_path, anterior_tmp)
                os.replace(anterior_tmp, DB_PATH)
            _limpar_wal_shm(DB_PATH)
        except Exception:
            # rollback também falhou — pelo menos não esconder o erro original
            pass
        for resto in (temp_path, anterior_tmp):
            try:
                if os.path.exists(resto):
                    os.remove(resto)
            except OSError:
                pass
        _limpar_wal_shm(DB_PATH)
        raise HTTPException(status_code=500, detail=f"Falha ao restaurar: {e}")

    # 4) O `.anterior` fica no disco: é substituído no restauro seguinte
    return {"ok": True, "mensagem": "Base de dados restaurada"}

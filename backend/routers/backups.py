# backend/routers/backups.py
import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import text
from database import engine, DB_PATH

router = APIRouter(prefix="/backups", tags=["backups"])

@router.get("/exportar")
def exportar_backup():
    # Forçamos o dump para o ficheiro estar atualizado
    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE);"))
    
    return FileResponse(
        path=DB_PATH,
        filename="rastreio_backup.db",
        media_type="application/octet-stream"
    )

@router.post("/importar")
async def importar_backup(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith('.db'):
        raise HTTPException(status_code=400, detail="Ficheiro inválido")

    engine.dispose()

    try:
        # Criar backup de segurança dentro de backend/
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, DB_PATH + '.anterior')
        
        # Limpar logs
        for extra in [DB_PATH + "-wal", DB_PATH + "-shm"]:
            if os.path.exists(extra):
                os.remove(extra)

        conteudo = await file.read()
        
        # Escrita atómica
        temp_path = DB_PATH + ".tmp"
        with open(temp_path, 'wb') as f:
            f.write(conteudo)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, DB_PATH)
        
        return {"ok": True, "mensagem": "Base de dados restaurada"}
    
    except Exception as e:
        if os.path.exists(DB_PATH + '.anterior'):
            shutil.copy2(DB_PATH + '.anterior', DB_PATH)
        raise HTTPException(status_code=500, detail=str(e))
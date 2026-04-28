from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text
from database import engine
import shutil
import os
import tempfile

router = APIRouter(prefix="/backups", tags=["backups"])

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'rastreio.db'))

@router.get("/exportar")
def exportar_backup():
    # Cria ficheiro temporário para o backup
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()

    with engine.connect() as conn:
        conn.execute(text(f"VACUUM INTO '{tmp.name}'"))

    return FileResponse(
        path=tmp.name,
        filename="rastreio_backup.db",
        media_type="application/octet-stream"
    )

@router.post("/importar")
async def importar_backup(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith('.db'):
        raise HTTPException(status_code=400, detail="Ficheiro inválido. Tem de ser .db")

    # 1. Fechar todas as conexões ativas para libertar o ficheiro
    engine.dispose()

    try:
        # 2. Backup de segurança
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, DB_PATH + '.anterior')

        # 3. Escrita do novo ficheiro
        with open(DB_PATH, 'wb') as f:
            conteudo = await file.read()
            f.write(conteudo)
            
        return {"ok": True, "mensagem": "Base de dados restaurada com sucesso"}
    
    except Exception as e:
        # Se algo falhar, tentamos restaurar o .anterior
        if os.path.exists(DB_PATH + '.anterior'):
            shutil.copy2(DB_PATH + '.anterior', DB_PATH)
        raise HTTPException(status_code=500, detail=f"Erro ao restaurar: {str(e)}")
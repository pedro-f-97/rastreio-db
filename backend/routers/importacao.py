from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, PerfilImportacao as PerfilImportacaoModel
from parser_importacao import parse_ficheiro
from importador_transacoes import importar_transacoes

router = APIRouter(prefix="/importacao", tags=["importacao"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _obter_perfil(perfil_id: int, db: Session) -> PerfilImportacaoModel:
    perfil = db.query(PerfilImportacaoModel).filter(PerfilImportacaoModel.id == perfil_id).first()
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return perfil

@router.post("/preview")
async def preview_extrato(perfil_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    perfil = _obter_perfil(perfil_id, db)
    conteudo = await file.read()
    try:
        resultado = parse_ficheiro(conteudo, perfil)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    linhas_preview = resultado["transacoes"][:10]
    # Converter dates para string para serialização JSON
    for linha in linhas_preview:
        linha["data"] = str(linha["data"])

    return {
        "linhas_preview": linhas_preview,
        "total_linhas": resultado["total_linhas"],
        "erros": resultado["erros"],
    }

@router.post("/importar")
async def importar_extrato(perfil_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    perfil = _obter_perfil(perfil_id, db)
    conteudo = await file.read()
    try:
        resultado = parse_ficheiro(conteudo, perfil)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resultado["transacoes"] and resultado["erros"]:
        raise HTTPException(status_code=400, detail="Nenhuma transação válida encontrada. Verifica o perfil.")

    return importar_transacoes(resultado["transacoes"], db)
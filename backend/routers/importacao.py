from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import PerfilImportacao as PerfilImportacaoModel, get_db
from importador_transacoes import importar_transacoes
from parser_importacao import parse_ficheiro

router = APIRouter(prefix="/importacao", tags=["importacao"])


def _obter_perfil(perfil_id: int, db: Session) -> PerfilImportacaoModel:
    perfil = db.query(PerfilImportacaoModel).filter(PerfilImportacaoModel.id == perfil_id).first()
    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return perfil


@router.post("/preview")
async def preview_extrato(
    perfil_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
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
async def importar_extrato(
    perfil_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    perfil = _obter_perfil(perfil_id, db)
    conteudo = await file.read()
    try:
        resultado = parse_ficheiro(conteudo, perfil)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Uma linha com erro recusa o ficheiro inteiro: não se importa metade (D12d, D29)
    erros = resultado["erros"]
    if erros:
        n = len(erros)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Nada foi importado: o ficheiro tem {n} linha{'s' if n != 1 else ''} com erro "
                f"(a primeira é a linha {erros[0]['linha']}: {erros[0]['erro']}). "
                "Corrige o ficheiro ou o perfil; a pré-visualização mostra todas."
            ),
        )
    return importar_transacoes(resultado["transacoes"], db, conta_id=perfil.conta_id)

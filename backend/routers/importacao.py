from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import (
    Importacao,
    MovimentoAtivo,
    PerfilImportacao as PerfilImportacaoModel,
    Transacao,
    get_db,
)
from importador_transacoes import importar_transacoes
from parser_importacao import parse_ficheiro
from routers.patrimonio import _recusar_sobre_venda

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
    # Sem conta, as transacções contariam nas estatísticas mas nunca na liquidez
    if perfil.conta_id is None:
        raise HTTPException(
            status_code=400,
            detail="Este perfil não tem conta associada. Edita o perfil e escolhe uma conta.",
        )
    conteudo = await file.read()
    try:
        resultado = parse_ficheiro(conteudo, perfil)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Uma linha com erro recusa o ficheiro inteiro: não se importa metade
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
    return importar_transacoes(
        resultado["transacoes"], db, conta_id=perfil.conta_id, ficheiro=file.filename or ""
    )


def _ultimas_por_conta(db: Session) -> set[int]:
    """O id da importação mais recente de cada conta: só essas se desfazem.

    Os ids crescem com o tempo, por isso a mais recente é a de id maior.
    """
    return {id_ for (id_,) in db.query(func.max(Importacao.id)).group_by(Importacao.conta_id).all()}


@router.get("/historico")
def historico_importacoes(db: Session = Depends(get_db)):
    ultimas = _ultimas_por_conta(db)
    importacoes = db.query(Importacao).order_by(Importacao.id.desc()).all()
    return [
        {
            "id": i.id,
            "data_hora": i.data_hora,
            "conta_id": i.conta_id,
            "conta_nome": i.conta.nome,
            "ficheiro": i.ficheiro,
            "inseridas": i.inseridas,
            "duplicadas": i.duplicadas,
            "pode_desfazer": i.id in ultimas,
        }
        for i in importacoes
    ]


@router.delete("/{importacao_id}", status_code=204)
def desfazer_importacao(
    importacao_id: int, apagar_movimentos: bool = False, db: Session = Depends(get_db)
):
    importacao = db.get(Importacao, importacao_id)
    if importacao is None:
        raise HTTPException(status_code=404, detail="Importação não encontrada.")
    # Uma importação anterior pode ter linhas que as seguintes deram como
    # duplicadas: desfazê-la apagava-as, embora o extracto seguinte as trouxesse
    if importacao.id not in _ultimas_por_conta(db):
        raise HTTPException(
            status_code=409,
            detail="Só se pode desfazer a importação mais recente de cada conta.",
        )

    ids_transacoes = select(Transacao.id).where(Transacao.importacao_id == importacao_id)
    movimentos = (
        db.query(MovimentoAtivo)
        .filter(MovimentoAtivo.transacao_id.in_(ids_transacoes))
        .order_by(MovimentoAtivo.data, MovimentoAtivo.id)
        .all()
    )
    if movimentos and not apagar_movimentos:
        # O ecrã mostra-os e pergunta; só com a confirmação se apagam
        raise HTTPException(
            status_code=409,
            detail={
                "mensagem": "Há transações desta importação já tratadas como ativos.",
                "movimentos": [
                    {
                        "id": m.id,
                        "ativo_nome": m.ativo.nome,
                        "tipo_movimento": m.tipo_movimento.value,
                        "data": str(m.data),
                        "valor_total": m.valor_total,
                    }
                    for m in movimentos
                ],
            },
        )

    ativos = {m.ativo for m in movimentos}
    for m in movimentos:
        db.delete(m)
    # Como ao apagar um movimento à mão: sem a compra, uma venda posterior não
    # pode ficar com mais unidades do que as que havia. Recusa e desfaz tudo
    for ativo in ativos:
        _recusar_sobre_venda(db, ativo)

    db.query(Transacao).filter(Transacao.importacao_id == importacao_id).delete(
        synchronize_session=False
    )
    db.delete(importacao)
    db.commit()

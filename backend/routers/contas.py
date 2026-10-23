from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import schemas
from database import Conta as ContaModel, Transacao as TransacaoModel, get_db
from servicos.patrimonio_serv import saldo_conta_em
from servicos.verificacao_saldo import verificar_saldo

router = APIRouter(prefix="/contas", tags=["contas"])


@router.get("/", response_model=List[schemas.Conta])
def listar_contas(incluir_inativas: bool = Query(False), db: Session = Depends(get_db)):
    q = db.query(ContaModel)
    if not incluir_inativas:
        q = q.filter(ContaModel.ativa == True)
    return q.order_by(ContaModel.nome).all()


@router.post("/", response_model=schemas.Conta)
def criar_conta(payload: schemas.ContaCreate, db: Session = Depends(get_db)):
    existente = db.query(ContaModel).filter(ContaModel.nome == payload.nome).first()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe uma conta com este nome.")
    conta = ContaModel(**payload.model_dump())
    db.add(conta)
    db.commit()
    db.refresh(conta)
    return conta


@router.put("/{conta_id}", response_model=schemas.Conta)
def actualizar_conta(conta_id: int, payload: schemas.ContaUpdate, db: Session = Depends(get_db)):
    conta = db.query(ContaModel).filter(ContaModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    for campo, valor in payload.model_dump(exclude_none=True).items():
        setattr(conta, campo, valor)
    db.commit()
    db.refresh(conta)
    return conta


@router.delete("/{conta_id}")
def apagar_ou_desativar_conta(conta_id: int, db: Session = Depends(get_db)):
    conta = db.query(ContaModel).filter(ContaModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    tem_transacoes = db.query(TransacaoModel).filter(TransacaoModel.conta_id == conta_id).first()
    if tem_transacoes:
        conta.ativa = False
        db.commit()
        return {"acao": "desativada", "conta_id": conta_id}
    if conta.perfis_importacao:
        # Apagada, a conta sairia dos perfis sem aviso, e um perfil sem conta
        # não importa
        raise HTTPException(
            status_code=409,
            detail="Não é possível apagar uma conta com perfis de importação associados.",
        )
    db.delete(conta)
    db.commit()
    return {"acao": "eliminada", "conta_id": conta_id}


@router.get("/{conta_id}/saldo")
def saldo_conta(conta_id: int, db: Session = Depends(get_db)):
    conta = db.query(ContaModel).filter(ContaModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    saldo = saldo_conta_em(db, conta, date.today())
    return {
        "conta_id": conta_id,
        "nome": conta.nome,
        "saldo_referencia": float(conta.saldo_referencia),
        "data_referencia": str(conta.data_referencia),
        "saldo_atual": saldo,
    }


@router.get("/{conta_id}/verificacao-saldo")
def verificacao_saldo(conta_id: int, db: Session = Depends(get_db)):
    conta = db.query(ContaModel).filter(ContaModel.id == conta_id).first()
    if not conta:
        raise HTTPException(status_code=404, detail="Conta não encontrada.")
    return verificar_saldo(db, conta)

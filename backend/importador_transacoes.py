import os
import shutil
from sqlalchemy.orm import Session
from database import Transacao, RegraCategorizacao, DB_PATH
from sqlalchemy import or_

def aplicar_regras(transacao: Transacao, regras: list[RegraCategorizacao]):
    if transacao.descricao.upper().startswith("TRF"):
        return
    for regra in regras:
        if regra.palavra_chave.upper() in transacao.descricao.upper():
            if transacao.categoria_id is None:
                transacao.categoria_id = regra.categoria_id
                transacao.subcategoria_id = regra.subcategoria_id
            elif transacao.categoria_id == regra.categoria_id and transacao.subcategoria_id is None:
                transacao.subcategoria_id = regra.subcategoria_id
            break

def importar_transacoes(transacoes_parsed: list[dict], db: Session, conta_id: int | None = None) -> dict:
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, DB_PATH + ".pre_import")

    regras = db.query(RegraCategorizacao).all()
    inseridas = 0
    duplicadas = 0

    try:
        query_existentes = db.query(
            Transacao.data,
            Transacao.descricao,
            Transacao.valor,
            Transacao.saldo
        ).filter(Transacao.conta_id == conta_id)

        existentes = set(
            (r.data, r.descricao, r.valor, r.saldo)
            for r in query_existentes
        )

        for t in transacoes_parsed:
            chave = (t["data"], t["descricao"], t["valor"], t["saldo"])

            if chave in existentes:
                duplicadas += 1
                continue

            nova = Transacao(
                data=t["data"],
                descricao=t["descricao"],
                valor=t["valor"],
                saldo=t["saldo"],
                conta_id=conta_id,
            )
            aplicar_regras(nova, regras)
            db.add(nova)
            inseridas += 1

        db.commit()
    except Exception as e:
        db.rollback()
        raise

    return {"inseridas": inseridas, "duplicadas": duplicadas}
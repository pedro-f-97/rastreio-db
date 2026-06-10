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

def importar_transacoes(transacoes_parsed: list[dict], db: Session) -> dict:
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, DB_PATH + ".pre_import")

    regras = db.query(RegraCategorizacao).all()
    inseridas = 0
    duplicadas = 0

    try:
        for t in transacoes_parsed:
            filtro_saldo = (
                Transacao.saldo == t["saldo"]
                if t["saldo"] is not None
                else Transacao.saldo.is_(None)
            )
            existente = db.query(Transacao).filter(
                Transacao.data == t["data"],
                Transacao.descricao == t["descricao"],
                Transacao.valor == t["valor"],
                filtro_saldo,
            ).first()

            if existente:
                duplicadas += 1
                #print(f"DUPLICADA: {t['data']} {t['descricao']} {t['valor']}")
                continue

            nova = Transacao(
                data=t["data"],
                descricao=t["descricao"],
                valor=t["valor"],
                saldo=t["saldo"],
            )
            aplicar_regras(nova, regras)
            db.add(nova)
            inseridas += 1
            #print(f"INSERIDA: {t['data']} {t['descricao']} {t['valor']}")

        db.commit()
    except Exception as e:
        db.rollback()
        #print(f"ERRO: {e}")
        raise

    return {"inseridas": inseridas, "duplicadas": duplicadas}
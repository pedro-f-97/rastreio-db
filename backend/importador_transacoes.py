from collections import Counter

from sqlalchemy.orm import Session

from database import RegraCategorizacao, Transacao


def casa_palavra(palavra_chave: str, descricao: str) -> bool:
    """A comparação única das regras: ignora maiúsculas, também nas letras
    acentuadas, e trata a palavra-chave como texto literal."""
    return palavra_chave.upper() in descricao.upper()


def aplicar_regras(transacao: Transacao, regras: list[RegraCategorizacao]):
    # Fase 1: verificar regras de exclusão (categoria_id = None)
    for regra in regras:
        if regra.categoria_id is not None:
            continue
        if casa_palavra(regra.palavra_chave, transacao.descricao):
            return  # ← transação fica sem categoria

    # Fase 2: aplicar primeira regra de categorização que corresponde
    for regra in regras:
        if regra.categoria_id is None:
            continue
        if casa_palavra(regra.palavra_chave, transacao.descricao):
            if transacao.categoria_id is None:
                transacao.categoria_id = regra.categoria_id
                transacao.subcategoria_id = regra.subcategoria_id
            elif transacao.categoria_id == regra.categoria_id and transacao.subcategoria_id is None:
                transacao.subcategoria_id = regra.subcategoria_id
            break


def regras_por_precedencia(db: Session) -> list[RegraCategorizacao]:
    """Regras pela ordem em que são avaliadas: a palavra-chave mais longa
    primeiro, porque é a mais específica, e em empate a mais antiga."""
    regras = db.query(RegraCategorizacao).all()
    return sorted(regras, key=lambda r: (-len(r.palavra_chave), r.id))


def importar_transacoes(
    transacoes_parsed: list[dict], db: Session, conta_id: int | None = None
) -> dict:
    regras = regras_por_precedencia(db)
    inseridas = 0
    duplicadas = 0

    try:
        query_existentes = db.query(
            Transacao.data, Transacao.descricao, Transacao.valor, Transacao.saldo
        ).filter(Transacao.conta_id == conta_id)

        # Conta-se quantas vezes cada linha já existe: cada cópia na BD absorve
        # uma linha igual do ficheiro, e as restantes são transações novas
        # (dois cafés iguais no mesmo dia, um deles só no extracto seguinte)
        existentes = Counter((r.data, r.descricao, r.valor, r.saldo) for r in query_existentes)

        for t in transacoes_parsed:
            chave = (t["data"], t["descricao"], t["valor"], t["saldo"])

            if existentes[chave] > 0:
                existentes[chave] -= 1
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
    except Exception:
        db.rollback()
        raise

    return {"inseridas": inseridas, "duplicadas": duplicadas}

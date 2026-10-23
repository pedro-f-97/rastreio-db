from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from database import Importacao, RegraCategorizacao, Transacao


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
    transacoes_parsed: list[dict],
    db: Session,
    conta_id: int,
    ficheiro: str,
    compara_saldo: bool = True,
) -> dict:
    regras = regras_por_precedencia(db)
    novas = []
    duplicadas = 0

    try:
        query_existentes = db.query(
            Transacao.data, Transacao.descricao, Transacao.valor, Transacao.saldo
        ).filter(Transacao.conta_id == conta_id)

        # Sem saldo no extracto, o saldo da BD não entra na comparação: é o que
        # se escreveu à mão, e a linha do ficheiro é a mesma transação
        def chave(data, descricao, valor, saldo):
            return (data, descricao, valor, saldo) if compara_saldo else (data, descricao, valor)

        # Conta-se quantas vezes cada linha já existe: cada cópia na BD absorve
        # uma linha igual do ficheiro, e as restantes são transações novas
        # (dois cafés iguais no mesmo dia, um deles só no extracto seguinte)
        existentes = Counter(chave(r.data, r.descricao, r.valor, r.saldo) for r in query_existentes)

        for t in transacoes_parsed:
            c = chave(t["data"], t["descricao"], t["valor"], t["saldo"])

            if existentes[c] > 0:
                existentes[c] -= 1
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
            novas.append(nova)

        # Só uma importação que inseriu alguma coisa fica registada: é a que
        # se pode desfazer. Tudo no mesmo commit que as transacções
        if novas:
            importacao = Importacao(
                data_hora=datetime.now(),
                conta_id=conta_id,
                ficheiro=ficheiro,
                inseridas=len(novas),
                duplicadas=duplicadas,
            )
            db.add(importacao)
            db.flush()
            for nova in novas:
                nova.importacao_id = importacao.id
            db.add_all(novas)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"inseridas": len(novas), "duplicadas": duplicadas}

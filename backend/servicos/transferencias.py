"""As transferências sem par: as que não têm a outra metade numa conta registada.

Uma transferência fica fora das métricas porque se pressupõe que o dinheiro só
mudou de conta. Isso só é verdade se a saída numa conta tiver a entrada
correspondente noutra; sem ela, o dinheiro sai ou entra no património sem
contar como despesa nem como receita.
"""

from itertools import combinations

from sqlalchemy.orm import Session, joinedload

from database import Categoria, TipoCategoria, Transacao
from servicos.dinheiro import arredondar

# Duas transferências emparelham com as datas a esta distância, no máximo: uma
# transferência entre bancos chega a demorar uns dias úteis, mais o fim de semana
DIAS_PAR = 7


def _centimos(valor) -> int:
    return round(arredondar(valor) * 100)


def transferencias_sem_par(db: Session) -> list[Transacao]:
    """As transferências sem par, por data.

    Duas transferências fazem um par se estão em contas diferentes, têm valores
    simétricos ao cêntimo e as datas a `DIAS_PAR` dias, no máximo. Cada uma só
    entra num par. Os pares formam-se do mais próximo no tempo para o mais
    afastado, e em empate pelo mais antigo: duas saídas de 100 € e uma entrada
    de 100 € deixam sem par a saída mais afastada da entrada.
    """
    transferencias = (
        db.query(Transacao)
        .join(Categoria, Transacao.categoria_id == Categoria.id)
        .filter(Categoria.tipo == TipoCategoria.transferencia)
        .options(joinedload(Transacao.conta))
        .order_by(Transacao.data, Transacao.id)
        .all()
    )

    # Só se comparam as transferências com o mesmo valor absoluto
    por_valor: dict[int, list[Transacao]] = {}
    for t in transferencias:
        por_valor.setdefault(abs(_centimos(t.valor)), []).append(t)

    candidatos = []
    for grupo in por_valor.values():
        for a, b in combinations(grupo, 2):
            dias = abs((b.data - a.data).days)
            if (
                a.conta_id != b.conta_id
                and _centimos(a.valor) == -_centimos(b.valor)
                and dias <= DIAS_PAR
            ):
                # `combinations` mantém a ordem por data e id: `a` é a mais antiga
                candidatos.append((dias, a.data, a.id, b.id, a, b))

    emparelhadas = set()
    for *_, a, b in sorted(candidatos, key=lambda c: c[:4]):
        if a.id not in emparelhadas and b.id not in emparelhadas:
            emparelhadas |= {a.id, b.id}

    return [t for t in transferencias if t.id not in emparelhadas]

"""A pragma `foreign_keys` está ligada (D1).

O SQLite só aplica as chaves estrangeiras com `PRAGMA foreign_keys = ON`, e a
pragma é por conexão: `database.ligar_chaves_estrangeiras` liga-a em cada
conexão nova da engine da app, e o `conftest.py` faz o mesmo na engine
in-memory dos testes. Sem `ON DELETE` declarado, vale o `NO ACTION` do
SQLite: um pai com filhos não se apaga, e um filho não aponta para um pai que
não existe. Cada endpoint trata dos filhos antes de apagar o pai (ver os
testes de cada router); estes testes fixam só a rede de segurança da BD.
"""

from datetime import date

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError

import database
from database import Categoria, TipoCategoria, Transacao


def test_engine_da_app_liga_a_pragma():
    """Uma conexão da engine da app tem `foreign_keys = 1`.

    A engine aponta para a BD temporária do `conftest.py`
    (`test_seguranca_bd.py` garante-o), nunca para a real.
    """
    database.garantir_pasta_dados()
    with database.engine.connect() as con:
        assert con.execute(text("PRAGMA foreign_keys")).scalar() == 1


def _categoria_com_transacao(session):
    cat = Categoria(nome="Casa", tipo=TipoCategoria.despesa)
    session.add(cat)
    session.commit()
    session.add(
        Transacao(data=date(2025, 3, 10), descricao="Pingo Doce", valor=-50.0, categoria_id=cat.id)
    )
    session.commit()
    return cat


def test_apagar_pai_com_filhos_e_recusado_pela_bd(session):
    """Um `DELETE` directo de uma categoria com uma transacção falha.

    É o caso que, com a pragma desligada, deixava a transacção órfã: passava
    sem erro e a transacção desaparecia das estatísticas.

    Estado final da BD: 1 categoria e 1 transacção a apontar para ela.
    """
    cat = _categoria_com_transacao(session)

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        session.execute(delete(Categoria).where(Categoria.id == cat.id))
    session.rollback()

    assert session.query(Categoria).count() == 1
    assert session.query(Transacao).one().categoria_id == cat.id


def test_filho_a_apontar_para_pai_inexistente_e_recusado_pela_bd(session):
    """Uma transacção com `categoria_id` 999, que não existe, não é gravada.

    Estado final da BD: 0 transacções.
    """
    session.add(
        Transacao(data=date(2025, 3, 10), descricao="Pingo Doce", valor=-50.0, categoria_id=999)
    )

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        session.commit()
    session.rollback()

    assert session.query(Transacao).count() == 0

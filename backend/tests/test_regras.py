"""
Testes para POST /api/regras/aplicar-em-massa.

Cobrem o bug B3 original (payload não validado -> KeyError -> 500 quando
faltava uma chave) e o comportamento correto depois da validação Pydantic.

NOTA: o schemas.py atual não foi fornecido nesta análise; os testes assumem
o formato de payload confirmado experimentalmente: {"itens": [{"id": int,
"categoria_id": int, "subcategoria_id": int | None}]}. Se os nomes dos
campos no schema real forem diferentes, ajustar aqui — a lógica dos testes
mantém-se.
"""
from datetime import date

from database import Categoria, Subcategoria, Transacao


def _seed_transacao_categoria_subcategoria(db_session):
    cat = Categoria(nome="Alimentação", tipo="despesa")
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)

    sub = Subcategoria(nome="Supermercado", categoria_id=cat.id)
    db_session.add(sub)
    db_session.commit()
    db_session.refresh(sub)

    t = Transacao(data=date(2024, 1, 1), descricao="PINGO DOCE", valor=-30.0)
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    return t, cat, sub


def test_payload_sem_categoria_id_e_rejeitado_com_422_nao_500(client, db_session):
    t, _cat, _sub = _seed_transacao_categoria_subcategoria(db_session)

    r = client.post("/api/regras/aplicar-em-massa", json={"itens": [{"id": t.id}]})

    assert r.status_code == 422
    assert r.status_code != 500


def test_subcategoria_de_outra_categoria_e_marcada_invalida(client, db_session):
    t, _cat, sub = _seed_transacao_categoria_subcategoria(db_session)

    outra_cat = Categoria(nome="Transporte", tipo="despesa")
    db_session.add(outra_cat)
    db_session.commit()
    db_session.refresh(outra_cat)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{"id": t.id, "categoria_id": outra_cat.id, "subcategoria_id": sub.id}]
    })

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aplicadas"] == 0
    assert corpo["invalidas"] == [t.id]


def test_payload_valido_e_coerente_aplica_categoria_e_subcategoria(client, db_session):
    t, cat, sub = _seed_transacao_categoria_subcategoria(db_session)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{"id": t.id, "categoria_id": cat.id, "subcategoria_id": sub.id}]
    })

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aplicadas"] == 1
    assert corpo["ignoradas"] == []
    assert corpo["invalidas"] == []

    db_session.refresh(t)
    assert t.categoria_id == cat.id
    assert t.subcategoria_id == sub.id


def test_id_de_transacao_inexistente_e_ignorado_nao_rebenta(client, db_session):
    _t, cat, _sub = _seed_transacao_categoria_subcategoria(db_session)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{"id": 999999, "categoria_id": cat.id}]
    })

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aplicadas"] == 0
    assert corpo["ignoradas"] == [999999]


def test_categoria_inexistente_e_marcada_invalida(client, db_session):
    t, _cat, _sub = _seed_transacao_categoria_subcategoria(db_session)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{"id": t.id, "categoria_id": 999999}]
    })

    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aplicadas"] == 0
    assert corpo["invalidas"] == [t.id]


def test_lista_vazia_devolve_resultado_vazio_sem_erro(client, db_session):
    r = client.post("/api/regras/aplicar-em-massa", json={"itens": []})

    assert r.status_code == 200
    assert r.json() == {"aplicadas": 0, "ignoradas": [], "invalidas": []}

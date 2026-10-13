"""Testes da API de tipos de ativo (`/api/tipos-ativo/`).

Cobre os quatro endpoints de `backend/routers/tipos_ativo.py`:

* `GET /` (`:8-10`) — lista ordenada por nome;
* `POST /` (`:12-21`) — criação, com pré-checagem de nome duplicado (`:14-16`,
  409);
* `PUT /{tipo_id}` (`:23-32`) — renomeação; 404 se não existir; **sem**
  pré-checagem de duplicado;
* `DELETE /{tipo_id}` (`:34-43`) — 404 se não existir, 409 se tiver ativos
  (`if tipo.ativos:`, `:39`), senão apaga.

Etiquetas: `# DEVIDA-TECNICA: D24` no PUT com nome duplicado (mesma classe do
D24: nome duplicado responde 500 em vez de 409/400) e `# DEVIDA-TECNICA: D1` no
apagar com ativos (a pré-checagem protege por via da `relationship`, não da
pragma). Ver `docs/divida-tecnica.md`.

Valores esperados calculados à mão e escritos como constantes; datas fixas em
2024. Nenhum teste toca na base de dados real (ver `conftest.py`). Como a
fixture `client` e a fixture `session` partilham a sessão SQLAlchemy, as
verificações de estado começam por `session.expire_all()`.
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from database import Ativo, TipoAtivo, TipoContabilizacao


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _tipos(session):
    """Semeia ETF (tem_unidades=True) e Imóvel (False). Devolve-os por `id`."""
    etf = TipoAtivo(nome="ETF", tem_unidades=True)
    imovel = TipoAtivo(nome="Imóvel", tem_unidades=False)
    session.add_all([etf, imovel])
    session.commit()
    session.refresh(etf)
    session.refresh(imovel)
    return etf, imovel


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

def test_listar_tipos_ativo_ordenados_por_nome(client, session):
    """`GET /` devolve os tipos com `id`, `nome` e `tem_unidades`.

    Cálculo à mão (`:10`, `order_by(TipoAtivo.nome)`): "ETF" < "Imóvel" na
    ordem de bytes, por isso ETF vem primeiro. Esperado:
      [ {id: etf.id, nome: ETF,    tem_unidades: True},
        {id: imovel.id, nome: Imóvel, tem_unidades: False} ]

    Estado final da BD: 2 tipos de ativo; sem ativos.
    """
    etf, imovel = _tipos(session)

    r = client.get("/api/tipos-ativo/")

    assert r.status_code == 200
    assert r.json() == [
        {"id": etf.id, "nome": "ETF", "tem_unidades": True},
        {"id": imovel.id, "nome": "Imóvel", "tem_unidades": False},
    ]
    assert session.query(TipoAtivo).count() == 2


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------

def test_criar_tipo_ativo_e_duplicado_da_409(client, session):
    """Criar funciona; um nome repetido é recusado com 409 antes de escrever.

    Cálculo à mão (`:14-16`): a pré-checagem compara `TipoAtivo.nome`; "Crypto"
    não existe, cria (id 3, porque ETF=1 e Imóvel=2); "ETF" já existe, a linha
    16 responde `409` e nada é escrito. Esperado:
      POST Crypto -> 200 {id: 3, nome: "Crypto", tem_unidades: True}
      POST ETF    -> 409 {"detail": "Já existe um tipo de ativo com este nome."}

    Estado final da BD: 3 tipos (os 2 semeados + Crypto).
    """
    _tipos(session)

    r = client.post("/api/tipos-ativo/", json={"nome": "Crypto", "tem_unidades": True})
    assert r.status_code == 200
    assert r.json() == {"id": 3, "nome": "Crypto", "tem_unidades": True}

    r_dup = client.post("/api/tipos-ativo/", json={"nome": "ETF"})
    assert r_dup.status_code == 409
    assert r_dup.json() == {"detail": "Já existe um tipo de ativo com este nome."}

    assert session.query(TipoAtivo).count() == 3


# ---------------------------------------------------------------------------
# PUT /{tipo_id}
# ---------------------------------------------------------------------------

def test_renomear_tipo_ativo_e_404(client, session):
    """Renomear altera nome e `tem_unidades`; id inexistente dá 404.

    Cálculo à mão (`:25-32`):
      PUT /{imovel.id} {"nome":"Imobiliário","tem_unidades":True} -> encontra,
        escreve os dois campos (`:28-29`) e devolve 200 com os novos valores
      PUT /9999 -> a `first()` (`:25`) devolve None -> 404
        {"detail": "Tipo de ativo não encontrado."}

    Estado final da BD: Imóvel passa a "Imobiliário"/True; 2 tipos.
    """
    _etf, imovel = _tipos(session)

    r = client.put(f"/api/tipos-ativo/{imovel.id}",
                   json={"nome": "Imobiliário", "tem_unidades": True})
    assert r.status_code == 200
    assert r.json() == {"id": imovel.id, "nome": "Imobiliário", "tem_unidades": True}

    r_404 = client.put("/api/tipos-ativo/9999",
                       json={"nome": "X", "tem_unidades": False})
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Tipo de ativo não encontrado."}

    session.expire_all()
    assert session.query(TipoAtivo).count() == 2


def test_renomear_tipo_ativo_para_nome_duplicado_integrity(client, session):
    # DEVIDA-TECNICA: D24 — o PUT não pré-checa o nome duplicado (ao contrário
    # do POST, `:14-16`), pelo que `tipos_ativo.nome` (`unique=True`,
    # database.py:125) rebenta no `commit()` (`:30`) com IntegrityError. Em
    # produção é um 500. Mesma classe do D24 das categorias.
    """Renomear para um nome existente rebenta com `IntegrityError`.

    Cálculo à mão (`:28-30`): a linha 28 escreve "ETF" em Imóvel, mas já existe
    um tipo "ETF"; o `commit()` da linha 30 falha com
    `UNIQUE constraint failed: tipos_ativo.nome`. `tem_unidades` também é
    escrito (linha 29) e é revertido pelo rollback do teste.

    Estado final da BD: o rollback desfaz a tentativa; Imóvel mantém o nome e
    continuam 2 tipos.
    """
    _etf, imovel = _tipos(session)

    with pytest.raises(IntegrityError,
                       match="UNIQUE constraint failed: tipos_ativo.nome"):
        client.put(f"/api/tipos-ativo/{imovel.id}",
                   json={"nome": "ETF", "tem_unidades": True})
    session.rollback()

    session.expire_all()
    imovel = session.get(TipoAtivo, imovel.id)
    assert imovel.nome == "Imóvel"
    assert imovel.tem_unidades is False
    assert session.query(TipoAtivo).count() == 2


# ---------------------------------------------------------------------------
# DELETE /{tipo_id}
# ---------------------------------------------------------------------------

def test_apagar_tipo_ativo_com_ativos_da_409(client, session):
    # DEVIDA-TECNICA: D1 — a pré-checagem `if tipo.ativos:` (`:39`) protege por
    # via da `relationship`, não da pragma `foreign_keys`; `ativos.tipo_id` é
    # `NOT NULL` (database.py:244).
    """Um tipo com ativos associados não é apagado: 409.

    Cálculo à mão (`:39-40`): o tipo ETF tem um ativo (nome "VWCE"), logo
    `tipo.ativos` não é vazio, a linha 40 responde `409`
    {"detail": "Não é possível apagar um tipo com ativos associados."} e a
    linha 41 não corre.

    Estado final da BD: 2 tipos e 1 ativo; nada muda.
    """
    etf, _imovel = _tipos(session)
    ativo = Ativo(nome="VWCE", tipo_id=etf.id,
                  contabilizacao=TipoContabilizacao.investimento)
    session.add(ativo)
    session.commit()

    r = client.delete(f"/api/tipos-ativo/{etf.id}")

    assert r.status_code == 409
    assert r.json() == {"detail": "Não é possível apagar um tipo com ativos associados."}
    assert session.query(TipoAtivo).count() == 2
    assert session.query(Ativo).count() == 1


def test_apagar_tipo_ativo_sem_ativos_e_inexistente(client, session):
    """Sem ativos, o tipo é apagado; id inexistente dá 404.

    Cálculo à mão (`:36-43`):
      DELETE /{imovel.id} -> encontra, `tipo.ativos` é vazio (falso), a linha
        41 apaga -> 200 {"ok": True}
      DELETE /9999 -> a `first()` (`:36`) devolve None -> 404
        {"detail": "Tipo de ativo não encontrado."}

    Estado final da BD: só fica o ETF (1 tipo); o 404 não altera nada.
    """
    etf, imovel = _tipos(session)

    r = client.delete(f"/api/tipos-ativo/{imovel.id}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert session.query(TipoAtivo).count() == 1

    r_404 = client.delete("/api/tipos-ativo/9999")
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Tipo de ativo não encontrado."}

    session.expire_all()
    assert session.get(TipoAtivo, etf.id) is not None
    assert session.query(TipoAtivo).count() == 1

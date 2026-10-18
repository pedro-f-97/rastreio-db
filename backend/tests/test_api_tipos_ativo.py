"""Testes da API de tipos de ativo (`/api/tipos-ativo/`).

Cobre os quatro endpoints de `backend/routers/tipos_ativo.py`:

* `GET /` (`listar_tipos_ativo`) — lista ordenada por nome;
* `POST /` (`criar_tipo_ativo`) — criação, com pré-checagem de nome duplicado
  (a query `existente` e o `raise` 409);
* `PUT /{tipo_id}` (`renomear_tipo_ativo`) — renomeação; 404 se não existir;
  pré-checagem de nome duplicado contra os **outros** tipos (`TipoAtivo.id !=
  tipo_id`, 409);
* `DELETE /{tipo_id}` (`apagar_tipo_ativo`) — 404 se não existir, 409 se tiver
  ativos (`if tipo.ativos:`), senão apaga.

Etiquetas: `# DEVIDA-TECNICA: D1` no apagar com ativos (a pré-checagem protege
por via da `relationship`, não da pragma). O nome duplicado no PUT, que era um
500 por `IntegrityError` e estava anotado como D24, passou a 409 — ver
`docs/divida-tecnica.md`.

Valores esperados calculados à mão e escritos como constantes; datas fixas em
2024. Nenhum teste toca na base de dados real (ver `conftest.py`). Como a
fixture `client` e a fixture `session` partilham a sessão SQLAlchemy, as
verificações de estado começam por `session.expire_all()`.
"""

from datetime import date

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

    Cálculo à mão (o `order_by(TipoAtivo.nome)` de `listar_tipos_ativo`):
    "ETF" < "Imóvel" na ordem de bytes, por isso ETF vem primeiro. Esperado:
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

    Cálculo à mão (a pré-checagem de `criar_tipo_ativo`): compara
    `TipoAtivo.nome`; "Crypto" não existe, cria (id 3, porque ETF=1 e Imóvel=2);
    "ETF" já existe, a pré-checagem responde `409` e nada é escrito. Esperado:
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

    Cálculo à mão (o corpo de `renomear_tipo_ativo`):
      PUT /{imovel.id} {"nome":"Imobiliário","tem_unidades":True} -> encontra,
        escreve os dois campos (`existente.nome` e `existente.tem_unidades`) e
        devolve 200 com os novos valores
      PUT /9999 -> a `first()` devolve None -> 404
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


def test_renomear_tipo_ativo_para_nome_duplicado_da_409(client, session):
    """Renomear para um nome existente é recusado com 409, sem escrever.

    D24 (`docs/divida-tecnica.md`): o PUT passou a pré-checar o nome contra os
    **outros** tipos (`TipoAtivo.id != tipo_id` na pré-checagem de
    `renomear_tipo_ativo`), como o POST já fazia em `criar_tipo_ativo`, pelo que
    a colisão não chega a `commit()` — em produção deixou de ser um 500 por
    `IntegrityError` (`tipos_ativo.nome` é `unique=True` no modelo `TipoAtivo`).

    Cálculo à mão:
      PUT em Imóvel {"nome": "ETF", "tem_unidades": True} -> já existe um tipo
        "ETF" noutra linha -> 409 {"detail": "Já existe um tipo de ativo com
        este nome."}, e `tem_unidades` nem chega a ser escrito

    Estado final da BD: nada muda — Imóvel mantém o nome "Imóvel" e
    `tem_unidades` False, e continuam 2 tipos.
    """
    _etf, imovel = _tipos(session)

    r = client.put(f"/api/tipos-ativo/{imovel.id}",
                   json={"nome": "ETF", "tem_unidades": True})

    assert r.status_code == 409
    assert r.json() == {"detail": "Já existe um tipo de ativo com este nome."}

    session.expire_all()
    imovel = session.get(TipoAtivo, imovel.id)
    assert imovel.nome == "Imóvel"
    assert imovel.tem_unidades is False
    assert session.query(TipoAtivo).count() == 2


def test_renomear_tipo_ativo_mantendo_o_proprio_nome_e_200(client, session):
    """Guardar um tipo sem mudar o nome não é duplicado: 200.

    D24 (`docs/divida-tecnica.md`): a pré-checagem do PUT exclui o próprio
    `tipo_id`, por isso o nome de um tipo continua a poder ser re-submetido tal
    e qual.

    Cálculo à mão:
      PUT em ETF {"nome": "ETF", "tem_unidades": True} -> a query não encontra
        OUTRO tipo com esse nome -> escreve os mesmos valores de antes e
        responde 200 {"id": <id do ETF>, "nome": "ETF", "tem_unidades": True}

    Estado final da BD: nada muda — continuam 2 tipos, sem ativos.
    """
    etf, _imovel = _tipos(session)

    r = client.put(f"/api/tipos-ativo/{etf.id}",
                   json={"nome": "ETF", "tem_unidades": True})

    assert r.status_code == 200
    assert r.json() == {"id": etf.id, "nome": "ETF", "tem_unidades": True}

    session.expire_all()
    assert session.query(TipoAtivo).count() == 2
    assert session.get(TipoAtivo, etf.id).nome == "ETF"


# ---------------------------------------------------------------------------
# DELETE /{tipo_id}
# ---------------------------------------------------------------------------

def test_apagar_tipo_ativo_com_ativos_da_409(client, session):
    # DEVIDA-TECNICA: D1 — a pré-checagem `if tipo.ativos:` de
    # `apagar_tipo_ativo` protege por via da `relationship`, não da pragma
    # `foreign_keys`; `ativos.tipo_id` é `NOT NULL` no modelo `Ativo`.
    """Um tipo com ativos associados não é apagado: 409.

    Cálculo à mão (o ramo dos ativos de `apagar_tipo_ativo`): o tipo ETF tem um
    ativo (nome "VWCE"), logo `tipo.ativos` não é vazio, o `raise` responde
    `409` {"detail": "Não é possível apagar um tipo com ativos associados."} e
    o `db.delete(tipo)` não corre.

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

    Cálculo à mão (o corpo de `apagar_tipo_ativo`):
      DELETE /{imovel.id} -> encontra, `tipo.ativos` é vazio (falso), o
        `db.delete(tipo)` apaga -> 200 {"ok": True}
      DELETE /9999 -> a `first()` devolve None -> 404
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

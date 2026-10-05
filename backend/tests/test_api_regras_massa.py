"""Testes de API de `POST /api/regras/aplicar-em-massa`.

Portados do `test_regras.py` antigo (Pedro, 16 de Setembro, commit `398130b`),
que foi escrito contra outro `conftest`: usava a fixture `db_session` e importava
`main`. Aqui usam-se as fixtures `session` e `client` do `conftest.py` actual, que
põem a base de dados em memória e montam a app a partir de `routers/` — o `main`
nunca é importado.

O que fica fixado
-----------------
O endpoint (`backend/routers/regras.py`, `aplicar_em_massa`, linha 141) recebe um
`AplicarEmMassaPayload` e devolve um `AplicarEmMassaResultado`
(`backend/schemas.py`, linhas 205 a 216):

    entrada   {"itens": [{"id": int, "categoria_id": int, "subcategoria_id": int | None}]}
    saida     {"aplicadas": int, "ignoradas": [int], "invalidas": [int]}

`categoria_id` é obrigatório, pelo que um item sem essa chave nunca chega ao
endpoint: é o Pydantic que a rejeita, com 422, e não um `KeyError` a dar 500. Foi
esse o bug B3 original, e é o primeiro teste abaixo.

Os três cestos da resposta, e o que cada um quer dizer:

* `aplicadas` — quantas transacções foram escritas: a transacção existe, a
  categoria existe, e a subcategoria, se vier, é dessa categoria.
* `ignoradas` — os `id` pedidos que não estão na base de dados.
* `invalidas` — as referências que não são coerentes: a transacção existe, mas a
  categoria não existe, ou a subcategoria é de outra categoria.

A distinção entre `ignoradas` e `invalidas` é a parte subtil: ambas deixam a
transacção por tocar, e só o motivo é diferente. Uma é um `id` que não existe, a
outra é uma referência que não é coerente com a transacção.

Valores esperados
-----------------
Não há contas a fazer aqui: o endpoint não faz aritmética, devolve contagens e
listas de `id`. Os valores esperados são escritos à mão como constantes — "uma
transacção semeada, uma aplicação" ou "nada a aplicar, e o motivo disto" — e nunca
copiados de uma execução. Os `id` usados são os que a base de dados nova atribui
por ordem de `commit` (1 à categoria, 2 à subcategoria, 3 à transacção) e o
`999999`, que não existe. As datas são fixas em 2024: nenhum teste assenta na
data de hoje.

Os testes
---------
Seis: um por ramo da resposta, mais o caso do payload inválido e o da lista
vazia. Nenhum toca no `main`, na base de dados real, nem no sistema de ficheiros.
"""

from datetime import date

from database import Categoria, Subcategoria, Transacao, TipoCategoria


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def _semeia_categoria_subcategoria_transacao(session):
    """Semeia uma categoria, uma subcategoria dessa categoria e uma transacção.

    Devolve a transacção, a categoria e a subcategoria, já com `id` atribuído.
    """
    cat = Categoria(nome="Alimentação", tipo=TipoCategoria.despesa)
    session.add(cat)
    session.commit()
    session.refresh(cat)

    sub = Subcategoria(nome="Supermercado", categoria_id=cat.id)
    session.add(sub)
    session.commit()
    session.refresh(sub)

    transacao = Transacao(
        data=date(2024, 1, 1),
        descricao="PINGO DOCE",
        valor=-30.0,
    )
    session.add(transacao)
    session.commit()
    session.refresh(transacao)

    return transacao, cat, sub


# ---------------------------------------------------------------------------
# Os seis testes
# ---------------------------------------------------------------------------

def test_payload_sem_categoria_id_da_422(client):
    """Um item sem `categoria_id` é rejeitado pelo Pydantic, com 422.

    Não chega a `aplicar_em_massa`: `AplicarEmMassaItem.categoria_id` é um `int`
    obrigatório (`schemas.py`, linha 207), e o FastAPI devolve 422 antes de
    chamar a função. É a diferença entre o 422 de hoje e o 500 do bug B3, em que
    o acesso directo ao dicionário rebentava com `KeyError`.

    O 500 original não é distinguível deste 422 por um `!= 500`: um 5xx faria o
    `TestClient` levantar a excepção em vez de responder, e o teste rebentava
    logo a seguir. Fica por isso o `== 422` e nada mais.

    Não pede `session`: com o payload inválido nada chega a ser lido da base de
    dados, e semeá-la só esconderia que a validação acontece antes de tudo.
    """
    r = client.post("/api/regras/aplicar-em-massa", json={"itens": [{"id": 1}]})

    assert r.status_code == 422


def test_subcategoria_de_outra_categoria_e_invalida(client, session):
    """Uma subcategoria que é de outra categoria deixa a transacção por tocar.

    Cálculo à mão:
      a transacção existe                        -> não vai para `ignoradas`
      a categoria pedida existe                  -> a linha 180 passa
      a subcategoria pedida existe               -> `sub` não é None
      mas `sub.categoria_id` é o da outra        -> a linha 186 é verdadeira
      logo o item entra em `invalidas`           -> aplicadas = 0, invalidas = [id]
    """
    transacao, _cat, sub = _semeia_categoria_subcategoria_transacao(session)

    outra = Categoria(nome="Transporte", tipo=TipoCategoria.despesa)
    session.add(outra)
    session.commit()
    session.refresh(outra)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{
            "id": transacao.id,
            "categoria_id": outra.id,
            "subcategoria_id": sub.id,
        }]
    })

    assert r.status_code == 200
    assert r.json() == {"aplicadas": 0, "ignoradas": [], "invalidas": [transacao.id]}


def test_payload_valido_aplica_categoria_e_subcategoria(client, session):
    """O caminho feliz: uma aplicação, zero ignoradas, zero inválidas.

    Cálculo à mão:
      a transacção existe                        -> não vai para `ignoradas`
      a categoria pedida existe                  -> a linha 180 passa
      a subcategoria é dessa mesma categoria     -> a linha 186 é falsa
      logo escreve-se                           -> aplicadas = 1

    E, no fim, a transacção tem mesmo os dois `id` apontados: o endpoint faz
    `db.commit()` na linha 194, e o teste confirma-o pela sessão, que é a mesma
    que o endpoint usa.
    """
    transacao, cat, sub = _semeia_categoria_subcategoria_transacao(session)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{
            "id": transacao.id,
            "categoria_id": cat.id,
            "subcategoria_id": sub.id,
        }]
    })

    assert r.status_code == 200
    assert r.json() == {"aplicadas": 1, "ignoradas": [], "invalidas": []}

    session.refresh(transacao)
    assert transacao.categoria_id == cat.id
    assert transacao.subcategoria_id == sub.id


def test_id_inexistente_vai_para_ignoradas(client, session):
    """Um `id` que não existe é ignorado, e não dá erro.

    Cálculo à mão:
      a consulta da linha 154 com `in_([999999])` devolve vazio
      logo `transacoes.get(999999)` é None         -> linha 176
      logo o `id` vai para `ignoradas`              -> aplicadas = 0, ignoradas = [999999]

    A distinção com `invalidas` importa: aqui o problema é o `id`, não a
    referência de categoria, que é válida. Uma categoria que não existe dá
    `invalidas`, com a transacção a existir.
    """
    _transacao, cat, _sub = _semeia_categoria_subcategoria_transacao(session)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{"id": 999999, "categoria_id": cat.id}]
    })

    assert r.status_code == 200
    assert r.json() == {"aplicadas": 0, "ignoradas": [999999], "invalidas": []}


def test_categoria_inexistente_e_invalida(client, session):
    """Uma categoria que não existe deixa a transacção por tocar.

    Cálculo à mão:
      a transacção existe                        -> não vai para `ignoradas`
      `cats_ok` não traz o 999999                 -> a linha 180 é verdadeira
      logo o item entra em `invalidas`           -> aplicadas = 0, invalidas = [id]

    O `subcategoria_id` não vem no payload, e por isso a validação da linha 184
    nem chega a ser avaliada: com a categoria errada, o item já foi descartado
    uma linha acima.
    """
    transacao, _cat, _sub = _semeia_categoria_subcategoria_transacao(session)

    r = client.post("/api/regras/aplicar-em-massa", json={
        "itens": [{"id": transacao.id, "categoria_id": 999999}]
    })

    assert r.status_code == 200
    assert r.json() == {"aplicadas": 0, "ignoradas": [], "invalidas": [transacao.id]}


def test_lista_vazia_da_resultado_vazio(client):
    """Uma lista vazia devolve o resultado vazio, sem tocar em nada.

    Cálculo à mão: a linha 146 apanha a lista vazia antes de qualquer consulta e
    devolve logo os três cestos a zero e vazios. É um atalho deliberado, que
    evita o `in_([])` da linha 154.

    Não pede `session`: com a lista vazia nada é lido nem escrito na base de
    dados. O teste passa com a base de dados inteiramente vazia.
    """
    r = client.post("/api/regras/aplicar-em-massa", json={"itens": []})

    assert r.status_code == 200
    assert r.json() == {"aplicadas": 0, "ignoradas": [], "invalidas": []}

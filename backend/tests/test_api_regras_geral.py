"""Testes da API de regras (`/api/regras/`), excepto `aplicar-em-massa`.

Cobre o que faltava em `backend/routers/regras.py`:

* `POST /` — pré-checagem de duplicado (400) e o backfill, que usa o mesmo
  motor da importação (`casa_palavra` e as regras de exclusão);
* `DELETE /{regra_id}` (`:75-82`);
* `POST /pre-visualizar` (`:84-138`).

Ficam de fora, com ficheiro próprio: `aplicar-em-massa` (`:141-195`,
`test_api_regras_massa.py`) e a listagem `GET /` (`:18-31`, já exercitada por
`test_api_regras_criar.py`, que também cobre a validação da `palavra_chave`).

O motor de regras e o backfill divergiam: desde a correcção, o backfill compara como a
importação (`casa_palavra`) e respeita as regras de exclusão. Fica só a
diferença do pré-filtro com transacções órfãs (subcategoria sem categoria),
um estado que as chaves estrangeiras não impedem: a subcategoria existe, só não
pertence à categoria da transacção.
Nenhum valor esperado foi copiado de uma execução: são calculados à mão no
docstring de cada teste. As datas são fixas em 2025; nunca se usa a data de
hoje. Os testes não tocam na base de dados real (ver `conftest.py`).

A fixture `client` e a fixture `session` partilham a mesma sessão SQLAlchemy:
os pedidos e a verificação do estado da BD falam com a mesma sessão, pelo que a
leitura depois de um pedido começa sempre por `session.expire_all()`.
"""

from datetime import date

from database import Categoria, RegraCategorizacao, Subcategoria, TipoCategoria, Transacao

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _categorias(session):
    """Semeia Casa (despesa), Lazer (despesa) e Alimentação (de Casa).

    Devolve `(casa, lazer, sub_alim)` já com `id`. A subcategoria existe para
    o backfill lhe poder apontar (o router valida a sua existência).
    """
    casa = Categoria(nome="Casa", tipo=TipoCategoria.despesa)
    lazer = Categoria(nome="Lazer", tipo=TipoCategoria.despesa)
    session.add_all([casa, lazer])
    session.commit()
    session.refresh(casa)
    session.refresh(lazer)

    sub_alim = Subcategoria(nome="Alimentação", categoria_id=casa.id)
    session.add(sub_alim)
    session.commit()
    session.refresh(sub_alim)
    return casa, lazer, sub_alim


def _transacao(session, descricao, dia, categoria_id=None, subcategoria_id=None):
    """Cria e devolve uma transacção com `id`, na data fixa de 2025-01-`dia`."""
    t = Transacao(
        data=date(2025, 1, dia),
        descricao=descricao,
        valor=-10.0,
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


# ---------------------------------------------------------------------------
# POST / — nome duplicado (400) e backfill
# ---------------------------------------------------------------------------


def test_criar_regra_duplicada_da_400(client, session):
    """Uma palavra-chave que já existe é recusada com 400, antes de escrever.

    Cálculo à mão (`:35-37`): a regra "PINGO" já existe, logo `existente` não é
    None na linha 36, a linha 37 responde `400` e o `POST` termina sem criar
    nada. Esperado: 1 regra antes e depois.

    Estado final da BD: 1 regra (a semeada); nenhuma transacção.
    """
    session.add(RegraCategorizacao(palavra_chave="PINGO"))
    session.commit()

    r = client.post("/api/regras/", json={"palavra_chave": "PINGO"})

    assert r.status_code == 400
    assert r.json() == {"detail": "Já existe uma regra com esta palavra-chave"}
    assert session.query(RegraCategorizacao).count() == 1


def test_backfill_toca_por_categorizar_e_mesma_categoria_sem_subcategoria(client, session):
    """O backfill só escreve em dois casos; nas restantes, nada muda.

    Cálculo à mão (`:50-67`), com a regra "pingo" -> categoria Casa e
    subcategoria Alimentação:

      t1 (categoria None, subcategoria None)  -> 1.ª query  (`:52-55`)
      t2 (categoria Casa, subcategoria None)  -> 2.ª query  (`:61-65`)
      t3 (categoria Lazer)                    -> nenhuma query a apanha
      t4 (categoria Casa, subcategoria Alim.) -> idem (a 2.ª exige `sub is None`)

      `transacoes_atualizadas = len([t1]) + len([t2]) = 1 + 1 = 2` (`:72`)

    Estado final da BD: t1 -> (Casa, Alimentação), t2 -> subcategoria
    Alimentação, t3 -> (Lazer, None), t4 -> (Casa, Alimentação). As já
    categorizadas não são tocadas nem contadas.
    """
    casa, lazer, sub_alim = _categorias(session)
    t1 = _transacao(session, "PINGO DOCE", 1)
    t2 = _transacao(session, "PINGO DOCE", 2, categoria_id=casa.id)
    t3 = _transacao(session, "PINGO DOCE", 3, categoria_id=lazer.id)
    t4 = _transacao(session, "PINGO DOCE", 4, categoria_id=casa.id, subcategoria_id=sub_alim.id)

    r = client.post(
        "/api/regras/",
        json={
            "palavra_chave": "pingo",
            "categoria_id": casa.id,
            "subcategoria_id": sub_alim.id,
        },
    )

    assert r.status_code == 200
    assert r.json()["transacoes_atualizadas"] == 2

    session.expire_all()
    assert (
        session.get(Transacao, t1.id).categoria_id,
        session.get(Transacao, t1.id).subcategoria_id,
    ) == (casa.id, sub_alim.id)
    assert (
        session.get(Transacao, t2.id).categoria_id,
        session.get(Transacao, t2.id).subcategoria_id,
    ) == (casa.id, sub_alim.id)
    assert (
        session.get(Transacao, t3.id).categoria_id,
        session.get(Transacao, t3.id).subcategoria_id,
    ) == (lazer.id, None)
    assert (
        session.get(Transacao, t4.id).categoria_id,
        session.get(Transacao, t4.id).subcategoria_id,
    ) == (casa.id, sub_alim.id)


def test_backfill_sobre_transacao_orfa_sobrescreve_a_subcategoria(client, session):
    """O backfill não preserva a subcategoria de uma transacção órfã.

    Cálculo à mão (`:50-58`): a transacção tem `categoria_id is None` e
    `subcategoria_id` = Alimentação. A regra aponta para Casa **sem**
    subcategoria. A 1.ª query apanha-a e a linha 58 escreve
    `subcategoria_id = None`, pelo que a subcategoria que existia desaparece.
    Esperado: `(Casa, None)` e `transacoes_atualizadas = 1`.

    Possível defeito se acontecer: os dados válidos não deviam ter uma
    subcategoria sem categoria, por isso o cenário é construído à mão.
    """
    casa, _lazer, sub_alim = _categorias(session)
    orfa = _transacao(session, "PINGO DOCE", 1, subcategoria_id=sub_alim.id)

    r = client.post(
        "/api/regras/",
        json={
            "palavra_chave": "pingo",
            "categoria_id": casa.id,
        },
    )

    assert r.status_code == 200
    assert r.json()["transacoes_atualizadas"] == 1

    session.expire_all()
    orfa = session.get(Transacao, orfa.id)
    assert orfa.categoria_id == casa.id
    assert orfa.subcategoria_id is None


# ---------------------------------------------------------------------------
# POST / — acentos, "%" e "_"
# ---------------------------------------------------------------------------


def test_backfill_com_acento_casa_descricao_maiuscula(client, session):
    """A palavra "café" casa a descrição em minúsculas e em maiúsculas.

    Antes da correcção, o `ilike` do SQLite só ignora maiúsculas em letras ASCII, e
    "CAFÉ" não casava. Agora a comparação é `casa_palavra`, a da importação:
    "café".upper() = "CAFÉ" está em "CAFÉ PASTELARIA" e em
    "café pastelaria".upper(). Esperado: `transacoes_atualizadas = 2`, as duas
    categorizadas.
    """
    casa, _lazer, _sub = _categorias(session)
    t_min = _transacao(session, "café pastelaria", 1)
    t_mai = _transacao(session, "CAFÉ PASTELARIA", 2)

    r = client.post("/api/regras/", json={"palavra_chave": "café", "categoria_id": casa.id})

    assert r.status_code == 200
    assert r.json()["transacoes_atualizadas"] == 2

    session.expire_all()
    assert session.get(Transacao, t_min.id).categoria_id == casa.id
    assert session.get(Transacao, t_mai.id).categoria_id == casa.id


def test_backfill_casa_descricao_em_maiusculas(client, session):
    """Uma palavra-chave em minúsculas casa a descrição toda em maiúsculas.

    Cálculo à mão (`:52-55`): a regra é "pingo" e a transacção "PINGO DOCE";
    o padrão "%pingo%" casa a descrição. Esperado: `transacoes_atualizadas = 1`
    e a transacção com a categoria da regra.
    """
    casa, _lazer, _sub = _categorias(session)
    t = _transacao(session, "PINGO DOCE", 1)

    r = client.post("/api/regras/", json={"palavra_chave": "pingo", "categoria_id": casa.id})

    assert r.status_code == 200
    assert r.json()["transacoes_atualizadas"] == 1

    session.expire_all()
    assert session.get(Transacao, t.id).categoria_id == casa.id


def test_backfill_percent_e_texto_literal(client, session):
    """Um "%" na palavra-chave só casa o literal "%".

    Antes da correcção, com `ilike`, a regra "50%" virava o padrão "%50%%" e casava
    "PAGAMENTO 5000". Agora é texto: "50%" não está em "PAGAMENTO 5000" e está
    em "DESCONTO 50%". Esperado: `transacoes_atualizadas = 1`, só a do desconto.
    """
    casa, _lazer, _sub = _categorias(session)
    t_5000 = _transacao(session, "PAGAMENTO 5000", 1)
    t_desc = _transacao(session, "DESCONTO 50%", 2)

    r = client.post("/api/regras/", json={"palavra_chave": "50%", "categoria_id": casa.id})

    assert r.status_code == 200
    assert r.json()["transacoes_atualizadas"] == 1

    session.expire_all()
    assert session.get(Transacao, t_5000.id).categoria_id is None
    assert session.get(Transacao, t_desc.id).categoria_id == casa.id


def test_backfill_underscore_e_texto_literal(client, session):
    """Um "_" na palavra-chave só casa o literal "_".

    Antes da correcção, com `ilike`, "a_b" casava "PAGAMENTO AXB". Agora
    "A_B" não está em "PAGAMENTO AXB" e está em "REF A_B 12". Esperado:
    `transacoes_atualizadas = 1`, só a da referência.
    """
    casa, _lazer, _sub = _categorias(session)
    t_axb = _transacao(session, "PAGAMENTO AXB", 1)
    t_ref = _transacao(session, "REF A_B 12", 2)

    r = client.post("/api/regras/", json={"palavra_chave": "a_b", "categoria_id": casa.id})

    assert r.status_code == 200
    assert r.json()["transacoes_atualizadas"] == 1

    session.expire_all()
    assert session.get(Transacao, t_axb.id).categoria_id is None
    assert session.get(Transacao, t_ref.id).categoria_id == casa.id


def test_backfill_respeita_as_regras_de_exclusao(client, session):
    """O que uma regra de exclusão apanha fica por tocar, como na importação.

    Antes da correcção, o backfill ignorava as regras de exclusão.
    Cálculo à mão, com a exclusão "trf" já criada e a regra nova
    "pingo" -> (Casa, Alimentação):
      "PINGO DOCE" (sem categoria)       -> casa "pingo", não casa "trf" -> categoriza
      "TRF PINGO" (sem categoria)        -> casa "trf" -> fica (None, None)
      "TRF PINGO 2" (Casa, sem sub)      -> casa "trf" -> fica (Casa, None)
      `transacoes_atualizadas = 1`
    """
    casa, _lazer, sub_alim = _categorias(session)
    session.add(RegraCategorizacao(palavra_chave="trf", categoria_id=None))
    session.commit()
    t_ok = _transacao(session, "PINGO DOCE", 1)
    t_trf = _transacao(session, "TRF PINGO", 2)
    t_trf_casa = _transacao(session, "TRF PINGO 2", 3, categoria_id=casa.id)

    r = client.post(
        "/api/regras/",
        json={
            "palavra_chave": "pingo",
            "categoria_id": casa.id,
            "subcategoria_id": sub_alim.id,
        },
    )

    assert r.status_code == 200
    assert r.json()["transacoes_atualizadas"] == 1

    session.expire_all()

    def estado(t):
        return (
            session.get(Transacao, t.id).categoria_id,
            session.get(Transacao, t.id).subcategoria_id,
        )

    assert estado(t_ok) == (casa.id, sub_alim.id)
    assert estado(t_trf) == (None, None)
    assert estado(t_trf_casa) == (casa.id, None)


# ---------------------------------------------------------------------------
# POST /pre-visualizar vs backfill (com transacções órfãs)
# ---------------------------------------------------------------------------


def test_pre_visualizar_e_backfill_contam_o_mesmo_com_dados_validos(client, session):
    # A pré-visualização pré-filtra `subcategoria_id IS NULL` e o backfill
    # filtra por `categoria_id == None` (1.ª query) e
    # `categoria_id == nova.categoria_id and subcategoria_id == None` (2.ª).
    """Com dados válidos, as duas contagens coincidem (2 e 2).

    Lendo o código: a pré-visualização pré-filtra `subcategoria_id IS NULL`
    (`:87-89`) e, na fase 2 (`:107-136`), mantém as transacções cuja categoria
    é None ou é a da regra. O backfill soma a 1.ª query (categoria None) à 2.ª
    (mesma categoria e subcategoria None). Para dados válidos — em que uma
    subcategoria só existe com uma categoria — os dois conjuntos são iguais.
    Esperado: `len(sem_conflito) = 2`, `len(com_conflito) = 0` e
    `transacoes_atualizadas = 2`.

    A divergência do pré-filtro só apareceria com uma
    transacção órfã (categoria None e subcategoria definida), um estado
    inválido; essa semente está no teste
    `test_backfill_sobre_transacao_orfa_sobrescreve_a_subcategoria`.

    Estado final da BD: a regra é eliminada e recriada (é a única forma de
    correr o backfill), e as duas transacções ficam com a categoria da regra e
    subcategoria None.
    """
    casa, _lazer, _sub = _categorias(session)
    regra = RegraCategorizacao(palavra_chave="PINGO", categoria_id=casa.id)
    session.add(regra)
    session.commit()
    session.refresh(regra)

    t_a = _transacao(session, "PINGO DOCE", 1)
    t_b = _transacao(session, "PINGO DOCE", 2, categoria_id=casa.id)

    preview = client.post("/api/regras/pre-visualizar")
    assert preview.status_code == 200
    assert len(preview.json()["sem_conflito"]) == 2
    assert len(preview.json()["com_conflito"]) == 0
    assert {item["id"] for item in preview.json()["sem_conflito"]} == {t_a.id, t_b.id}

    apagar = client.delete(f"/api/regras/{regra.id}")
    assert apagar.status_code == 200
    assert apagar.json() == {"ok": True}

    criar = client.post(
        "/api/regras/",
        json={
            "palavra_chave": "PINGO",
            "categoria_id": casa.id,
        },
    )
    assert criar.status_code == 200
    assert criar.json()["transacoes_atualizadas"] == 2

    session.expire_all()
    assert session.get(Transacao, t_a.id).categoria_id == casa.id
    assert session.get(Transacao, t_b.id).categoria_id == casa.id


# ---------------------------------------------------------------------------
# DELETE /{regra_id}
# ---------------------------------------------------------------------------


def test_pre_visualizar_avalia_primeiro_a_palavra_chave_mais_longa(client, session):
    """A pré-visualização usa a mesma precedência que a importação.

    Cálculo à mão: "casa" -> Casa (criada primeiro) e "casa lazer" -> Lazer
    (criada depois); "CASA LAZER LDA" casa as duas e está por categorizar.
    A mais longa ("casa lazer", 10 caracteres) é avaliada primeiro -> a sugestão
    é Lazer, sem conflito.
    """
    casa, lazer, _ = _categorias(session)
    session.add(RegraCategorizacao(palavra_chave="casa", categoria_id=casa.id))
    session.commit()
    session.add(RegraCategorizacao(palavra_chave="casa lazer", categoria_id=lazer.id))
    session.commit()
    t = _transacao(session, "CASA LAZER LDA", 5)

    r = client.post("/api/regras/pre-visualizar")

    assert r.status_code == 200
    assert [(x["id"], x["categoria_id"]) for x in r.json()["sem_conflito"]] == [
        (t.id, lazer.id),
    ]
    assert r.json()["com_conflito"] == []


def test_apagar_regra_existente_e_inexistente(client, session):
    """Apagar uma regra existente dá 200; uma inexistente dá 404.

    Cálculo à mão (`:75-82`):
      DELETE /9999 -> a `first()` (`:77`) devolve None -> `404`
        {"detail": "Regra não encontrada"}
      DELETE /{id} -> encontra e apaga (`:80-81`) -> `200 {"ok": True}`

    Estado final da BD: a regra semeada desaparece; a tentativa de 404 não
    deixa nada.
    """
    regra = RegraCategorizacao(palavra_chave="PINGO")
    session.add(regra)
    session.commit()
    session.refresh(regra)

    r_404 = client.delete("/api/regras/9999")
    assert r_404.status_code == 404
    assert r_404.json() == {"detail": "Regra não encontrada"}
    assert session.query(RegraCategorizacao).count() == 1

    r = client.delete(f"/api/regras/{regra.id}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert session.query(RegraCategorizacao).count() == 0


# ---------------------------------------------------------------------------
# POST / com IDs inexistentes
# ---------------------------------------------------------------------------


def test_criar_regra_com_categoria_inexistente_da_400(client, session):
    """Uma categoria que não existe dá 400 e a regra não é gravada.

    Cálculo à mão: `db.get(Categoria, 999)` devolve None, logo `criar_regra`
    responde 400 com "Categoria não encontrada." antes do `db.add`. A
    transacção "PINGO DOCE", sem categoria, não é tocada pelo backfill.

    Estado final da BD: 0 regras; a transacção continua sem categoria.
    """
    t = _transacao(session, "PINGO DOCE", 1)

    r = client.post("/api/regras/", json={"palavra_chave": "PINGO", "categoria_id": 999})

    assert r.status_code == 400
    assert r.json() == {"detail": "Categoria não encontrada."}
    session.expire_all()
    assert session.query(RegraCategorizacao).count() == 0
    assert session.get(Transacao, t.id).categoria_id is None


def test_criar_regra_com_subcategoria_inexistente_da_400(client, session):
    """Uma subcategoria que não existe dá 400 e a regra não é gravada.

    Cálculo à mão: Casa existe, `db.get(Subcategoria, 999)` devolve None, logo
    `criar_regra` responde 400 com "Subcategoria não encontrada.".

    Estado final da BD: 0 regras; a transacção continua sem categoria.
    """
    casa, _lazer, _sub = _categorias(session)
    t = _transacao(session, "PINGO DOCE", 1)

    r = client.post(
        "/api/regras/",
        json={
            "palavra_chave": "PINGO",
            "categoria_id": casa.id,
            "subcategoria_id": 999,
        },
    )

    assert r.status_code == 400
    assert r.json() == {"detail": "Subcategoria não encontrada."}
    session.expire_all()
    assert session.query(RegraCategorizacao).count() == 0
    assert session.get(Transacao, t.id).categoria_id is None

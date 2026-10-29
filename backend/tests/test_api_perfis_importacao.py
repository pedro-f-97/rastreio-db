"""Testes de API do router `routers/perfis_importacao.py`.

O que fica fixado
-----------------
Todos os endpoints do router estavam por cobrir (o relatorio de cobertura dava
68 declaracoes, 47 em falta). Aqui entra-se sempre pelo endpoint real, sobre a
BD in-memory da fixture `session`, e confirma-se tambem o estado final na
sessao — nao basta olhar para a resposta.

Caminho canonico das rotas
--------------------------
As rotas sao declaradas sem barra final (`routers/perfis_importacao.py:46` e
`:63`): `PUT/DELETE /api/perfis-importacao/{id}`. O frontend chama-as **com**
barra final (`frontend/src/api/perfisImportacao.js:5-6`), e o Starlette
redirecciona com 307 para o caminho sem barra. Os testes usam o caminho
canonico, para nao dependerem do redireccionamento.

Nota sobre o `PUT` (A14)
------------------------
O frontend **nao tem interlocutor de `PUT`**: `atualizarPerfil` esta definido
em `frontend/src/api/perfisImportacao.js:5`, mas nenhuma pagina o importa nem
o chama; o formulario de perfis (`frontend/src/pages/Importacao.jsx:154`) so
invoca `criarPerfil` (POST). O `PUT` reescreve todos os campos com
`dados.model_dump()` (`routers/perfis_importacao.py:57-58`). A conta e
obrigatoria ao criar e ao editar: um corpo sem `conta_id` da 422.
Nao ha, hoje, caminho de UI que exercite o `PUT`.

Valores esperados
-----------------
Calculados a mao e escritos como constantes. Nada aqui usa a data de hoje nem
toca na base de dados real.
"""

import io
from datetime import date

from openpyxl import Workbook

from database import Conta, ModoValor, PerfilImportacao, TipoFicheiro

# Payload minimo para `PerfilImportacaoCreate` (schema, linhas 71-100), sem a
# conta: cada teste junta `conta_id` de uma conta semeada, porque e obrigatoria.
# Os restantes campos tem valores por omissao. `coluna_valor` e obrigatoria
# para `modo_valor="coluna_unica"`.
PERFIL_BASE = {
    "nome": "Demo",
    "tipo_ficheiro": "xlsx",
    "linha_inicio_dados": 1,
    "coluna_data": 0,
    "formato_data": "%d/%m/%Y",
    "coluna_descricao": 1,
    "modo_valor": "coluna_unica",
    "coluna_valor": 2,
}


def payload(**alteracoes):
    """Copia do payload base com as alteracoes pedidas."""
    dados = dict(PERFIL_BASE)
    dados.update(alteracoes)
    return dados


def semear_perfil(session, nome):
    """Grava um perfil completo, com enums reais, sem passar pela API."""
    perfil = PerfilImportacao(
        nome=nome,
        tipo_ficheiro=TipoFicheiro.xlsx,
        linha_inicio_dados=1,
        coluna_data=0,
        formato_data="%d/%m/%Y",
        coluna_descricao=1,
        modo_valor=ModoValor.coluna_unica,
        coluna_valor=2,
    )
    session.add(perfil)
    session.commit()
    return perfil


def semear_conta(session, nome):
    conta = Conta(
        nome=nome,
        saldo_referencia=0.0,
        data_referencia=date(2025, 1, 1),
        ativa=True,
    )
    session.add(conta)
    session.commit()
    return conta


# ---------------------------------------------------------------------------
# A1/A2 — GET /api/perfis-importacao/
# ---------------------------------------------------------------------------


def test_listar_perfis_ordena_por_nome(client, session):
    """A listagem vem ordenada por `nome`, nao pela ordem de insercao.

    Cálculo à mão: semeia-se "Zeta" (id 1) e "Alfa" (id 2). A query
    `order_by(PerfilImportacaoModel.nome)` (`routers/perfis_importacao.py:14`)
    devolve `["Alfa", "Zeta"]`; a ordem de insercao seria `["Zeta", "Alfa"]`.
    """
    semear_perfil(session, "Zeta")
    semear_perfil(session, "Alfa")

    r = client.get("/api/perfis-importacao/")

    assert r.status_code == 200
    assert [p["nome"] for p in r.json()] == ["Alfa", "Zeta"]
    assert session.query(PerfilImportacao).count() == 2


def test_listar_perfis_sem_perfis_devolve_lista_vazia(client, session):
    """Sem perfis, a resposta e `[]` (200), e a BD continua a zero linhas."""
    r = client.get("/api/perfis-importacao/")

    assert r.status_code == 200
    assert r.json() == []
    assert session.query(PerfilImportacao).count() == 0


# ---------------------------------------------------------------------------
# A3/A4/A5 — POST /api/perfis-importacao/
# ---------------------------------------------------------------------------


def test_criar_perfil_grava_e_devolve_201(client, session):
    """Um payload valido cria uma linha e responde 201 (nao 200).

    Cálculo à mão: um `POST`, uma linha. O `status_code=201` esta declarado na
    rota (`routers/perfis_importacao.py:16`).
    """
    conta = semear_conta(session, "Banco")
    r = client.post("/api/perfis-importacao/", json=payload(nome="Demo", conta_id=conta.id))

    assert r.status_code == 201
    corpo = r.json()
    assert corpo["id"] == 1
    assert corpo["nome"] == "Demo"
    assert corpo["coluna_valor"] == 2
    assert corpo["conta_id"] == conta.id

    assert session.query(PerfilImportacao).count() == 1
    perfil = session.query(PerfilImportacao).one()
    assert perfil.nome == "Demo"
    assert perfil.modo_valor == ModoValor.coluna_unica


def test_criar_perfil_com_nome_duplicado_da_409(client, session):
    """Nome ja existente: 409 e nenhuma linha nova.

    Cálculo à mão: um perfil semeado + um `POST` com o mesmo nome -> a BD fica
    com 1 linha.
    """
    semear_perfil(session, "Demo")
    conta = semear_conta(session, "Banco")

    r = client.post("/api/perfis-importacao/", json=payload(nome="Demo", conta_id=conta.id))

    assert r.status_code == 409
    assert r.json()["detail"] == "Já existe um perfil com esse nome."
    assert session.query(PerfilImportacao).count() == 1


def test_criar_perfil_sem_conta_da_422(client, session):
    """Sem `conta_id`, o perfil nao e criado.

    As transacções de um perfil sem conta contavam nas estatisticas mas nunca
    na liquidez. Cálculo à mão: um `POST` recusado -> 0 perfis na BD.
    """
    r = client.post("/api/perfis-importacao/", json=payload(nome="Demo"))

    assert r.status_code == 422
    assert session.query(PerfilImportacao).count() == 0


def test_criar_perfil_sem_coluna_valor_da_422(client, session):
    """`coluna_unica` sem `coluna_valor` e rejeitado pelo schema (422).

    O validador esta em `schemas.py:94-95`. Nada e gravado: a validacao do
    Pydantic corre antes da rota.
    """
    r = client.post(
        "/api/perfis-importacao/",
        json=payload(nome="Demo", coluna_valor=None),
    )

    assert r.status_code == 422
    assert session.query(PerfilImportacao).count() == 0


def test_criar_perfil_grava_a_coluna_de_imposto(client, session):
    """A coluna de imposto é gravada e devolvida, como a da comissão.

    Cálculo à mão: um `POST` com `coluna_fee` 11 e `coluna_imposto` 12, como no
    extracto da TR -> 201, e a linha gravada tem 12.
    """
    conta = semear_conta(session, "Banco")
    r = client.post(
        "/api/perfis-importacao/",
        json=payload(nome="TR", conta_id=conta.id, coluna_fee=11, coluna_imposto=12),
    )

    assert r.status_code == 201
    assert r.json()["coluna_imposto"] == 12
    assert session.query(PerfilImportacao).one().coluna_imposto == 12


def test_criar_perfil_com_coluna_de_imposto_negativa_da_422(client, session):
    """Uma coluna de imposto negativa é recusada pelo schema, como as outras.

    Cálculo à mão: `coluna_imposto` -1 -> 422, 0 perfis na BD.
    """
    conta = semear_conta(session, "Banco")
    r = client.post(
        "/api/perfis-importacao/",
        json=payload(nome="TR", conta_id=conta.id, coluna_imposto=-1),
    )

    assert r.status_code == 422
    assert session.query(PerfilImportacao).count() == 0


# ---------------------------------------------------------------------------
# A6..A9 — POST /api/perfis-importacao/analisar-ficheiro
# ---------------------------------------------------------------------------


def test_analisar_ficheiro_csv_devolve_as_linhas_como_texto(client):
    """CSV com BOM: o `utf-8-sig` retira-o e cada celula vem como string.

    Cálculo à mão: tres linhas, tres colunas; o `csv.reader` usa a virgula por
    omissao. O valor numerico `-10` vem como a string `"-10"`.
    """
    conteudo = ("\ufeffdata,descricao,valor\n2025-01-01,Compra,-10\n2025-01-02,Venda,20\n").encode(
        "utf-8"
    )

    r = client.post(
        "/api/perfis-importacao/analisar-ficheiro",
        files={"file": ("extracto.csv", conteudo, "text/csv")},
    )

    assert r.status_code == 200
    assert r.json()["linhas"] == [
        ["data", "descricao", "valor"],
        ["2025-01-01", "Compra", "-10"],
        ["2025-01-02", "Venda", "20"],
    ]


def test_analisar_ficheiro_csv_delimitado_por_ponto_e_virgula_le_as_colunas(client):
    """Um CSV com `;` mostra as colunas certas na criação de um perfil.

    Antes da correcção, o `csv.reader` usava a vírgula e cada linha vinha num só campo
    (`"a;b"`, `"1;2"`). Agora usa `_detectar_delimitador` sobre as primeiras
    linhas: `;` dá 2 colunas em cada linha, `,` dá 1 -> `;`.
    """
    conteudo = "a;b\n1;2\n".encode("utf-8")

    r = client.post(
        "/api/perfis-importacao/analisar-ficheiro",
        files={"file": ("extracto.csv", conteudo, "text/csv")},
    )

    assert r.status_code == 200
    assert r.json()["linhas"] == [["a", "b"], ["1", "2"]]


def test_analisar_ficheiro_csv_em_windows_1252_le_os_acentos(client):
    """Um CSV em Windows-1252 mostra os acentos certos, em vez de dar 500.

    Cálculo à mão: «Descrição» e «Água» têm bytes (0xe7, 0xe3, 0xc1) que não
    são UTF-8 válido nesta sequência; a leitura em Windows-1252 devolve o texto
    original. `,` dá 2 colunas em cada linha -> `[["Descrição", "Valor"],
    ["Água", "-10"]]`.
    """
    conteudo = "Descrição,Valor\nÁgua,-10\n".encode("cp1252")

    r = client.post(
        "/api/perfis-importacao/analisar-ficheiro",
        files={"file": ("extracto.csv", conteudo, "text/csv")},
    )

    assert r.status_code == 200
    assert r.json()["linhas"] == [["Descrição", "Valor"], ["Água", "-10"]]


def test_analisar_ficheiro_csv_que_nao_e_utf8_nem_windows_1252_da_400(client):
    """Bytes que nenhuma das duas codificações lê dão 400 em PT-PT, não 500.

    0xc1 não pode começar um carácter em UTF-8; 0x81 não tem carácter em
    Windows-1252.
    """
    r = client.post(
        "/api/perfis-importacao/analisar-ficheiro",
        files={"file": ("extracto.csv", b"\xc1\x81,a\n", "text/csv")},
    )

    assert r.status_code == 400
    assert r.json() == {
        "detail": "Não foi possível ler o ficheiro: a codificação não é UTF-8 nem Windows-1252."
    }


def test_analisar_ficheiro_csv_com_extensao_em_maiusculas(client):
    """Um `EXTRACTO.CSV` é lido como CSV, e não aberto como Excel.

    Antes da correcção, a extensão era comparada com `.csv` em minúsculas, e um nome em
    maiúsculas ia parar ao `openpyxl`, que falhava a abrir o ficheiro. Cálculo
    à mão: `a,b / 1,2` -> 2 colunas por linha -> `[["a", "b"], ["1", "2"]]`.
    """
    r = client.post(
        "/api/perfis-importacao/analisar-ficheiro",
        files={"file": ("EXTRACTO.CSV", "a,b\n1,2\n".encode("utf-8"), "text/csv")},
    )

    assert r.status_code == 200
    assert r.json()["linhas"] == [["a", "b"], ["1", "2"]]


def test_analisar_ficheiro_xlsx_converte_none_em_string_vazia(client):
    """Um XLSX e lido com `openpyxl` e as celulas vazias viram `""`.

    Cálculo à mão: a folha tem tres linhas; a terceira comeca com uma celula
    vazia (`None`), que `routers/perfis_importacao.py:43` converte em `""`. Os
    numeros sao convertidos com `str`: `-10` -> `"-10"` e `20` -> `"20"`.
    """
    wb = Workbook()
    ws = wb.active
    ws.append(["data", "descricao", "valor"])
    ws.append(["2025-01-01", "Compra", -10])
    ws.append([None, "Venda", 20])
    buffer = io.BytesIO()
    wb.save(buffer)

    r = client.post(
        "/api/perfis-importacao/analisar-ficheiro",
        files={
            "file": (
                "extracto.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert r.status_code == 200
    assert r.json()["linhas"] == [
        ["data", "descricao", "valor"],
        ["2025-01-01", "Compra", "-10"],
        ["", "Venda", "20"],
    ]


def test_analisar_ficheiro_csv_limita_a_12_linhas(client):
    """Mais de 12 linhas: so as primeiras 12 regressam.

    Cálculo à mão: 14 linhas `linha0`..`linha13`; `zip(range(12), reader)`
    (`routers/perfis_importacao.py:35`) corta nas 12 primeiras, terminando em
    `linha11`.
    """
    conteudo = "".join(f"linha{i}\n" for i in range(14)).encode("utf-8")

    r = client.post(
        "/api/perfis-importacao/analisar-ficheiro",
        files={"file": ("extracto.csv", conteudo, "text/csv")},
    )

    assert r.status_code == 200
    linhas = r.json()["linhas"]
    assert len(linhas) == 12
    assert linhas[0] == ["linha0"]
    assert linhas[-1] == ["linha11"]


# ---------------------------------------------------------------------------
# A10..A14 — PUT /api/perfis-importacao/{id}
# ---------------------------------------------------------------------------


def test_atualizar_perfil_grava_os_campos(client, session):
    """Editar um perfil actualiza os campos enviados.

    Cálculo à mão: semeia-se `coluna_valor=2` e envia-se `coluna_valor=5`; a
    resposta e a BD passam a 5.
    """
    perfil = semear_perfil(session, "Demo")
    conta = semear_conta(session, "Banco")

    r = client.put(
        f"/api/perfis-importacao/{perfil.id}",
        json=payload(nome="Demo2", coluna_valor=5, conta_id=conta.id),
    )

    assert r.status_code == 200
    assert r.json()["nome"] == "Demo2"
    assert r.json()["coluna_valor"] == 5

    session.refresh(perfil)
    assert perfil.nome == "Demo2"
    assert perfil.coluna_valor == 5


def test_atualizar_perfil_com_o_proprio_nome_nao_da_conflito(client, session):
    """Guardar sem mudar o nome nao e conflito com ele mesmo.

    A condicao `PerfilImportacaoModel.id != perfil_id`
    (`routers/perfis_importacao.py:53`) exclui o proprio registo. Sem ela, o
    `POST` devolveria 409.
    """
    perfil = semear_perfil(session, "Demo")
    conta = semear_conta(session, "Banco")

    r = client.put(
        f"/api/perfis-importacao/{perfil.id}",
        json=payload(nome="Demo", conta_id=conta.id),
    )

    assert r.status_code == 200
    assert r.json()["nome"] == "Demo"


def test_atualizar_perfil_com_nome_de_outro_da_409(client, session):
    """Renomear para o nome de outro perfil e conflito (409).

    Cálculo à mão: dois perfis "Alfa" e "Beta"; renomear "Alfa" para "Beta"
    falha, e a BD fica inalterada.
    """
    alfa = semear_perfil(session, "Alfa")
    semear_perfil(session, "Beta")
    conta = semear_conta(session, "Banco")

    r = client.put(
        f"/api/perfis-importacao/{alfa.id}",
        json=payload(nome="Beta", conta_id=conta.id),
    )

    assert r.status_code == 409
    assert r.json()["detail"] == "Já existe um perfil com esse nome."
    session.refresh(alfa)
    assert alfa.nome == "Alfa"


def test_atualizar_perfil_inexistente_da_404(client, session):
    """Um id que nao existe responde 404 e nao grava nada."""
    # O corpo tem de ser valido para chegar a rota; o perfil e procurado antes
    # da conta, por isso a conta 1 inexistente nao chega a ser vista
    r = client.put("/api/perfis-importacao/999", json=payload(conta_id=1))

    assert r.status_code == 404
    assert r.json()["detail"] == "Perfil não encontrado."
    assert session.query(PerfilImportacao).count() == 0


def test_atualizar_perfil_sem_conta_da_422_e_mantem_a_conta(client, session):
    """O `PUT` sem `conta_id` e recusado (422) e o perfil fica com a conta.

    Antes da correcção, o `PUT` reescrevia todos os campos e um corpo sem
    `conta_id` repunha-o a `None`, sem erro. A conta passou a ser obrigatoria
    em `PerfilImportacaoCreate`.
    """
    conta = semear_conta(session, "Banco")
    perfil = semear_perfil(session, "Demo")
    perfil.conta_id = conta.id
    session.commit()

    r = client.put(
        f"/api/perfis-importacao/{perfil.id}",
        json=payload(nome="Demo"),
    )

    assert r.status_code == 422
    session.refresh(perfil)
    assert perfil.conta_id == conta.id


# ---------------------------------------------------------------------------
# A15/A16 — DELETE /api/perfis-importacao/{id}
# ---------------------------------------------------------------------------


def test_eliminar_perfil_apaga_a_linha(client, session):
    """Apagar responde 204 sem corpo e remove a linha.

    Cálculo à mão: um perfil semeado -> depois do `DELETE`, 0 linhas.
    """
    perfil = semear_perfil(session, "Demo")

    r = client.delete(f"/api/perfis-importacao/{perfil.id}")

    assert r.status_code == 204
    assert r.content == b""
    assert session.query(PerfilImportacao).count() == 0


def test_eliminar_perfil_inexistente_da_404(client, session):
    """Apagar um id que nao existe responde 404."""
    r = client.delete("/api/perfis-importacao/999")

    assert r.status_code == 404
    assert r.json()["detail"] == "Perfil não encontrado."


# ---------------------------------------------------------------------------
# A17..A20 — PATCH /api/perfis-importacao/{id}/conta
# ---------------------------------------------------------------------------


def test_associar_conta_grava_o_conta_id(client, session):
    """Associar uma conta devolve `ok` e grava o `conta_id`.

    Cálculo à mão: perfil com `conta_id=None` + `PATCH {"conta_id": <id>}` ->
    resposta `{"ok": true, "conta_id": <id>}` e BD com `conta_id` igual.
    """
    conta = semear_conta(session, "Banco")
    perfil = semear_perfil(session, "Demo")

    r = client.patch(
        f"/api/perfis-importacao/{perfil.id}/conta",
        json={"conta_id": conta.id},
    )

    assert r.status_code == 200
    assert r.json() == {"ok": True, "conta_id": conta.id}
    session.refresh(perfil)
    assert perfil.conta_id == conta.id


def test_associar_conta_nula_da_422_e_mantem_a_conta(client, session):
    """`conta_id: null` e recusado (422): um perfil nao pode ficar sem conta.

    Antes da correcção, `PATCH {"conta_id": null}` desassociava a conta.
    """
    conta = semear_conta(session, "Banco")
    perfil = semear_perfil(session, "Demo")
    perfil.conta_id = conta.id
    session.commit()

    r = client.patch(
        f"/api/perfis-importacao/{perfil.id}/conta",
        json={"conta_id": None},
    )

    assert r.status_code == 422
    session.refresh(perfil)
    assert perfil.conta_id == conta.id


def test_associar_conta_perfil_inexistente_da_404(client, session):
    """Associar num perfil que nao existe responde 404."""
    r = client.patch(
        "/api/perfis-importacao/999/conta",
        json={"conta_id": 1},
    )

    assert r.status_code == 404
    assert r.json()["detail"] == "Perfil não encontrado."


def test_associar_conta_inexistente_da_400_e_nao_grava(client, session):
    """Um `conta_id` que nao existe da 400 e nao e gravado.

    Era gravado tal e qual (200 com `conta_id=999`), porque o SQLite nao
    aplicava as chaves estrangeiras e o handler nao validava a conta.

    Cálculo à mão: `PATCH {"conta_id": 999}` num perfil sem conta ->
    `db.get(Conta, 999)` devolve None -> 400 "Conta não encontrada.".

    Estado final da BD: o perfil continua sem conta.
    """
    perfil = semear_perfil(session, "Demo")

    r = client.patch(
        f"/api/perfis-importacao/{perfil.id}/conta",
        json={"conta_id": 999},
    )

    assert r.status_code == 400
    assert r.json() == {"detail": "Conta não encontrada."}
    session.expire_all()
    assert session.get(PerfilImportacao, perfil.id).conta_id is None


def test_criar_perfil_com_conta_inexistente_da_400_e_nao_grava(client, session):
    """`POST` com `conta_id` que nao existe: 400 e nenhum perfil.

    Cálculo à mão: nome livre, `db.get(Conta, 999)` devolve None -> 400
    "Conta não encontrada." antes do `db.add`. Estado final: 0 perfis.
    """
    r = client.post("/api/perfis-importacao/", json=payload(conta_id=999))

    assert r.status_code == 400
    assert r.json() == {"detail": "Conta não encontrada."}
    session.expire_all()
    assert session.query(PerfilImportacao).count() == 0


def test_atualizar_perfil_com_conta_inexistente_da_400_e_nao_grava(client, session):
    """`PUT` com `conta_id` que nao existe: 400 e o perfil fica como estava.

    Cálculo à mão: o perfil "Demo" existe, o corpo muda o nome para "Outro" e
    a conta para 999; `db.get(Conta, 999)` devolve None -> 400 "Conta não
    encontrada." antes do `setattr`. Estado final: nome "Demo", sem conta.
    """
    perfil = semear_perfil(session, "Demo")

    r = client.put(
        f"/api/perfis-importacao/{perfil.id}",
        json=payload(nome="Outro", conta_id=999),
    )

    assert r.status_code == 400
    assert r.json() == {"detail": "Conta não encontrada."}
    session.expire_all()
    guardado = session.get(PerfilImportacao, perfil.id)
    assert (guardado.nome, guardado.conta_id) == ("Demo", None)

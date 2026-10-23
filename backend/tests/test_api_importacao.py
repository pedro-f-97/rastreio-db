"""Testes de API de `POST /api/importacao/preview` e `POST /api/importacao/importar`.

Cobrem os dois endpoints do router de importação (`backend/routers/importacao.py`)
e, com eles, o motor `importar_transacoes` (`backend/importador_transacoes.py`),
que só é chamado por aqui. O parser já está caracterizado em
`test_parser_importacao.py`; aqui testa-se a ligação.

Rotas reais
-----------
`/api/importacao/preview` (`importacao.py:15`) e `/api/importacao/importar`
(`importacao.py:35`). O `perfil_id` é um parâmetro de consulta (`?perfil_id=`);
o ficheiro vai em `multipart/form-data`, campo `file`.

O que os endpoints fazem, lido por ordem
----------------------------------------
* `_obter_perfil` (`importacao.py:9-13`) corre **antes** de ler o ficheiro. Se o
  id não existir, responde 404 `"Perfil não encontrado."`.
* `preview_extrato` (`:15-33`) analisa o ficheiro; qualquer excepção vira 400 com
  `detail=str(e)`; devolve `transacoes[:10]` com a `data` convertida a `str`,
  mais `total_linhas` e `erros`. **Não escreve nada na base de dados.**
* `importar_extrato` (`:35-45`) analisa o ficheiro; 400 se
  `not transacoes and erros`; senão chama
  `importar_transacoes(transacoes, db, conta_id=perfil.conta_id)`.

Regra de deduplicação, lida do código (`importador_transacoes.py:31-48`)
-----------------------------------------------------------------------
1. A chave é o 4-uplo `(data, descricao, valor, saldo)`, com comparação
   **exacta**: `descricao` tal como o parser a produziu, `valor`/`saldo` sem
   arredondar, e `saldo` distingue `None` de `0.0`. Excepção: num perfil
   **sem saldo** (`tem_saldo` falso), a chave é só `(data, descricao, valor)`,
   porque o saldo da BD é o que se escreveu à mão numa conta cujo extracto não
   o traz.
2. A comparação é feita **só contra transacções da mesma conta**
   (`filter(Transacao.conta_id == conta_id)`). Com `conta_id=None` o SQLAlchemy
   traduz `== None` para `IS NULL`, pelo que só compara com transacções de
   `conta_id` NULL.
3. `existentes` conta quantas vezes cada chave já está na conta, e cada cópia
   absorve **uma** linha igual do ficheiro. Com 1 na BD e 2 no ficheiro, entra
   1 (antes entrava 0). Linhas repetidas **dentro do mesmo
   ficheiro**, sem cópias na BD, entram todas.

Convenções fixadas (comportamento actual, não corrigido)
--------------------------------------------------------
* Um erro por linha **não** faz o endpoint falhar: o parser acumula-o em `erros`
  e o preview devolve 200 com a lista. Só uma excepção do parser (ficheiro
  ilegível, p.ex.) é que vira 400.
* Ficheiro sem transacções e sem erros (só cabeçalho/linhas vazias) →
  `importar_transacoes([])` → 200 `{"inseridas": 0, "duplicadas": 0}`. É
  defensável: nada para importar não é um erro.
* Linhas repetidas no mesmo ficheiro entram todas (`inseridas` iguais). É
  defensável: duas transacções iguais no mesmo dia podem ser reais (dois cafés,
  por exemplo), e a deduplicação é só contra o que já existe na conta.

Nada aqui é corrigido.

Valores esperados
-----------------
Calculados à mão e escritos como constantes, com o cálculo no comentário de cada
teste. As datas são fixas em 2026: nenhum teste assenta na data de hoje. O perfil
e a conta são criados com as classes e enums reais (`PerfilImportacao`,
`Conta`, `TipoFicheiro`, `ModoValor`) e os ids são os que a base de dados nova
atribui, nunca números fixos.
"""

from datetime import date, datetime

import pytest

from database import (
    Ativo,
    Categoria,
    Conta,
    Importacao,
    ModoValor,
    MovimentoAtivo,
    PerfilImportacao,
    PrecoAtivo,
    RegraCategorizacao,
    Subcategoria,
    TipoAtivo,
    TipoCategoria,
    TipoContabilizacao,
    TipoFicheiro,
    TipoMovimento,
    Transacao,
)

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def _criar_conta(session, nome="Conta X"):
    """Cria uma conta com data de referência fixa e devolve-a com `id`."""
    conta = Conta(
        nome=nome,
        saldo_referencia=0.0,
        data_referencia=date(2026, 1, 1),
        ativa=True,
    )
    session.add(conta)
    session.commit()
    session.refresh(conta)
    return conta


def _criar_perfil(session, **campos):
    """Cria um perfil de importação CSV por omissão.

    Os valores por omissão são o cenário mais comum: CSV com vírgula decimal,
    uma coluna de valor e uma data por linha, dados a começar na linha 2. Os
    campos passados em `campos` sobrepõem-se. Devolve o perfil com `id`.
    """
    perfil = PerfilImportacao(
        nome="Perfil de teste",
        tipo_ficheiro=TipoFicheiro.csv,
        linha_inicio_dados=2,
        coluna_data=0,
        formato_data="%d/%m/%Y",
        coluna_descricao=1,
        modo_valor=ModoValor.coluna_unica,
        coluna_valor=2,
        separador_decimal=",",
        tem_saldo=False,
        conta_id=None,
    )
    for campo, valor in campos.items():
        setattr(perfil, campo, valor)
    session.add(perfil)
    session.commit()
    session.refresh(perfil)
    return perfil


def escrever_csv(caminho, linhas, codificacao="utf-8-sig"):
    """Escreve um CSV verdadeiro no disco e devolve o caminho.

    Copiado de `tests/test_parser_importacao.py` (por ser curto): a chave está
    em `utf-8-sig`, que é como o Excel exporta em português, com a marca de ordem
    de bytes no princípio do ficheiro.
    """
    caminho.write_text("".join(linha + "\n" for linha in linhas), encoding=codificacao)
    return caminho


# Extrato CSV limpo, duas linhas válidas, para os cenários de importação.
CSV_DUAS_LINHAS = (
    "Data,Descrição,Valor",
    '31/01/2026,Supermercado,"-45,60"',
    '02/02/2026,Salário,"1500,00"',
)

# As duas transacções que `CSV_DUAS_LINHAS` produz, calculadas à mão:
#   linha 2: "-45,60" -> -45.60 ; linha 3: "1500,00" -> 1500.00 ; saldo ausente
#   (tem_saldo=False) -> None.
TRANSACOES_DUAS_LINHAS = [
    {"data": date(2026, 1, 31), "descricao": "Supermercado", "valor": -45.6, "saldo": None},
    {"data": date(2026, 2, 2), "descricao": "Salário", "valor": 1500.0, "saldo": None},
]


def _pedido_preview(client, perfil_id, conteudo, nome="extrato.csv"):
    return client.post(
        f"/api/importacao/preview?perfil_id={perfil_id}",
        files={"file": (nome, conteudo, "text/csv")},
    )


def _pedido_importar(client, perfil_id, conteudo, nome="extrato.csv"):
    return client.post(
        f"/api/importacao/importar?perfil_id={perfil_id}",
        files={"file": (nome, conteudo, "text/csv")},
    )


# ---------------------------------------------------------------------------
# /preview
# ---------------------------------------------------------------------------


def test_preview_devolve_as_primeiras_linhas_sem_tocar_na_bd(client, session, tmp_path):
    """Duas linhas válidas: 200 com as duas, e a base de dados fica vazia.

    Cálculo à mão: `str(date(2026, 1, 31))` = "2026-01-31" e
    `str(date(2026, 2, 2))` = "2026-02-02"; os valores saem tal como o parser os
    lê (`TRANSACOES_DUAS_LINHAS`). `total_linhas` = 2 transacções + 0 erros.
    """
    perfil = _criar_perfil(session)
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_DUAS_LINHAS)

    r = _pedido_preview(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {
        "linhas_preview": [
            {"data": "2026-01-31", "descricao": "Supermercado", "valor": -45.6, "saldo": None},
            {"data": "2026-02-02", "descricao": "Salário", "valor": 1500.0, "saldo": None},
        ],
        "total_linhas": 2,
        "erros": [],
    }
    # O preview é só-leitura: nenhuma transacção foi criada.
    assert session.query(Transacao).count() == 0


def test_preview_limita_a_dez_linhas(client, session, tmp_path):
    """Com 11 linhas, o preview mostra as 10 primeiras e conta as 11.

    Gera-se com um ciclo: para `n` em 1..11, a linha é `{n:02d}/01/2026`,
    descrição "Linha {n}" e valor `"-{n},00"` (logo -n,00). A décima linha do
    preview é a n=10; a n=11 não aparece. `total_linhas` = 11.
    """
    perfil = _criar_perfil(session)
    linhas = ["Data,Descrição,Valor"]
    for n in range(1, 12):
        linhas.append(f'{n:02d}/01/2026,Linha {n},"-{n},00"')
    caminho = escrever_csv(tmp_path / "onze.csv", linhas)

    r = _pedido_preview(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    corpo = r.json()
    preview = corpo["linhas_preview"]
    assert len(preview) == 10
    assert preview[0] == {
        "data": "2026-01-01",
        "descricao": "Linha 1",
        "valor": -1.0,
        "saldo": None,
    }
    assert preview[9] == {
        "data": "2026-01-10",
        "descricao": "Linha 10",
        "valor": -10.0,
        "saldo": None,
    }
    assert corpo["total_linhas"] == 11
    assert corpo["erros"] == []


def test_preview_reporta_linha_invalida_como_erro_sem_400(client, session, tmp_path):
    """Uma data inválida não faz 400: entra na lista de erros e o resto passa.

    Cálculo à mão: a linha 3 é 31 de fevereiro, que o `strptime` recusa; o parser
    acumula `{"linha": 3, "erro": ...}` e continua. Sobra 1 transacção, logo
    `total_linhas` = 1 + 1 = 2 e o preview tem 1 linha.
    """
    perfil = _criar_perfil(session)
    caminho = escrever_csv(
        tmp_path / "com_erro.csv",
        (
            "Data,Descrição,Valor",
            '31/01/2026,Supermercado,"-45,60"',
            '31/02/2026,Café,"-3,20"',
        ),
    )

    r = _pedido_preview(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {
        "linhas_preview": [
            {"data": "2026-01-31", "descricao": "Supermercado", "valor": -45.6, "saldo": None},
        ],
        "total_linhas": 2,
        "erros": [
            {"linha": 3, "erro": "data inválida: '31/02/2026' (formato esperado: %d/%m/%Y)"},
        ],
    }
    assert session.query(Transacao).count() == 0


def test_preview_com_perfil_inexistente_da_404(client):
    """Um `perfil_id` que não existe dá 404, antes de o ficheiro ser lido.

    `_obter_perfil` corre na linha 17, antes do `file.read()` da linha 18, por
    isso o conteúdo enviado é irrelevante e pode ir vazio. Não pede `session`:
    nada é lido da base de dados para além da procura do perfil.
    """
    r = _pedido_preview(client, 999999, b"")

    assert r.status_code == 404
    assert r.json() == {"detail": "Perfil não encontrado."}


def test_preview_com_ficheiro_indescodificavel_da_400(client, session):
    """Bytes que não são UTF-8 nem Windows-1252 dão 400 com uma mensagem em PT-PT.

    O perfil é CSV, logo `_ler_linhas_csv` chama `_decodificar_csv`. `0xc1`
    não pode começar um carácter em UTF-8, e `0x81` é um dos cinco bytes sem
    carácter em Windows-1252, por isso as duas leituras falham e sai
    `ErroParsing`. O `except Exception` do router apanha-o e responde 400 com
    `detail=str(e)`.

    Nota de comportamento: este `except Exception` transforma **qualquer** erro
    de programação em 400, o que esconde bugs servidor. Não é corrigido aqui.
    """
    perfil = _criar_perfil(session)
    conteudo_invalido = b'\xc1\x8131/01/2026,Supermercado,"-45,60"'

    r = _pedido_preview(client, perfil.id, conteudo_invalido)

    assert r.status_code == 400
    assert r.json() == {
        "detail": "Não foi possível ler o ficheiro: a codificação não é UTF-8 nem Windows-1252."
    }


# ---------------------------------------------------------------------------
# /importar — inserção e deduplicação
# ---------------------------------------------------------------------------


def test_importar_insere_e_devolve_contagens(client, session, tmp_path):
    """Duas linhas novas: 200 com `{"inseridas": 2, "duplicadas": 0}`.

    Estado final, lido pela sessão: 2 transacções na conta do perfil, sem
    categoria nem subcategoria (não há regras semeadas) e `saldo` None.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_DUAS_LINHAS)

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 2, "duplicadas": 0}

    guardadas = session.query(Transacao).order_by(Transacao.data).all()
    assert [
        (
            t.data,
            t.descricao,
            t.valor,
            t.saldo,
            t.conta_id,
            t.categoria_id,
            t.subcategoria_id,
        )
        for t in guardadas
    ] == [
        (date(2026, 1, 31), "Supermercado", -45.6, None, conta.id, None, None),
        (date(2026, 2, 2), "Salário", 1500.0, None, conta.id, None, None),
    ]


def test_importar_duas_vezes_deduplica(client, session, tmp_path):
    """Importar o mesmo ficheiro outra vez não cria nada: as duas são duplicadas.

    Cálculo à mão: na 2.ª chamada `existentes` já contém
    `(2026-01-31, "Supermercado", -45.6, None)` e
    `(2026-02-02, "Salário", 1500.0, None)`, que são exactamente as duas chaves
    do ficheiro. Logo `inseridas` = 0 e `duplicadas` = 2; a base de dados fica
    com as 2 linhas da primeira importação.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_DUAS_LINHAS)
    conteudo = caminho.read_bytes()

    _pedido_importar(client, perfil.id, conteudo)
    r = _pedido_importar(client, perfil.id, conteudo)

    assert r.status_code == 200
    assert r.json() == {"inseridas": 0, "duplicadas": 2}
    assert session.query(Transacao).count() == 2


def test_dedup_usa_os_quatro_campos(client, session, tmp_path):
    """A chave é `(data, descricao, valor, saldo)`: mudar um campo escapa à dedup.

    Semeia-se `(2026-02-02, "Salário", 1500.0, None)`. O ficheiro traz essa linha
    igual (duplicada) e uma outra, nova:
      Supermercado  -> chave nova                    -> inserida
      Salário       -> chave igual à semeada         -> duplicada
    Resultado: `{"inseridas": 1, "duplicadas": 1}`; a base de dados fica com as
    2 linhas (a semeada + a nova).
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    session.add(
        Transacao(
            data=date(2026, 2, 2),
            descricao="Salário",
            valor=1500.0,
            saldo=None,
            conta_id=conta.id,
        )
    )
    session.commit()
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_DUAS_LINHAS)

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 1, "duplicadas": 1}
    assert session.query(Transacao).count() == 2


def test_dedup_com_saldo_distinto_nao_e_duplicado(client, session, tmp_path):
    """Com `tem_saldo`, um saldo diferente faz a linha deixar de ser duplicada.

    Semeia-se `(2026-01-31, "Supermercado", -45.6, saldo=100.0)`. A linha
    importada é igual em data, descrição e valor, mas com saldo `200,00` ->
    200.0. As chaves diferem no quarto campo:
      semeada   (2026-01-31, "Supermercado", -45.6, 100.0)
      importada (2026-01-31, "Supermercado", -45.6, 200.0)
    -> não é duplicada: `{"inseridas": 1, "duplicadas": 0}`. É este o caso que a
    mutação de tirar o `saldo` da chave tem de apanhar.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(
        session,
        conta_id=conta.id,
        tem_saldo=True,
        coluna_saldo=3,
    )
    session.add(
        Transacao(
            data=date(2026, 1, 31),
            descricao="Supermercado",
            valor=-45.6,
            saldo=100.0,
            conta_id=conta.id,
        )
    )
    session.commit()
    caminho = escrever_csv(
        tmp_path / "com_saldo.csv",
        (
            "Data,Descrição,Valor,Saldo",
            '31/01/2026,Supermercado,"-45,60","200,00"',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 1, "duplicadas": 0}
    assert session.query(Transacao).count() == 2


def test_dedup_com_saldo_zero_contra_none_nao_e_duplicado(client, session, tmp_path):
    """A chave distingue `saldo=0.0` de `saldo=None`.

    Semeia-se `(2026-01-31, "Supermercado", -45.6, saldo=None)`. A linha
    importada tem saldo `0,00` -> 0.0. Em Python `0.0 != None` e o SQLAlchemy
    compara-os como valores distintos, logo as chaves diferem:
      semeada   (2026-01-31, "Supermercado", -45.6, None)
      importada (2026-01-31, "Supermercado", -45.6, 0.0)
    -> não é duplicada: `{"inseridas": 1, "duplicadas": 0}`.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(
        session,
        conta_id=conta.id,
        tem_saldo=True,
        coluna_saldo=3,
    )
    session.add(
        Transacao(
            data=date(2026, 1, 31),
            descricao="Supermercado",
            valor=-45.6,
            saldo=None,
            conta_id=conta.id,
        )
    )
    session.commit()
    caminho = escrever_csv(
        tmp_path / "saldo_zero.csv",
        (
            "Data,Descrição,Valor,Saldo",
            '31/01/2026,Supermercado,"-45,60","0,00"',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 1, "duplicadas": 0}
    assert session.query(Transacao).count() == 2


def test_linha_sem_saldo_e_duplicada_da_transacao_com_saldo_escrito(client, session, tmp_path):
    """Uma linha sem saldo absorve a cópia a que se escreveu o saldo à mão.

    Semeia-se `(2026-01-31, "Supermercado", -45.6, saldo=954.4)`, como se o
    saldo tivesse sido escrito à mão. `CSV_DUAS_LINHAS` (perfil sem saldo) traz
    o Supermercado sem saldo, que é a mesma transação, e o Salário, que é nova:
    `{"inseridas": 1, "duplicadas": 1}`; a BD fica com 1 + 1 = 2, e o saldo
    escrito continua lá.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    session.add(
        Transacao(
            data=date(2026, 1, 31),
            descricao="Supermercado",
            valor=-45.6,
            saldo=954.4,
            conta_id=conta.id,
        )
    )
    session.commit()
    caminho = escrever_csv(tmp_path / "sem_saldo.csv", CSV_DUAS_LINHAS)

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 1, "duplicadas": 1}
    assert session.query(Transacao).count() == 2
    assert session.query(Transacao.saldo).filter(Transacao.descricao == "Supermercado").all() == [
        (954.4,)
    ]


def test_linhas_sem_saldo_contam_as_copias_com_e_sem_saldo(client, session, tmp_path):
    """Num perfil sem saldo, cada cópia na BD, com ou sem saldo, absorve uma
    linha.

    Semeiam-se 2 Supermercados de 31/01/2026 a -45,60: um sem saldo e um com o
    saldo 954,4 escrito à mão. O ficheiro traz 3 linhas iguais, sem saldo:
    as 2 cópias absorvem 2, sobra 1 -> `{"inseridas": 1, "duplicadas": 2}`; a
    BD fica com 2 + 1 = 3.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    for saldo in (None, 954.4):
        session.add(
            Transacao(
                data=date(2026, 1, 31),
                descricao="Supermercado",
                valor=-45.6,
                saldo=saldo,
                conta_id=conta.id,
            )
        )
    session.commit()
    caminho = escrever_csv(
        tmp_path / "tres.csv",
        ("Data,Descrição,Valor",) + ('31/01/2026,Supermercado,"-45,60"',) * 3,
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 1, "duplicadas": 2}
    assert session.query(Transacao).count() == 3


def test_com_saldo_no_extracto_linha_sem_saldo_nao_absorve_copia_com_saldo(
    client, session, tmp_path
):
    """Num perfil com saldo, a comparação continua a usar os quatro campos.

    Semeia-se `(2026-01-31, "Supermercado", -45.6, saldo=950.0)`. O ficheiro
    (perfil com saldo) traz a mesma linha com a célula do saldo vazia -> None.
    As chaves diferem no saldo (950.0 contra None) -> não é duplicada:
    `{"inseridas": 1, "duplicadas": 0}`; a BD fica com 2.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id, tem_saldo=True, coluna_saldo=3)
    session.add(
        Transacao(
            data=date(2026, 1, 31),
            descricao="Supermercado",
            valor=-45.6,
            saldo=950.0,
            conta_id=conta.id,
        )
    )
    session.commit()
    caminho = escrever_csv(
        tmp_path / "celula_vazia.csv",
        (
            "Data,Descrição,Valor,Saldo",
            '31/01/2026,Supermercado,"-45,60",',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 1, "duplicadas": 0}
    assert session.query(Transacao).count() == 2


def test_dedup_e_por_conta(client, session, tmp_path):
    """A mesma transacção noutra conta não conta como duplicado.

    Semeia-se a transacção `(2026-01-31, "Supermercado", -45.6, None)` na conta
    2. O perfil aponta para a conta 1. Na consulta de existentes
    (`filter(Transacao.conta_id == conta_id)`), a linha da conta 2 não entra,
    logo a linha importada é nova -> `{"inseridas": 1, "duplicadas": 0}`. A base
    de dados fica com 2 linhas: uma por conta.
    """
    conta1 = _criar_conta(session, nome="Conta 1")
    conta2 = _criar_conta(session, nome="Conta 2")
    perfil = _criar_perfil(session, conta_id=conta1.id)
    session.add(
        Transacao(
            data=date(2026, 1, 31),
            descricao="Supermercado",
            valor=-45.6,
            saldo=None,
            conta_id=conta2.id,
        )
    )
    session.commit()
    caminho = escrever_csv(
        tmp_path / "extrato.csv",
        (
            "Data,Descrição,Valor",
            '31/01/2026,Supermercado,"-45,60"',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 1, "duplicadas": 0}
    assert session.query(Transacao).count() == 2
    nova = session.query(Transacao).filter_by(conta_id=conta1.id).one()
    assert (nova.data, nova.descricao, nova.valor, nova.saldo) == (
        date(2026, 1, 31),
        "Supermercado",
        -45.6,
        None,
    )


def test_linhas_repetidas_no_mesmo_ficheiro_nao_sao_deduplicadas(client, session, tmp_path):
    """Duas linhas iguais no mesmo ficheiro entram as duas.

    Comportamento actual: `existentes` conta só o que já estava na conta (0
    cópias) e nunca recebe as chaves novas, por isso a segunda linha repetida
    não é vista como duplicada -> `{"inseridas": 2, "duplicadas": 0}`. É
    defensável: dois movimentos iguais no mesmo dia podem ser reais (dois
    cafés) e a deduplicação é, por desenho, só contra o que já existia na
    conta. Fixa-se o comportamento actual.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(
        tmp_path / "repetido.csv",
        (
            "Data,Descrição,Valor",
            '31/01/2026,Supermercado,"-45,60"',
            '31/01/2026,Supermercado,"-45,60"',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 2, "duplicadas": 0}
    assert session.query(Transacao).count() == 2


def test_importar_com_perfil_sem_conta_da_400_e_nao_grava(client, session, tmp_path):
    """Um perfil sem conta (por exemplo, a conta foi apagada) não importa (4.1).

    Antes, as linhas entravam com `conta_id=None`: contavam nas estatísticas mas
    nunca na liquidez. Cálculo à mão: um pedido recusado -> 0 transacções.
    """
    perfil = _criar_perfil(session, conta_id=None)
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_DUAS_LINHAS)

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 400
    assert r.json() == {
        "detail": "Este perfil não tem conta associada. Edita o perfil e escolhe uma conta."
    }
    assert session.query(Transacao).count() == 0


@pytest.mark.parametrize(
    "na_bd, no_ficheiro, esperado, total",
    [
        # O exemplo: um café no 1.º extracto, dois no seguinte.
        # 1 cópia na BD absorve 1 linha; sobra 1 -> 1 inserida, 1 duplicada;
        # BD: 1 + 1 = 2.
        (1, 2, {"inseridas": 1, "duplicadas": 1}, 2),
        # 2 na BD, 3 no ficheiro (antes dava 0 e 3).
        # 2 absorvidas, sobra 1 -> 1 inserida, 2 duplicadas; BD: 2 + 1 = 3.
        (2, 3, {"inseridas": 1, "duplicadas": 2}, 3),
        # O ficheiro traz menos do que a BD: as 2 cópias chegam para a 1 linha
        # -> 0 inseridas, 1 duplicada; BD fica com 2.
        (2, 1, {"inseridas": 0, "duplicadas": 1}, 2),
    ],
)
def test_dedup_conta_as_copias_que_ja_existem(
    client, session, tmp_path, na_bd, no_ficheiro, esperado, total
):
    """Linhas iguais: entram as que o ficheiro tem a mais do que a BD (3.2)."""
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    cabecalho = ("Data,Descrição,Valor",)
    cafe = '03/02/2026,Café,"-0,80"'
    primeiro = escrever_csv(tmp_path / "primeiro.csv", cabecalho + (cafe,) * na_bd)
    segundo = escrever_csv(tmp_path / "segundo.csv", cabecalho + (cafe,) * no_ficheiro)

    _pedido_importar(client, perfil.id, primeiro.read_bytes())
    r = _pedido_importar(client, perfil.id, segundo.read_bytes())

    assert r.status_code == 200
    assert r.json() == esperado
    assert session.query(Transacao).count() == total


def test_dedup_por_contagem_nao_mistura_chaves(client, session, tmp_path):
    """A cópia de um café não absorve uma linha diferente.

    BD: 1 café. Ficheiro: 2 cafés e 1 supermercado.
      café: 2 no ficheiro - 1 na BD -> 1 inserido, 1 duplicado
      supermercado: 0 na BD -> 1 inserido
    -> {"inseridas": 2, "duplicadas": 1}; BD: 1 + 2 = 3, com 2 cafés.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    cabecalho = ("Data,Descrição,Valor",)
    cafe = '03/02/2026,Café,"-0,80"'
    supermercado = '03/02/2026,Supermercado,"-45,60"'
    primeiro = escrever_csv(tmp_path / "primeiro.csv", cabecalho + (cafe,))
    segundo = escrever_csv(tmp_path / "segundo.csv", cabecalho + (cafe, supermercado, cafe))

    _pedido_importar(client, perfil.id, primeiro.read_bytes())
    r = _pedido_importar(client, perfil.id, segundo.read_bytes())

    assert r.json() == {"inseridas": 2, "duplicadas": 1}
    assert session.query(Transacao).count() == 3
    assert session.query(Transacao).filter(Transacao.descricao == "Café").count() == 2


# ---------------------------------------------------------------------------
# /importar — regras de categorização e casos-limite
# ---------------------------------------------------------------------------


def test_importar_aplica_regras_de_categorizacao(client, session, tmp_path):
    """Durante a importação, as regras da base de dados categorizam as linhas.

    `importar_transacoes` carrega todas as `RegraCategorizacao` (linha 26) e
    chama `aplicar_regras` por cada transacção nova (linha 57). Semeiam-se duas
    regras desencontradas (os padrões não se cruzam, para não depender da ordem;
    a precedência é testada em `test_importador_regras.py`):
      "supermercado" (categoria definida) -> categoriza
      "café"         (categoria_id None)  -> exclusão, deixa sem categoria
    O ficheiro traz "Supermercado" e "Café":
      Supermercado -> fica com (categoria, subcategoria) da regra
      Café         -> fica com (None, None)
    """
    categoria = Categoria(nome="Alimentação", tipo=TipoCategoria.despesa)
    session.add(categoria)
    session.commit()
    session.refresh(categoria)
    subcategoria = Subcategoria(nome="Supermercado", categoria_id=categoria.id)
    session.add(subcategoria)
    session.commit()
    session.refresh(subcategoria)

    session.add(
        RegraCategorizacao(
            palavra_chave="supermercado",
            categoria_id=categoria.id,
            subcategoria_id=subcategoria.id,
        )
    )
    session.add(
        RegraCategorizacao(
            palavra_chave="café",
            categoria_id=None,
            subcategoria_id=None,
        )
    )
    session.commit()

    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(
        tmp_path / "com_regras.csv",
        (
            "Data,Descrição,Valor",
            '31/01/2026,Supermercado,"-45,60"',
            '01/02/2026,Café,"-3,20"',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 2, "duplicadas": 0}

    supermercado = session.query(Transacao).filter_by(descricao="Supermercado").one()
    assert (supermercado.categoria_id, supermercado.subcategoria_id) == (
        categoria.id,
        subcategoria.id,
    )
    cafe = session.query(Transacao).filter_by(descricao="Café").one()
    assert (cafe.categoria_id, cafe.subcategoria_id) == (None, None)


def test_importar_sem_transacoes_validas_da_400(client, session, tmp_path):
    """Só com uma linha, e com erro, o endpoint recusa com 400.

    Cálculo à mão: a única linha de dados (linha 2) tem data inválida, logo
    `erros` tem 1 entrada; qualquer erro recusa o ficheiro, com a
    mensagem a apontar a linha 2. A base de dados fica vazia.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(
        tmp_path / "tudo_invalido.csv",
        (
            "Data,Descrição,Valor",
            '31/02/2026,Café,"-3,20"',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 400
    assert r.json() == {
        "detail": (
            "Nada foi importado: o ficheiro tem 1 linha com erro (a primeira é a "
            "linha 2: data inválida: '31/02/2026' (formato esperado: %d/%m/%Y)). "
            "Corrige o ficheiro ou o perfil; a pré-visualização mostra todas."
        ),
    }
    assert session.query(Transacao).count() == 0


def test_importar_com_uma_linha_com_erro_nao_importa_nenhuma(client, session, tmp_path):
    """Uma linha com erro recusa o ficheiro inteiro, mesmo com outras válidas.

    Antes da correcção, a importação gravava as linhas válidas e ignorava as outras sem
    o dizer na resposta. Decisão do utilizador: qualquer erro recusa tudo.
    Cálculo à mão, perfil em vírgula:
      linha 2 "-3,20"     -> válida
      linha 3 "1,234.56"  -> o decimal (vírgula) não é o último separador -> erro
      linha 4 "31/13/2026" -> data inválida -> erro
      2 erros, o primeiro na linha 3 -> 400, e 0 transacções gravadas.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(
        tmp_path / "misto.csv",
        (
            "Data,Descrição,Valor",
            '01/02/2026,Café,"-3,20"',
            '02/02/2026,Renda,"1,234.56"',
            '31/13/2026,Luz,"-40,00"',
        ),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 400
    assert r.json()["detail"] == (
        "Nada foi importado: o ficheiro tem 2 linhas com erro (a primeira é a "
        "linha 3: valor '1,234.56' não corresponde ao separador decimal do "
        "perfil (',')). Corrige o ficheiro ou o perfil; a pré-visualização "
        "mostra todas."
    )
    assert session.query(Transacao).count() == 0


def test_importar_ficheiro_sem_dados_da_200_com_zero(client, session, tmp_path):
    """Um ficheiro só com cabeçalho (zero transacções, zero erros) dá 200 a zeros.

    O parser devolve `{transacoes: [], total_linhas: 0, erros: []}`; como `erros`
    está vazio, a guarda dos erros não dispara e chama-se
    `importar_transacoes([])`, que devolve `{"inseridas": 0, "duplicadas": 0}`.
    Comportamento actual, considerado defensável: não haver nada para importar
    não é um erro. Fixa-se tal como está.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(tmp_path / "so_cabecalho.csv", ("Data,Descrição,Valor",))

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 200
    assert r.json() == {"inseridas": 0, "duplicadas": 0}
    assert session.query(Transacao).count() == 0


def test_importar_com_perfil_inexistente_da_404(client):
    """Um `perfil_id` que não existe dá 404, sem tocar na base de dados."""
    r = _pedido_importar(client, 999999, b"")

    assert r.status_code == 404
    assert r.json() == {"detail": "Perfil não encontrado."}


# ---------------------------------------------------------------------------
# /importar — registo da importação, para a poder desfazer
# ---------------------------------------------------------------------------


def test_importar_regista_a_importacao_e_marca_as_transaccoes(client, session, tmp_path):
    """Uma importação que insere fica registada, e as suas linhas levam o id dela.

    Cálculo à mão: `CSV_DUAS_LINHAS` insere 2 linhas novas e nenhuma duplicada,
    numa conta vazia. Fica 1 importação, da conta do perfil, com o nome com que o
    ficheiro foi enviado, `inseridas` 2, `duplicadas` 0 e a data e a hora do
    pedido; as 2 transacções têm `importacao_id` igual ao id dela.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(tmp_path / "extrato.csv", CSV_DUAS_LINHAS)

    antes = datetime.now()
    r = _pedido_importar(client, perfil.id, caminho.read_bytes(), nome="janeiro.csv")
    depois = datetime.now()

    assert r.status_code == 200
    importacao = session.query(Importacao).one()
    assert (
        importacao.conta_id,
        importacao.ficheiro,
        importacao.inseridas,
        importacao.duplicadas,
    ) == (conta.id, "janeiro.csv", 2, 0)
    assert antes <= importacao.data_hora <= depois
    assert [t.importacao_id for t in session.query(Transacao).all()] == [
        importacao.id,
        importacao.id,
    ]


def test_importacao_com_novas_e_duplicadas_so_marca_as_novas(client, session, tmp_path):
    """As linhas duplicadas não são da importação nova: ficam com a marca antiga.

    Cálculo à mão: a 1.ª importação traz Supermercado e Salário (importação A).
    A 2.ª traz as mesmas duas mais uma Renda de -600,00: 1 inserida e 2
    duplicadas (importação B). Supermercado e Salário ficam com A, a Renda com B.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    primeiro = escrever_csv(tmp_path / "a.csv", CSV_DUAS_LINHAS)
    segundo = escrever_csv(tmp_path / "b.csv", CSV_DUAS_LINHAS + ('03/02/2026,Renda,"-600,00"',))

    _pedido_importar(client, perfil.id, primeiro.read_bytes(), nome="a.csv")
    r = _pedido_importar(client, perfil.id, segundo.read_bytes(), nome="b.csv")

    assert r.json() == {"inseridas": 1, "duplicadas": 2}
    a, b = session.query(Importacao).order_by(Importacao.id).all()
    assert (a.ficheiro, a.inseridas, a.duplicadas) == ("a.csv", 2, 0)
    assert (b.ficheiro, b.inseridas, b.duplicadas) == ("b.csv", 1, 2)
    marcas = {t.descricao: t.importacao_id for t in session.query(Transacao).all()}
    assert marcas == {"Supermercado": a.id, "Salário": a.id, "Renda": b.id}


def test_importacao_so_com_duplicadas_nao_fica_registada(client, session, tmp_path):
    """Sem nada inserido, não há nada a desfazer: não se regista.

    Cálculo à mão: o mesmo ficheiro duas vezes; a 2.ª dá 0 inseridas e 2
    duplicadas, e continua a haver só a importação da 1.ª.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    conteudo = escrever_csv(tmp_path / "extrato.csv", CSV_DUAS_LINHAS).read_bytes()

    _pedido_importar(client, perfil.id, conteudo)
    r = _pedido_importar(client, perfil.id, conteudo)

    assert r.json() == {"inseridas": 0, "duplicadas": 2}
    assert session.query(Importacao).count() == 1


def test_importacao_recusada_nao_fica_registada(client, session, tmp_path):
    """Um ficheiro com uma linha com erro não importa nada, nem o registo.

    Cálculo à mão: a 2.ª linha tem a data «32/01/2026», inválida; o endpoint dá
    400 antes de chamar `importar_transacoes`, e ficam 0 importações e 0
    transacções.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    caminho = escrever_csv(
        tmp_path / "erro.csv",
        ("Data,Descrição,Valor", '31/01/2026,Supermercado,"-45,60"', '32/01/2026,Café,"-0,80"'),
    )

    r = _pedido_importar(client, perfil.id, caminho.read_bytes())

    assert r.status_code == 400
    assert session.query(Importacao).count() == 0
    assert session.query(Transacao).count() == 0


# ---------------------------------------------------------------------------
# /historico e desfazer uma importação
# ---------------------------------------------------------------------------

# Uma compra de um ETF, para os cenários com movimentos de ativo.
# Cálculo à mão: "-100,00" -> -100.00, a 03/02/2026.
CSV_COMPRA_ETF = ("Data,Descrição,Valor", '03/02/2026,Compra ETF,"-100,00"')


def _importar_ficheiro(client, perfil, tmp_path, nome, linhas):
    caminho = escrever_csv(tmp_path / nome, linhas)
    r = _pedido_importar(client, perfil.id, caminho.read_bytes(), nome=nome)
    assert r.status_code == 200
    return r.json()


def _desfazer(client, importacao_id, apagar_movimentos=None):
    params = {} if apagar_movimentos is None else {"apagar_movimentos": apagar_movimentos}
    return client.delete(f"/api/importacao/{importacao_id}", params=params)


def _ativo_com_unidades(session):
    tipo = TipoAtivo(nome="ETF", tem_unidades=True)
    session.add(tipo)
    session.commit()
    ativo = Ativo(nome="ETF Mundo", tipo_id=tipo.id, contabilizacao=TipoContabilizacao.investimento)
    session.add(ativo)
    session.commit()
    return ativo


def _comprar_com_a_transacao(client, session, ativo):
    """Trata a compra importada como o ecrã faz: 10 unidades a 10,00."""
    transacao = session.query(Transacao).filter_by(descricao="Compra ETF").one()
    r = client.post(
        "/api/patrimonio/movimentos",
        json={
            "ativo_id": ativo.id,
            "transacao_id": transacao.id,
            "tipo_movimento": "compra",
            "data": "2026-02-03",
            "quantidade": 10,
            "preco_unitario": 10.0,
            "valor_total": -100.0,
        },
    )
    assert r.status_code == 200


def test_historico_lista_a_mais_recente_primeiro_e_quais_se_desfazem(client, session, tmp_path):
    """Só a última importação de cada conta se pode desfazer.

    Cálculo à mão: a conta X importa a.csv (2 linhas) e depois b.csv (as mesmas
    2 mais a Renda: 1 inserida, 2 duplicadas); a conta Y importa c.csv (2
    linhas). Ids 1, 2 e 3, listados por ordem inversa: c (Y, a última de Y), b
    (X, a última de X) e a (X, já não é a última).
    """
    x = _criar_conta(session, "Conta X")
    y = _criar_conta(session, "Conta Y")
    perfil_x = _criar_perfil(session, nome="Perfil X", conta_id=x.id)
    perfil_y = _criar_perfil(session, nome="Perfil Y", conta_id=y.id)
    _importar_ficheiro(client, perfil_x, tmp_path, "a.csv", CSV_DUAS_LINHAS)
    _importar_ficheiro(
        client, perfil_x, tmp_path, "b.csv", CSV_DUAS_LINHAS + ('03/02/2026,Renda,"-600,00"',)
    )
    _importar_ficheiro(client, perfil_y, tmp_path, "c.csv", CSV_DUAS_LINHAS)

    r = client.get("/api/importacao/historico")

    assert r.status_code == 200
    assert [
        (
            i["ficheiro"],
            i["conta_id"],
            i["conta_nome"],
            i["inseridas"],
            i["duplicadas"],
            i["pode_desfazer"],
        )
        for i in r.json()
    ] == [
        ("c.csv", y.id, "Conta Y", 2, 0, True),
        ("b.csv", x.id, "Conta X", 1, 2, True),
        ("a.csv", x.id, "Conta X", 2, 0, False),
    ]


def test_desfazer_a_ultima_apaga_as_suas_transaccoes_e_o_registo(client, session, tmp_path):
    """Desfazer b.csv tira só a Renda; Supermercado e Salário são de a.csv.

    Cálculo à mão: a.csv insere 2, b.csv insere 1 (a Renda) e dá 2 duplicadas.
    Desfazer b dá 204; ficam as 2 transacções de a e só o registo de a, que
    passa a ser a última da conta e se pode desfazer.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    _importar_ficheiro(client, perfil, tmp_path, "a.csv", CSV_DUAS_LINHAS)
    _importar_ficheiro(
        client, perfil, tmp_path, "b.csv", CSV_DUAS_LINHAS + ('03/02/2026,Renda,"-600,00"',)
    )
    b = session.query(Importacao).filter_by(ficheiro="b.csv").one()

    r = _desfazer(client, b.id)

    assert r.status_code == 204
    session.expire_all()
    assert sorted(t.descricao for t in session.query(Transacao).all()) == [
        "Salário",
        "Supermercado",
    ]
    assert [i.ficheiro for i in session.query(Importacao).all()] == ["a.csv"]
    historico = client.get("/api/importacao/historico").json()
    assert [(i["ficheiro"], i["pode_desfazer"]) for i in historico] == [("a.csv", True)]


def test_depois_de_desfazer_o_mesmo_ficheiro_volta_a_entrar(client, session, tmp_path):
    """Desfeita, a importação pode ser repetida: as linhas não ficam duplicadas.

    Cálculo à mão: importar, desfazer e importar outra vez o mesmo ficheiro dá
    2 inseridas e 0 duplicadas, porque a conta ficou vazia.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    _importar_ficheiro(client, perfil, tmp_path, "a.csv", CSV_DUAS_LINHAS)
    _desfazer(client, session.query(Importacao).one().id)

    assert _importar_ficheiro(client, perfil, tmp_path, "a.csv", CSV_DUAS_LINHAS) == {
        "inseridas": 2,
        "duplicadas": 0,
    }


def test_desfazer_uma_que_nao_e_a_ultima_da_conta_da_409(client, session, tmp_path):
    """a.csv já tem uma importação a seguir na mesma conta: 409, nada muda.

    Cálculo à mão: a insere 2, b insere 1; desfazer a é recusado, e ficam as 3
    transacções e os 2 registos.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    _importar_ficheiro(client, perfil, tmp_path, "a.csv", CSV_DUAS_LINHAS)
    _importar_ficheiro(
        client, perfil, tmp_path, "b.csv", CSV_DUAS_LINHAS + ('03/02/2026,Renda,"-600,00"',)
    )
    a = session.query(Importacao).filter_by(ficheiro="a.csv").one()

    r = _desfazer(client, a.id)

    assert r.status_code == 409
    assert r.json() == {"detail": "Só se pode desfazer a importação mais recente de cada conta."}
    assert session.query(Transacao).count() == 3
    assert session.query(Importacao).count() == 2


def test_a_ultima_de_outra_conta_nao_impede_desfazer(client, session, tmp_path):
    """A regra é por conta: uma importação mais recente noutra conta não conta.

    Cálculo à mão: X importa a.csv (id 1), Y importa c.csv (id 2). Desfazer a
    dá 204: é a última de X. Ficam as 2 transacções de c.
    """
    x = _criar_conta(session, "Conta X")
    y = _criar_conta(session, "Conta Y")
    perfil_x = _criar_perfil(session, nome="Perfil X", conta_id=x.id)
    perfil_y = _criar_perfil(session, nome="Perfil Y", conta_id=y.id)
    _importar_ficheiro(client, perfil_x, tmp_path, "a.csv", CSV_DUAS_LINHAS)
    _importar_ficheiro(client, perfil_y, tmp_path, "c.csv", CSV_DUAS_LINHAS)
    a = session.query(Importacao).filter_by(ficheiro="a.csv").one()

    r = _desfazer(client, a.id)

    assert r.status_code == 204
    session.expire_all()
    assert {t.conta_id for t in session.query(Transacao).all()} == {y.id}
    assert session.query(Transacao).count() == 2


def test_desfazer_importacao_inexistente_da_404(client):
    r = _desfazer(client, 999999)

    assert r.status_code == 404
    assert r.json() == {"detail": "Importação não encontrada."}


def test_com_movimentos_sem_confirmar_da_409_com_a_lista(client, session, tmp_path):
    """A compra importada já foi tratada como ativo: 409 com o movimento, nada muda.

    Cálculo à mão: o movimento é a compra de 10 unidades por -100,00 a
    03/02/2026, do «ETF Mundo». Ficam a transacção, o movimento e o registo.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    _importar_ficheiro(client, perfil, tmp_path, "etf.csv", CSV_COMPRA_ETF)
    ativo = _ativo_com_unidades(session)
    _comprar_com_a_transacao(client, session, ativo)
    movimento = session.query(MovimentoAtivo).one()

    r = _desfazer(client, session.query(Importacao).one().id)

    assert r.status_code == 409
    assert r.json() == {
        "detail": {
            "mensagem": "Há transações desta importação já tratadas como ativos.",
            "movimentos": [
                {
                    "id": movimento.id,
                    "ativo_nome": "ETF Mundo",
                    "tipo_movimento": "compra",
                    "data": "2026-02-03",
                    "valor_total": -100.0,
                }
            ],
        }
    }
    assert session.query(Transacao).count() == 1
    assert session.query(MovimentoAtivo).count() == 1
    assert session.query(Importacao).count() == 1


def test_com_movimentos_e_confirmacao_apaga_tudo_menos_o_preco(client, session, tmp_path):
    """Confirmado, saem o movimento, a transacção e o registo; o preço fica.

    Cálculo à mão: a compra a 10,00 gravou o preço de 03/02/2026 (como no
    ecrã). Desfazer com `apagar_movimentos=true` dá 204 e deixa 0 movimentos,
    0 transacções, 0 importações e 1 preço, de 10,00.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    _importar_ficheiro(client, perfil, tmp_path, "etf.csv", CSV_COMPRA_ETF)
    ativo = _ativo_com_unidades(session)
    _comprar_com_a_transacao(client, session, ativo)

    r = _desfazer(client, session.query(Importacao).one().id, apagar_movimentos=True)

    assert r.status_code == 204
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 0
    assert session.query(Transacao).count() == 0
    assert session.query(Importacao).count() == 0
    assert [(p.data, p.preco) for p in session.query(PrecoAtivo).all()] == [
        (date(2026, 2, 3), 10.0)
    ]


def test_com_confirmacao_recusa_se_uma_venda_ficar_sem_unidades(client, session, tmp_path):
    """Sem a compra importada, a venda posterior ficava a descoberto: 422, nada muda.

    Cálculo à mão: a compra de 10 unidades (03/02/2026) vem da importação; a
    venda de 4 (10/02/2026) foi registada à parte. Sem a compra, há 0 unidades
    a 10/02, e a venda de 4 excede-as. Ficam os 2 movimentos, a transacção e o
    registo.
    """
    conta = _criar_conta(session)
    perfil = _criar_perfil(session, conta_id=conta.id)
    _importar_ficheiro(client, perfil, tmp_path, "etf.csv", CSV_COMPRA_ETF)
    ativo = _ativo_com_unidades(session)
    _comprar_com_a_transacao(client, session, ativo)
    session.add(
        MovimentoAtivo(
            ativo_id=ativo.id,
            tipo_movimento=TipoMovimento.venda,
            data=date(2026, 2, 10),
            quantidade=4,
            valor_total=48.0,
        )
    )
    session.commit()

    r = _desfazer(client, session.query(Importacao).one().id, apagar_movimentos=True)

    assert r.status_code == 422
    assert r.json() == {
        "detail": "A venda de 10/02/2026 (4 unidades) excede as 0 unidades em carteira nessa data."
    }
    session.expire_all()
    assert session.query(MovimentoAtivo).count() == 2
    assert session.query(Transacao).count() == 1
    assert session.query(Importacao).count() == 1

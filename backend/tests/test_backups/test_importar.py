"""Testes de caracterização de `POST /api/backups/importar`.

Portados do `test_backups.py` antigo (Pedro, 16 de Setembro, commit `398130b`),
com as fixtures novas desta sub-pasta. Os quatro testes de lá — a rejeição do
ficheiro não SQLite, a rejeição de um SQLite sem as tabelas esperadas, o ciclo
de ida e volta e o `xfail` sobre as colunas — estão todos aqui, e o `xfail`
passou a teste de caracterização a afirmar o comportamento actual.

O endpoint, lido linha a linha
------------------------------
`backend/routers/backups.py`, `importar_backup` (linha 62):

1. linha 64: o nome tem de acabar em `.db`; caso contrário, 400 `Ficheiro inválido`.
2. linha 68: o conteúdo não pode ser vazio; caso contrário, 400 `Ficheiro vazio`.
3. linhas 71-72: os caminhos são `DB_PATH + ".tmp"` e `DB_PATH + ".anterior"`,
   ou seja, ao lado da BD — que, por causa do `conftest`, está no directório
   temporário.
4. linha 80: o conteúdo vai para o `.tmp`, e só depois é validado.
5. linha 86 → `_validar_sqlite` (linha 40): `PRAGMA integrity_check` (linha 44) e
   a lista de tabelas de `sqlite_master` (linhas 48-53).
6. linha 91: `TABELAS_ESPERADAS - tabelas`; se sobrar alguma, 400 com a lista.
7. linha 108: `os.replace` — aqui a BD é mesmo substituída.
8. linhas 111-113: verificação pós-troca, um `SELECT COUNT(*)` a cada uma das 3.
9. linhas 130-131: só depois de tudo confirmar é que o `.anterior` é apagado.

Os dois grupos
--------------
O ficheiro separa o que o código faz bem do que fixa o que parece estar errado.
Nenhum dos testes é corrigido: onde o comportamento é questionável, o teste
afirma-o e leva `# DEVIDA-TECNICA: D6`, a remeter para
`docs/divida-tecnica.md`. As correções que o D6 pedir farão estes testes falhar
de propósito, que é o que se quer de um teste de caracterização.

* **Comportamento correcto** (cenários 1 a 8): as três rejeições que existem, o
  ficheiro corrompido, o ciclo de ida e volta e a amarração da lista de tabelas
  ao modelo.
* **Comportamento questionável** (cenários 9 a 11): um `.db` com as 3 tabelas e
  mais nada é aceite e destrói a BD; um `.db` com as 3 tabelas e as colunas
  erradas também; e a lista esperada é um subconjunto estrito das 11 tabelas do
  modelo.

Valores esperados
-----------------
Todos os valores esperados estão escritos à mão, como constantes, com o
raciocínio no comentário de cada teste. Nenhum foi copiado de uma execução. O
que se mediu foi a forma do erro (`OperationalError`, e não outra excepção do
SQLAlchemy) e o texto das mensagens, para que os testes afirmem o comportamento
real e não o imaginado.

Porquê uma sub-pasta
--------------------
Explicado no `conftest.py` desta pasta: o endpoint não usa `get_db` e trabalha
com a `engine` de ficheiro do módulo, pelo que a BD em memória do conftest pai
não chega.

Rollback por cobrir
------------------
O caminho de erro das linhas 115-127, que é o **único** que usa o `.anterior` a
sério, fica por cobrir. Não é atingível sem mexer em código de produção: para o
`SELECT COUNT(*)` da linha 113 falhar depois de o ficheiro ter passado a
validação, alguma das 3 tabelas teria de desaparecer entre a validação e a
checagem, e o ficheiro é o mesmo nos dois momentos. Tentado com as três
tabelas como *views*, que rebentariam na consulta: não passa, porque a consulta
da linha 51 filtra por `type='table'` e as views não aparecem, pelo que o
pedido é rejeitado na linha 94 com 400 e nunca chega ao `os.replace`.
"""

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

from database import Ativo, Base, Conta, SessionLocal, engine
from routers.backups import TABELAS_ESPERADAS


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

# As três tabelas que `TABELAS_ESPERADAS` exige, cada uma só com as colunas
# mínimas de que o endpoint precisa. É o ficheiro mais magro que a validação
# aceita, e o que serve de ficheiro de entrada a vários cenários.
MINIMO_3 = {
    "transacoes": "id INTEGER PRIMARY KEY, data TEXT, descricao TEXT, valor REAL",
    "categorias": "id INTEGER PRIMARY KEY, nome TEXT, tipo TEXT",
    "contas": "id INTEGER PRIMARY KEY, nome TEXT, saldo_referencia REAL, "
              "data_referencia TEXT, ativa INTEGER",
}

# As 11 tabelas do modelo (`Base.metadata.sorted_tables`), escritas à mão. A
# diferença para `TABELAS_ESPERADAS` está no cenário 11.
TABELAS_DO_MODELO = {
    "ativos", "categorias", "configuracao", "contas", "movimentos_ativo",
    "perfis_importacao", "precos_ativo", "regras_categorizacao", "subcategorias",
    "tipos_ativo", "transacoes",
}

# Uma conta semeada antes de cada cenário. O saldo e a data não são lidos por
# nenhum destes testes: o que interessa é o nome, para se ver o que sobrevive a
# um restauro.
CONTA_REAL = "Conta Real"


def criar_sqlite(caminho: Path, tabelas: dict[str, str]) -> bytes:
    """Cria um `.db` em `caminho` com as tabelas dadas e devolve os bytes.

    `caminho` é sempre um ficheiro dentro do `tmp_path` do teste, o que resolve
    o que o helper antigo fazia por conta própria: o nome saía de
    `abs(hash(frozenset(tabelas)))`, e o hash de `str` é salgado por processo —
    o nome mudava entre execuções, num directório partilhado por todos os
    testes, e a remoção só acontecia no fim e sem `try/finally`.
    """
    if caminho.exists():
        caminho.unlink()
    con = sqlite3.connect(caminho)
    try:
        for nome, colunas in tabelas.items():
            con.execute(f"CREATE TABLE {nome} ({colunas})")
        con.commit()
    finally:
        con.close()
    return caminho.read_bytes()


def integridade(caminho: Path) -> tuple[str, str]:
    """`(estado, detalhe)` do `PRAGMA integrity_check` de um ficheiro.

    Devolve `("linha", <primeira coluna>)` se o SQLite responder, e
    `("erro", <mensagem>)` se o `sqlite3` levantar `DatabaseError`. Um ficheiro
    íntegro dá `("linha", "ok")`.
    """
    con = sqlite3.connect(caminho)
    try:
        linha = con.execute("PRAGMA integrity_check").fetchone()
        if linha is None:
            return ("linha", "")
        return ("linha", str(linha[0]))
    except sqlite3.DatabaseError as exc:
        return ("erro", str(exc))
    finally:
        con.close()


def semear_conta_real() -> None:
    """Semeia a `Conta Real` na BD em ficheiro."""
    db = sessao_nova()
    try:
        db.add(Conta(nome=CONTA_REAL, saldo_referencia=100.0,
                     data_referencia=date(2024, 1, 1)))
        db.commit()
    finally:
        db.close()


def sessao_nova():
    """Sessão nova sobre a BD em ficheiro, depois de `dispose()`.

    O `dispose()` é o que garante que a próxima ligação abre o ficheiro que está
    no disco *agora*. Sem ele, uma sessão pode ficar com uma ligação antiga a um
    ficheiro que o endpoint já trocou.
    """
    engine.dispose()
    return SessionLocal()


def nomes_das_contas() -> list[str]:
    """Lê os nomes das contas pela BD em ficheiro."""
    db = sessao_nova()
    try:
        return [conta.nome for conta in db.query(Conta).all()]
    finally:
        db.close()


def existe(caminho_bd: Path, sufixo: str) -> bool:
    """Se existe o ficheiro que o endpoint usa com aquele sufixo.

    Os caminhos são `DB_PATH + ".tmp"` e `DB_PATH + ".anterior"`
    (`backups.py:71-72`), pelo que é aqui que se vai procurar o que ficou.
    """
    return Path(str(caminho_bd) + sufixo).exists()


def importar(client, conteudo: bytes, nome: str = "backup.db"):
    return client.post(
        "/api/backups/importar",
        files={"file": (nome, conteudo, "application/octet-stream")},
    )


# ---------------------------------------------------------------------------
# Comportamento correcto
# ---------------------------------------------------------------------------

def test_nao_sqlite_e_rejeitado_e_a_bd_fica_intacta(client, bd_em_ficheiro):
    """Um ficheiro que não é SQLite é recusado, e nada se mexe na BD.

    Cálculo à mão: o endpoint escreve o conteúdo no `.tmp` (linha 80) e chama
    `_validar_sqlite` (linha 86). O `sqlite3.connect` da linha 42 não falha —
    abre lazy — e é o primeiro `execute`, o `PRAGMA integrity_check` da linha 44,
    que levanta `DatabaseError`, apanhado na linha 54 e devolvido como 400. A
    linha 46 não é alcançada: para lá chegar, o `integrity_check` teria de
    responder com uma linha, e aqui responde com uma excepção.

    A BD fica intacta porque o `.tmp` é apagado na linha 88, ainda antes de a
    excepção subir, e o `os.replace` da linha 108 nunca chega a correr.
    """
    semear_conta_real()

    resposta = importar(client, b"isto nao e uma base de dados sqlite")

    assert resposta.status_code == 400
    assert resposta.json()["detail"].startswith(
        "O ficheiro não é uma base de dados SQLite válida"
    )
    assert not existe(bd_em_ficheiro, ".tmp")
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]


def test_sqlite_sem_as_tabelas_esperadas_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um SQLite válido que não tem as 3 tabelas é recusado, com a lista.

    Cálculo à mão: o ficheiro passa o `integrity_check` (linha 44) e a consulta a
    `sqlite_master` (linhas 48-53) devolve só `lixo`. A linha 91 dá
    `{"transacoes", "categorias", "contas"} - {"lixo"}` = as três, e a mensagem
    da linha 96 imprime `sorted(faltam)`, por ordem alfabética:

        ['categorias', 'contas', 'transacoes']

    A lista é o que torna o erro útil, e é o que este teste fixa.
    """
    semear_conta_real()
    conteudo = criar_sqlite(tmp_path / "lixo.db", {"lixo": "id INTEGER"})

    resposta = importar(client, conteudo)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == (
        "Estrutura inesperada. Faltam tabelas: "
        "['categorias', 'contas', 'transacoes']"
    )
    assert not existe(bd_em_ficheiro, ".tmp")
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]


def test_nome_sem_extensao_db_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um ficheiro válido com outro nome é recusado antes de ser lido.

    Cálculo à mão: a linha 64 é a primeira coisa que a função faz, e vem antes
    da leitura do conteúdo (linha 67). Nem chega a haver ficheiro no disco: o
    `.tmp` é criado só na linha 80, mais abaixo.

    Passa-se aqui um `.db` válido, para se ver que é o **nome** a ser recusado e
    não o conteúdo.
    """
    semear_conta_real()
    conteudo = criar_sqlite(tmp_path / "valido.db", MINIMO_3)

    resposta = importar(client, conteudo, nome="backup.txt")

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "Ficheiro inválido"
    assert not existe(bd_em_ficheiro, ".tmp")
    assert nomes_das_contas() == [CONTA_REAL]


def test_ficheiro_vazio_e_rejeitado(client, bd_em_ficheiro):
    """Um ficheiro de nome certo mas sem bytes é recusado.

    Cálculo à mão: a linha 64 passa (o nome acaba em `.db`), a leitura da linha
    67 devolve `b""`, e a linha 68 levanta o 400. Também antes de qualquer
    escrita: o `.tmp` só é criado na linha 80.
    """
    semear_conta_real()

    resposta = importar(client, b"")

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "Ficheiro vazio"
    assert not existe(bd_em_ficheiro, ".tmp")
    assert nomes_das_contas() == [CONTA_REAL]


def test_ficheiro_corrompido_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um `.db` com bytes estragados é recusado, e o dano não passa.

    O ficheiro de teste é um `.db` válido de 8 KiB, com 200 linhas em `contas`,
    ao qual se sobrepõem 64 bytes `0xff` a partir do deslocamento 4096 — uma
    página interior, fora do cabeçalho, para que o ficheiro continue a ser
    reconhecido como SQLite. A corrupção é determinística: não depende do que o
    SQLite escreva naquele sítio, e o mesmo teste produz o mesmo ficheiro em
    qualquer máquina.

    Pré-condição, dentro do próprio teste: abrir o ficheiro corrompido com o
    `sqlite3` e ver o que o `PRAGMA integrity_check` faz. Não é um adorno — o
    texto da resposta depende disso, e o comportamento do `integrity_check` já
    mudou entre versões do SQLite:

    * `("erro", ...)` — o `sqlite3` levanta `DatabaseError`. É o que acontece
      hoje, e o endpoint responde pela linha 55, com a mensagem que inclui a do
      `sqlite3`.
    * `("linha", ...)` — o `integrity_check` devolve uma linha que não é "ok".
      Então, e só então, a linha 46 é alcançada e a resposta é a outra:
      `Base de dados corrompida (integrity_check).`

    Se a pré-condição der "ok", o teste falha com uma mensagem que diz o que
    fazer, em vez de passar a vazio.
    """
    semear_conta_real()

    caminho = tmp_path / "limpo.db"
    criar_sqlite(caminho, {"contas": "id INTEGER PRIMARY KEY, nome TEXT"})
    con = sqlite3.connect(caminho)
    try:
        for numero in range(200):
            con.execute("INSERT INTO contas (nome) VALUES (?)", (f"linha {numero}",))
        con.commit()
    finally:
        con.close()

    assert integridade(caminho) == ("linha", "ok"), (
        f"O ficheiro de partida não está íntegro: {integridade(caminho)}"
    )

    with open(caminho, "r+b") as f:
        f.seek(4096)
        f.write(b"\xff" * 64)
    corrompido = tmp_path / "corrompido.db"
    corrompido.write_bytes(caminho.read_bytes())

    estado, detalhe = integridade(corrompido)
    assert (estado, detalhe) != ("linha", "ok"), (
        f"A corrupção não estragou o ficheiro: o integrity_check devolveu "
        f"({estado!r}, {detalhe!r}). Com esta versão do SQLite nenhum dos dois "
        "ramos da validação é alcançável; ver o docstring do módulo."
    )

    resposta = importar(client, corrompido.read_bytes())

    assert resposta.status_code == 400
    if estado == "erro":
        # Linha 55: o `sqlite3` levantou, e a mensagem repete o erro dele.
        assert resposta.json()["detail"].startswith(
            "O ficheiro não é uma base de dados SQLite válida"
        ), f"A validação mudou de ramo: integridade devolveu {detalhe!r}"
    else:
        # Linha 46: o `integrity_check` respondeu, e a linha não era "ok".
        assert resposta.json()["detail"] == (
            "Base de dados corrompida (integrity_check)."
        )
    assert not existe(bd_em_ficheiro, ".tmp")
    assert nomes_das_contas() == [CONTA_REAL]


def test_ida_e_volta_sem_alteracoes_preserva_os_dados(client, bd_em_ficheiro):
    """Exportar e reimportar o export, sem mexer em nada, não perde nada.

    Cálculo à mão: o `.db` exportado tem as 11 tabelas — é a BD da fixture, com o
    esquema inteiro —, logo `faltam` é vazio (linha 91) e o `os.replace` da
    linha 108 substitui o ficheiro por ele próprio, byte a byte. A `Conta Real`
    continua lá, com a mesma linha.

    O `.anterior` é criado na linha 104 e apagado na 130, pelo que no fim não há
    `.anterior`: se ficar, o restauro não se completou.
    """
    semear_conta_real()

    exportado = client.get("/api/backups/exportar")
    assert exportado.status_code == 200

    resposta = importar(client, exportado.content)

    assert resposta.status_code == 200
    assert resposta.json() == {
        "ok": True,
        "mensagem": "Base de dados restaurada",
    }
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]


def test_ida_e_volta_traz_de_volta_o_estado_anterior(client, bd_em_ficheiro):
    """O que se exportou manda sobre o que há depois de importar.

    Cálculo à mão: exporta-se a BD com uma conta, `Conta Real`. Depois cria-se
    `Conta Nova` e importa-se o export. A linha 108 substitui o ficheiro
    inteiro, pelo que `Conta Nova` deixa de existir: fica só a `Conta Real`.

    É este o teste que prova que o restauro substitui e não junta. O ciclo sem
    alterações, por si só, passaria mesmo que o endpoint não fizesse nada.
    """
    semear_conta_real()

    exportado = client.get("/api/backups/exportar")

    db = sessao_nova()
    try:
        db.add(Conta(nome="Conta Nova", saldo_referencia=50.0,
                     data_referencia=date(2024, 2, 1)))
        db.commit()
        assert len(db.query(Conta).all()) == 2
    finally:
        db.close()

    resposta = importar(client, exportado.content)

    assert resposta.status_code == 200
    assert resposta.json()["ok"] is True
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]


def test_tabelas_esperadas_existem_no_modelo():
    """Cada nome de `TABELAS_ESPERADAS` é mesmo o nome de uma tabela do modelo.

    Amarração de uma ponta: se alguém mudar o nome de uma tabela no
    `database.py`, a lista de `backups.py:13` passa a pedir uma tabela que não
    existe e a recusar ficheiros que estão bons. Isto apanha esse erro.

    A outra ponta — a lista ser completa — é o cenário 11.

    Não pede a BD: é uma comparação entre a constante do router e o modelo.
    """
    do_modelo = {tabela.name for tabela in Base.metadata.sorted_tables}

    assert TABELAS_ESPERADAS <= do_modelo, (
        f"TABELAS_ESPERADAS pede tabelas que o modelo não tem: "
        f"{sorted(TABELAS_ESPERADAS - do_modelo)}"
    )


# ---------------------------------------------------------------------------
# Comportamento questionável (D6)
# ---------------------------------------------------------------------------

def test_so_as_tres_tabelas_e_aceite_e_perde_o_resto(client, bd_em_ficheiro, tmp_path):
    # DEVIDA-TECNICA: D6
    """Um `.db` com as 3 tabelas e mais nada é aceite, e a BD perde o resto.

    Cálculo à mão: o ficheiro tem as 3 tabelas esperadas e nenhuma das outras
    oito, logo `faltam` é vazio (linha 91) e o `os.replace` da linha 108 corre. O
    que o endpoint devolve é um 200 de sucesso:

        {"ok": True, "mensagem": "Base de dados restaurada"}

    E o que se passa a seguir é o que este teste fixa, com duas leituras:

    * A tabela `contas` existe no ficheiro importado e vem vazia, logo a
      `Conta Real` **desaparece**: a leitura devolve uma lista vazia. A conta
      que estava na base de dados antes do pedido não está depois.
    * A tabela `ativos` não existe no ficheiro importado — era uma das oito que
      ninguém validou —, logo a consulta rebenta com
      `OperationalError: no such table: ativos`. É o erro que a aplicação
      encontraria no primeiro pedido que falhasse, com a BD já trocada e sem
      `.anterior` para recuar, porque a linha 130 já o apagou.

    Este é o teste que documenta o D6. Quando a lista passar a derivar de
    `Base.metadata.sorted_tables`, o endpoint tem de recusar este ficheiro com
    400 e este teste falha de propósito.
    """
    semear_conta_real()
    conteudo = criar_sqlite(tmp_path / "tres.db", MINIMO_3)

    resposta = importar(client, conteudo)

    assert resposta.status_code == 200
    assert resposta.json() == {
        "ok": True,
        "mensagem": "Base de dados restaurada",
    }
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == []

    db = sessao_nova()
    try:
        with pytest.raises(OperationalError, match="no such table: ativos"):
            db.query(Ativo).all()
    finally:
        db.close()


def test_tres_tabelas_com_colunas_erradas_e_aceite(client, bd_em_ficheiro, tmp_path):
    # DEVIDA-TECNICA: D6
    """Um `.db` com os 3 nomes certos e as colunas erradas também é aceite.

    Este é o `xfail(strict=True)` antigo, convertido em teste de
    caracterização: deixou de ser um "quando isto corrigir, apaga o xfail" e
    passou a afirmar o que o endpoint faz hoje.

    Cálculo à mão: o ficheiro tem as tabelas `transacoes`, `categorias` e
    `contas`, cada uma só com a coluna `id`. A validação da linha 91 só olha para
    **nomes**, e a verificação pós-troca da linha 113 é um `SELECT COUNT(*)`,
    que conta linhas sem tocar em colunas. Nada pelo caminho nota a falta das
    colunas, e o endpoint responde com 200 de sucesso.

    O que fica depois é uma base de dados que a aplicação não consegue ler:

    * `.anterior` não existe — foi apagado na linha 130, já depois de a
      verificação fraca dar tudo certo;
    * ler `contas` rebenta com `OperationalError: no such column: contas.nome`,
      que é o primeiro erro que um pedido real encontraria.

    O D6 fala dos nomes das tabelas; as colunas são a mesma validação pela outra
    face, e é por isso que o marcador é o mesmo.
    """
    semear_conta_real()
    conteudo = criar_sqlite(
        tmp_path / "colunas.db",
        {nome: "id INTEGER PRIMARY KEY" for nome in MINIMO_3},
    )

    resposta = importar(client, conteudo)

    assert resposta.status_code == 200
    assert resposta.json()["ok"] is True
    assert not existe(bd_em_ficheiro, ".anterior")

    db = sessao_nova()
    try:
        with pytest.raises(OperationalError, match="no such column: contas.nome"):
            db.query(Conta).all()
    finally:
        db.close()


def test_lista_esperada_e_menor_que_o_modelo():
    # DEVIDA-TECNICA: D6
    """A lista de tabelas esperadas é um subconjunto estrito das 11 do modelo.

    Cálculo à mão: o modelo tem 11 tabelas e `TABELAS_ESPERADAS` tem 3, logo
    faltam oito. A diferença, escrita à mão e por ordem alfabética:

        ativos, configuracao, movimentos_ativo, perfis_importacao, precos_ativo,
        regras_categorizacao, subcategorias, tipos_ativo

    São oito tabelas que o restauro não valida: um `.db` sem elas passa (é o
    cenário 9) e o `.anterior` é apagado na mesma. O D6 sugere derivar a lista
    de `Base.metadata.sorted_tables`, que é a fonte de verdade.

    Esta asserção falha de propósito quando isso acontecer, e nesse momento a
    lista de `backups.py:13` passa a ter 11 nomes em vez de 3.
    """
    do_modelo = {tabela.name for tabela in Base.metadata.sorted_tables}

    assert TABELAS_ESPERADAS < do_modelo, (
        "TABELAS_ESPERADAS já não é um subconjunto estrito do modelo. Se a "
        "correção do D6 foi feita, este teste e o cenário 9 têm de ser "
        "reescritos."
    )
    assert TABELAS_ESPERADAS == {"transacoes", "categorias", "contas"}
    assert do_modelo == TABELAS_DO_MODELO, (
        f"O modelo mudou, e não é o D6: {sorted(do_modelo ^ TABELAS_DO_MODELO)}. "
        "Actualiza TABELAS_DO_MODELO e o comentário deste teste."
    )
    assert sorted(do_modelo - TABELAS_ESPERADAS) == [
        "ativos",
        "configuracao",
        "movimentos_ativo",
        "perfis_importacao",
        "precos_ativo",
        "regras_categorizacao",
        "subcategorias",
        "tipos_ativo",
    ]

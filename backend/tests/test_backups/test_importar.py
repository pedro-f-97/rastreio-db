"""Testes de `POST /api/backups/importar`.

Portados do `test_backups.py` antigo (Pedro, 16 de Setembro, commit `398130b`),
com as fixtures novas desta sub-pasta, e depois invertidos pelo D6: os testes
que fixavam a validação fraca — só 3 tabelas, sem colunas, `.anterior` apagado
no fim — afirmam agora a correcção.

O endpoint, lido por ordem
--------------------------
`backend/routers/backups.py`, `importar_backup`:

1. o nome tem de acabar em `.db`; caso contrário, 400 `Ficheiro inválido`.
2. o conteúdo não pode ser vazio; caso contrário, 400 `Ficheiro vazio`.
3. os caminhos são `DB_PATH + ".tmp"` e `DB_PATH + ".anterior"`, ao lado da BD
   — que, por causa do `conftest`, está no directório temporário.
4. a limpeza inicial remove só o `.tmp`: um `.anterior` pré-existente fica no
   disco até um restauro que passe a validação o substituir.
5. o conteúdo vai para o `.tmp`, e só depois é validado, em dois passe:
   `_validar_sqlite` (PRAGMA integrity_check e leitura de `sqlite_master`,
   com as mensagens próprias de «não é SQLite» e «corrompida») e
   `_validar_estrutura` (tabelas e colunas contra
   `Base.metadata.sorted_tables`; qualquer falta → 400 com a mensagem
   genérica, sem dizer o que falta).
6. `engine.dispose()` fecha as ligações antes de mexer no ficheiro.
7. `shutil.copy2(DB_PATH, anterior_path)` cria ou substitui o `.anterior`.
8. `os.replace(temp_path, DB_PATH)` — a BD é mesmo substituída.
9. verificação pós-troca: `_validar_estrutura(DB_PATH)`, a MESMA validação de
   tabelas e colunas, agora sobre a BD trocada.
10. em erro no bloco 7-9, rollback: `dispose`, repõe a BD a partir do
    `.anterior` **sem o apagar**, e responde 500 `Falha ao restaurar: ...`.
11. no sucesso, o `.anterior` fica no disco até o restauro seguinte o
    substituir — o endpoint nunca o apaga.

Os testes
---------
Todos afirmam comportamento correcto. Onde antes estava fixado o defeito do
D6, o docstring guarda a história («era aceite com 200 …») para se perceber o
que mudou. Todos os valores esperados estão escritos à mão, como constantes,
com o raciocínio no comentário de cada teste: nenhum foi copiado de uma
execução.

Porquê uma sub-pasta
--------------------
Explicado no `conftest.py` desta pasta: o endpoint não usa `get_db` e trabalha
com a `engine` de ficheiro do módulo, pelo que a BD em memória do conftest pai
não chega.

Rollback por cobrir
-------------------
O caminho de erro que usa o `.anterior` a sério (o bloco `except Exception` de
`importar_backup`) continua por cobrir, e depois do D6 a razão ficou mais
estreita: a verificação pós-troca é a mesma `_validar_estrutura` e lê o mesmo
ficheiro que acabou de passar a validação prévia (o `os.replace` é atómico),
pelo que não pode falhar de forma natural. Forçá-la exigiria `monkeypatch` ao
nome privado `routers.backups._validar_estrutura`, o que acopla o teste ao
interior do router. A alternativa — sabotar o `os.replace` — só exercitaria o
ramo em que a BD nunca chega a ser substituída, e aí o `.tmp` fica para trás,
porque o rollback não o remove (D22, em `docs/divida-tecnica.md`).
"""

import sqlite3
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine

from database import Ativo, Base, Conta, SessionLocal, engine
from routers.backups import TABELAS_ESPERADAS


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

# Três das onze tabelas do modelo, cada uma só com as colunas mínimas. É o
# ficheiro mais magro que o endpoint já aceitou (o da validação antiga do D6)
# e continua a servir de entrada a vários cenários de rejeição.
MINIMO_3 = {
    "transacoes": "id INTEGER PRIMARY KEY, data TEXT, descricao TEXT, valor REAL",
    "categorias": "id INTEGER PRIMARY KEY, nome TEXT, tipo TEXT",
    "contas": "id INTEGER PRIMARY KEY, nome TEXT, saldo_referencia REAL, "
              "data_referencia TEXT, ativa INTEGER",
}

# As 11 tabelas do modelo (`Base.metadata.sorted_tables`), escritas à mão.
TABELAS_DO_MODELO = {
    "ativos", "categorias", "configuracao", "contas", "movimentos_ativo",
    "perfis_importacao", "precos_ativo", "regras_categorizacao", "subcategorias",
    "tipos_ativo", "transacoes",
}

# A frase única que o endpoint devolve a qualquer problema de estrutura (tabela
# em falta ou coluna em falta). Escrita à mão de propósito: se o router mudar o
# texto, este teste tem de ser actualizado por uma pessoa.
MENSAGEM_ESTRUTURA = (
    "O ficheiro não corresponde a um backup válido do Rastreio-DB"
)

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


def criar_bd_do_modelo(caminho: Path) -> bytes:
    """Cria um `.db` com as 11 tabelas e TODAS as colunas do modelo.

    O esquema é criado pelo próprio `Base.metadata.create_all`, e não escrito
    à mão: o ficheiro tem de bater certo com o modelo porque é o modelo que a
    validação usa como régua. O que os testes escrevem à mão são os valores
    esperados da resposta, não a forma do ficheiro de entrada.
    """
    if caminho.exists():
        caminho.unlink()
    motor = create_engine(f"sqlite:///{caminho}")
    try:
        Base.metadata.create_all(bind=motor)
    finally:
        motor.dispose()
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
    """Lê os nomes das contas pela BD em ficheiro, por ordem alfabética."""
    db = sessao_nova()
    try:
        return sorted(conta.nome for conta in db.query(Conta).all())
    finally:
        db.close()


def caminho_do(bd: Path, sufixo: str) -> Path:
    """O caminho com aquele sufixo ao lado da BD.

    O endpoint monta `DB_PATH + ".tmp"` e `DB_PATH + ".anterior"`, pelo que é
    aqui que se vai procurar o que ficou.
    """
    return Path(str(bd) + sufixo)


def existe(caminho_bd: Path, sufixo: str) -> bool:
    """Se existe o ficheiro que o endpoint usa com aquele sufixo."""
    return caminho_do(caminho_bd, sufixo).exists()


def contas_em(caminho: Path) -> list[str]:
    """Nomes das contas de um `.db` qualquer, lidos sem abrir em escrita.

    Usado sobre o `.anterior` para afirmar que ele guarda o estado anterior ao
    restauro. A leitura é `mode=ro`, como a própria validação do endpoint.
    """
    con = sqlite3.connect(Path(caminho).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return [
            linha[0]
            for linha in con.execute("SELECT nome FROM contas ORDER BY nome")
        ]
    finally:
        con.close()


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

    Cálculo à mão: o endpoint escreve o conteúdo no `.tmp` e chama
    `_validar_sqlite`. O `sqlite3.connect` não falha — abre lazy — e é o
    primeiro `execute`, o `PRAGMA integrity_check`, que levanta
    `DatabaseError`, apanhado e devolvido como 400. O ramo do
    `integrity_check` a dar «não ok» não é alcançado: para lá chegar, a
    consulta teria de devolver uma linha, e aqui devolve uma excepção.

    A BD fica intacta porque o `.tmp` é apagado antes de a excepção subir, e o
    `os.replace` nunca chega a correr. O `.anterior` também não é criado, e
    não havia nenhum pré-existente.
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


def test_sqlite_sem_as_tabelas_do_modelo_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um SQLite válido sem nenhuma tabela do modelo é recusado, sem detalhes.

    Cálculo à mão: o ficheiro tem só a tabela `lixo`, pelo que falham as onze
    tabelas de `TABELAS_DO_MODELO`. A validação de estrutura responde com o 400
    genérico e **não** lista o que falta — a lista
    `['categorias', 'contas', 'transacoes']` que este teste fixava antes do D6
    desapareceu de propósito.

    O `.tmp` é apagado antes do 400 subir, o `.anterior` não chega a ser
    criado e a BD fica como estava.
    """
    semear_conta_real()
    conteudo = criar_sqlite(tmp_path / "lixo.db", {"lixo": "id INTEGER"})

    resposta = importar(client, conteudo)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_ESTRUTURA
    assert not existe(bd_em_ficheiro, ".tmp")
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]


def test_nome_sem_extensao_db_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um ficheiro válido com outro nome é recusado antes de ser lido.

    Cálculo à mão: a comparação do nome é a primeira coisa que a função faz, e
    vem antes da leitura do conteúdo. Nem chega a haver ficheiro no disco: o
    `.tmp` é criado mais abaixo, depois de os dois testes de nome e de vazio.

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

    Cálculo à mão: o nome acaba em `.db`, a leitura devolve `b""`, e o vazio é
    recusado. Também antes de qualquer escrita: o `.tmp` só é criado depois.
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
    mudou entre versões de SQLite:

    * `("erro", ...)` — o `sqlite3` levanta `DatabaseError`. É o que acontece
      hoje, e o endpoint responde com a mensagem que inclui a do `sqlite3`.
    * `("linha", ...)` — o `integrity_check` devolve uma linha que não é "ok".
      Então, e só então, é alcançada a resposta outra:
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
        # O `sqlite3` levantou, e a mensagem repete o erro dele.
        assert resposta.json()["detail"].startswith(
            "O ficheiro não é uma base de dados SQLite válida"
        ), f"A validação mudou de ramo: integridade devolveu {detalhe!r}"
    else:
        # O `integrity_check` respondeu, e a linha não era "ok".
        assert resposta.json()["detail"] == (
            "Base de dados corrompida (integrity_check)."
        )
    assert not existe(bd_em_ficheiro, ".tmp")
    assert nomes_das_contas() == [CONTA_REAL]


def test_ida_e_volta_sem_alteracoes_preserva_os_dados(client, bd_em_ficheiro):
    """Exportar e reimportar o export, sem mexer em nada, não perde nada.

    Cálculo à mão: o `.db` exportado tem as 11 tabelas — é a BD da fixture, com
    o esquema inteiro —, logo a validação de tabelas e colunas passa e o
    `os.replace` substitui o ficheiro por ele próprio, byte a byte. A `Conta Real`
    continua lá, com a mesma linha.

    O `.anterior` é criado antes do swap e **fica**: depois do D6 nunca é
    apagado no ramo de sucesso. Aqui ele contém o estado imediatamente antes do
    restauro, que nesta ida-e-volta é o mesmo que o do fim — só a `Conta Real`.
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
    assert existe(bd_em_ficheiro, ".anterior")
    assert contas_em(caminho_do(bd_em_ficheiro, ".anterior")) == [CONTA_REAL]
    assert nomes_das_contas() == [CONTA_REAL]


def test_ida_e_volta_traz_de_volta_o_estado_anterior(client, bd_em_ficheiro):
    """O que se exportou manda sobre o que há depois de importar.

    Cálculo à mão: exporta-se a BD com uma conta, `Conta Real`. Depois cria-se
    `Conta Nova` e importa-se o export. O `os.replace` substitui o ficheiro
    inteiro, pelo que `Conta Nova` deixa de existir: fica só a `Conta Real`.

    É este o teste que prova que o restauro substitui e não junta. O ciclo sem
    alterações, por si só, passaria mesmo que o endpoint não fizesse nada.

    O `.anterior` fica com o estado imediatamente antes do restauro, ou seja,
    as duas contas. Por ordem alfabética, escrito à mão: `Conta Nova` antes de
    `Conta Real` (o `N` do segundo nome vem antes do `R` do primeiro).
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
    assert existe(bd_em_ficheiro, ".anterior")
    assert contas_em(caminho_do(bd_em_ficheiro, ".anterior")) == [
        "Conta Nova",
        "Conta Real",
    ]
    assert nomes_das_contas() == [CONTA_REAL]


def test_tabelas_esperadas_existem_no_modelo():
    """Cada nome de `TABELAS_ESPERADAS` é mesmo o nome de uma tabela do modelo.

    Amarração de uma ponta: se alguém voltar a fixar em `backups.py` um
    conjunto de nomes à mão, e esse conjunto pedir uma tabela que o modelo não
    tem, o restauro passa a recusar ficheiros bons. Isto apanha esse erro.

    A outra ponta — a lista ser completa — é
    `test_a_lista_validada_e_a_do_modelo`.

    Não pede a BD: é uma comparação entre a constante do router e o modelo.
    """
    do_modelo = {tabela.name for tabela in Base.metadata.sorted_tables}

    assert TABELAS_ESPERADAS <= do_modelo, (
        f"TABELAS_ESPERADAS pede tabelas que o modelo não tem: "
        f"{sorted(TABELAS_ESPERADAS - do_modelo)}"
    )


def test_a_lista_validada_e_a_do_modelo():
    """A lista de tabelas que o endpoint valida é exatamente a do modelo.

    Amarra a outra ponta do teste anterior: `TABELAS_ESPERADAS` deriva de
    `Base.metadata.sorted_tables` (D6), e esta asserção falha se alguém voltar
    a escrever o conjunto à mão com menos nomes — que foi exactamente o defeito
    original: 3 nomes fixos em vez das 11 tabelas do modelo.

    As 11 tabelas, escritas à mão e por ordem alfabética, são
    `TABELAS_DO_MODELO`; a comparação com o modelo está logo abaixo, e a
    diferença que o teste antigo fixava (`transacoes`, `categorias` e `contas`
    só) passaria a ter oito nomes a menos.
    """
    do_modelo = {tabela.name for tabela in Base.metadata.sorted_tables}

    assert do_modelo == TABELAS_DO_MODELO, (
        f"O modelo mudou e não é o D6: {sorted(do_modelo ^ TABELAS_DO_MODELO)}. "
        "Actualiza TABELAS_DO_MODELO e o comentário deste teste."
    )
    assert TABELAS_ESPERADAS == do_modelo, (
        "TABELAS_ESPERADAS já não coincide com Base.metadata.sorted_tables: "
        f"falta {sorted(do_modelo - TABELAS_ESPERADAS)}, "
        f"sobra {sorted(TABELAS_ESPERADAS - do_modelo)}. "
        "Se a lista voltou a ser fixada à mão, o D6 regressou."
    )


# ---------------------------------------------------------------------------
# Regressões do D6
# ---------------------------------------------------------------------------

def test_so_as_tres_tabelas_e_rejeitado_e_a_bd_fica_intacta(client, bd_em_ficheiro, tmp_path):
    """Um `.db` com as 3 tabelas e mais nada é recusado; a BD fica como estava.

    Histórico (D6): era aceite com `200 {"ok": True, "mensagem": "Base de dados
    restaurada"}`, a BD perdia as outras oito tabelas e o `.anterior` era
    apagado no fim, sem recuperação possível.

    Cálculo à mão: o ficheiro tem `transacoes`, `categorias` e `contas`, e
    faltam as outras oito de `TABELAS_DO_MODELO` — escritas à mão, por ordem
    alfabética: ativos, configuracao, movimentos_ativo, perfis_importacao,
    precos_ativo, regras_categorizacao, subcategorias, tipos_ativo. A validação
    responde 400 com a mensagem genérica, o `.tmp` é apagado e o `.anterior`
    não chega a ser criado.

    A BD fica como estava, e lê-se pelas duas pontas: a `Conta Real` continua
    lá, e a tabela `ativos` existe e vem vazia (era uma das oito que ninguém
    validava).
    """
    semear_conta_real()
    conteudo = criar_sqlite(tmp_path / "tres.db", MINIMO_3)

    resposta = importar(client, conteudo)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_ESTRUTURA
    assert not existe(bd_em_ficheiro, ".tmp")
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]

    db = sessao_nova()
    try:
        assert db.query(Ativo).all() == []
    finally:
        db.close()


def test_tres_tabelas_com_colunas_erradas_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um `.db` com os 3 nomes certos e as colunas erradas também é recusado.

    Histórico (D6): era o `xfail(strict=True)` antigo, depois teste de
    caracterização — aceite com 200, deixava uma BD ilegível e o `.anterior`
    apagado.

    Cálculo à mão: o ficheiro tem as tabelas `transacoes`, `categorias` e
    `contas`, cada uma só com a coluna `id`. A validação de estrutura responde
    400 com a mensagem genérica. Repare-se que, com este ficheiro, a recusa já
    vem das oito tabelas em falta — como **teste de colunas em concreto** ele
    não prova nada, e é por isso que existe
    `test_coluna_em_falta_numa_so_tabela_e_rejeitado`, que tem as 11 tabelas e
    só uma coluna a menos.

    A BD fica como estava: a `Conta Real` lê-se, e o saldo continua a ser os
    100.0 com que foi semeada.
    """
    semear_conta_real()
    conteudo = criar_sqlite(
        tmp_path / "colunas.db",
        {nome: "id INTEGER PRIMARY KEY" for nome in MINIMO_3},
    )

    resposta = importar(client, conteudo)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_ESTRUTURA
    assert not existe(bd_em_ficheiro, ".tmp")
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]

    db = sessao_nova()
    try:
        assert db.query(Conta).one().saldo_referencia == 100.0
    finally:
        db.close()


def test_rejeicao_nao_toca_no_anterior_pre_existente(client, bd_em_ficheiro, tmp_path):
    """Uma importação rejeitada não altera nem apaga o `.anterior` que lá está.

    Cálculo à mão: o primeiro pedido é um restauro bom (exportar → importar),
    que deixa no `.anterior` o estado anterior àquele restauro — aqui, só a
    `Conta Real`. Guardam-se os bytes. O segundo pedido é um `.db` com as 3
    tabelas, rejeitado com 400: a limpeza inicial tira do caminho só o `.tmp`,
    e a cópia do `.anterior` está depois da validação, pelo que nenhum dos
    caminhos de rejeição chega a tocar naquele ficheiro. Os bytes têm de ser
    os mesmos.
    """
    semear_conta_real()

    exportado = client.get("/api/backups/exportar")
    assert exportado.status_code == 200
    primeiro = importar(client, exportado.content)
    assert primeiro.status_code == 200

    anterior = caminho_do(bd_em_ficheiro, ".anterior")
    assert anterior.exists(), "O restauro bom devia ter criado o `.anterior`."
    bytes_antes = anterior.read_bytes()

    conteudo = criar_sqlite(tmp_path / "tres.db", MINIMO_3)
    resposta = importar(client, conteudo)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_ESTRUTURA
    assert anterior.exists(), "A rejeição apagou o `.anterior` pré-existente."
    assert anterior.read_bytes() == bytes_antes, (
        "A rejeição alterou o conteúdo do `.anterior` pré-existente."
    )
    assert nomes_das_contas() == [CONTA_REAL]


def test_modelo_completo_com_coluna_extra_e_aceite(client, bd_em_ficheiro, tmp_path):
    """As 11 tabelas do modelo com uma coluna extra são aceites.

    Cálculo à mão: o ficheiro tem as 11 tabelas do modelo com todas as colunas
    — criadas pelo próprio `Base.metadata` — mais `contas.coluna_extra`, que
    ninguém pediu. Colunas (e tabelas) a mais são aceites: só as em falta
    contam. A validação passa, o `os.replace` troca a BD, e:

    * a BD passa a ser a do ficheiro, cuja única conta é a `Conta Extra`;
    * o `.anterior` guarda o estado anterior ao restauro, a `Conta Real`.
    """
    semear_conta_real()
    caminho = tmp_path / "completo.db"
    criar_bd_do_modelo(caminho)

    con = sqlite3.connect(caminho)
    try:
        con.execute("ALTER TABLE contas ADD COLUMN coluna_extra TEXT")
        con.execute(
            "INSERT INTO contas (nome, saldo_referencia, data_referencia, ativa) "
            "VALUES ('Conta Extra', 1.0, '2024-03-01', 1)"
        )
        con.commit()
    finally:
        con.close()

    resposta = importar(client, caminho.read_bytes())

    assert resposta.status_code == 200
    assert resposta.json() == {
        "ok": True,
        "mensagem": "Base de dados restaurada",
    }
    assert existe(bd_em_ficheiro, ".anterior")
    assert contas_em(caminho_do(bd_em_ficheiro, ".anterior")) == [CONTA_REAL]
    assert nomes_das_contas() == ["Conta Extra"]


def test_coluna_em_falta_numa_so_tabela_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um `.db` completo com UMA coluna em falta numa só tabela é recusado.

    Cálculo à mão: o ficheiro tem as 11 tabelas com todas as colunas do modelo,
    à excepção de `transacoes.valor` (`database.py`, coluna `valor` da
    `Transacao`), removida com `ALTER TABLE transacoes DROP COLUMN valor`. As
    onze tabelas estão presentes, portanto só a comparação de colunas pode
    apanhar a falta — é este o teste que prova que as colunas são mesmo
    validadas (o das colunas erradas tem 8 tabelas a menos e seria recusado de
    qualquer modo).

    A recusa é 400 com a mensagem genérica, sem dizer a tabela nem a coluna, e
    a BD fica como estava.
    """
    semear_conta_real()
    caminho = tmp_path / "sem_valor.db"
    criar_bd_do_modelo(caminho)

    con = sqlite3.connect(caminho)
    try:
        con.execute("ALTER TABLE transacoes DROP COLUMN valor")
        con.commit()
    finally:
        con.close()

    resposta = importar(client, caminho.read_bytes())

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_ESTRUTURA
    assert not existe(bd_em_ficheiro, ".tmp")
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]


def test_ficheiro_sem_uma_tabela_do_modelo_e_sempre_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Falta de QUALQUER tabela do modelo é recusada — tabela a tabela.

    Cálculo à mão: `TABELAS_DO_MODELO` tem 11 tabelas. Para cada uma, copia-se
    o `.db` completo e apaga-se **só** essa tabela (`DROP TABLE`; o `sqlite3`
    dos testes não impõe chaves estrangeiras, pelo que o `DROP` corre), pelo
    que as outras dez continuam presentes. Os onze pedidos têm de dar 400 com
    a mesma mensagem genérica — mesmo para as três tabelas que a validação
    antiga conhecia.

    Um teste só com uma tabela a menos apanharia apenas o mutante que ignora
    essa tabela; correr as onze cobre qualquer uma delas. No fim, a BD tem de
    continuar com a `Conta Real` e sem restos em disco.
    """
    semear_conta_real()
    completo = criar_bd_do_modelo(tmp_path / "completo.db")

    for nome in sorted(TABELAS_DO_MODELO):
        caminho = tmp_path / f"sem_{nome}.db"
        caminho.write_bytes(completo)
        con = sqlite3.connect(caminho)
        try:
            con.execute(f"DROP TABLE {nome}")
            con.commit()
        finally:
            con.close()

        resposta = importar(client, caminho.read_bytes())

        assert resposta.status_code == 400, (
            f"Um `.db` sem a tabela {nome!r} foi aceite com "
            f"{resposta.status_code}: {resposta.text}"
        )
        assert resposta.json()["detail"] == MENSAGEM_ESTRUTURA

    assert not existe(bd_em_ficheiro, ".tmp")
    assert not existe(bd_em_ficheiro, ".anterior")
    assert nomes_das_contas() == [CONTA_REAL]

"""Testes de `POST /api/backups/importar`.

Portados do `test_backups.py` antigo (16 de Setembro, commit `398130b`),
com as fixtures novas desta sub-pasta, e depois invertidos pela correcção: os testes
que fixavam a validação fraca — só 3 tabelas, sem colunas, `.anterior` apagado
no fim — afirmam agora a correcção.

O endpoint, lido por ordem
--------------------------
`backend/routers/backups.py`, `importar_backup`:

1. o nome tem de acabar em `.db`; caso contrário, 400 `Ficheiro inválido`.
2. o conteúdo não pode ser vazio; caso contrário, 400 `Ficheiro vazio`.
3. o temporário é `DB_PATH + ".tmp"`, ao lado da BD — que, por causa do
   `conftest`, está no directório temporário.
4. a limpeza inicial remove só o `.tmp`: as cópias `.anterior-<data>` que já
   existam ficam no disco.
5. o conteúdo vai para o `.tmp`, e só depois é validado:
   `_validar_sqlite` (PRAGMA integrity_check e leitura de `sqlite_master`,
   com as mensagens próprias de «não é SQLite» e «corrompida»), depois
   `aplicar_migracoes` no `.tmp` (uma falha → 500 `Falha ao restaurar: ...`,
   sem tocar na BD), e por fim `_validar_estrutura` (`colunas_em_falta`, as
   tabelas e colunas de `Base.metadata.sorted_tables`; qualquer falta → 400
   com a mensagem genérica, sem dizer o que falta).
6. `engine.dispose()` fecha as ligações antes de mexer no ficheiro.
7. `shutil.copy2(DB_PATH, anterior_tmp)` seguido de
   `os.replace(anterior_tmp, anterior_path)` cria uma cópia nova,
   `DB_PATH + ".anterior-AAAA-MM-DD-HHMMSS"` (com `-2`, `-3` no mesmo
   segundo), só quando a cópia está completa.
8. `os.replace(temp_path, DB_PATH)` — a BD é mesmo substituída.
9. verificação pós-troca: `_validar_estrutura(DB_PATH)`, a MESMA validação de
   tabelas e colunas, agora sobre a BD trocada.
10. em erro no bloco 7-9, rollback: `dispose`, repõe a BD a partir da cópia
    **sem a apagar** — mas só se essa cópia foi criada neste pedido, e também
    por cópia ao lado seguida de `os.replace` —, remove o `.tmp` e o
    `.tmp` da cópia que tenham ficado, e responde 500
    `Falha ao restaurar: ...`.
11. no sucesso, a cópia fica no disco, e das cópias `.anterior-<data>` ficam
    só as 5 mais recentes (achado 6.3); a `.anterior` sem data, de versões
    anteriores, nunca é apagada.

Os testes
---------
Todos afirmam comportamento correcto. Onde antes estava fixado o defeito da
validação, o docstring guarda a história («era aceite com 200 …») para se perceber o
que mudou. Todos os valores esperados estão escritos à mão, como constantes,
com o raciocínio no comentário de cada teste: nenhum foi copiado de uma
execução.

Porquê uma sub-pasta
--------------------
Explicado no `conftest.py` desta pasta: o endpoint não usa `get_db` e trabalha
com a `engine` de ficheiro do módulo, pelo que a BD em memória do conftest pai
não chega.

Rollback
--------
O bloco `except Exception` de `importar_backup` não falha de forma natural: a
verificação pós-troca é a mesma `_validar_estrutura` que o ficheiro acabou de
passar. Por isso os testes da cópia do `.anterior`, no fim deste ficheiro, provocam as falhas
com `monkeypatch`: na cópia do `.anterior` (`shutil.copy2`), na troca
(`os.replace`), na verificação pós-troca (`_validar_estrutura`, um nome
privado do router — o acoplamento é o preço de cobrir o rollback a sério) e na
reposição feita pelo próprio rollback.
"""

import os
import re
import shutil
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine

import database
from database import Ativo, Base, Conta, SessionLocal, colunas_em_falta, engine
from routers import backups

# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

# Três das onze tabelas do modelo, cada uma só com as colunas mínimas. É o
# ficheiro mais magro que o endpoint já aceitou (o da validação antiga)
# e continua a servir de entrada a vários cenários de rejeição.
MINIMO_3 = {
    "transacoes": "id INTEGER PRIMARY KEY, data TEXT, descricao TEXT, valor REAL",
    "categorias": "id INTEGER PRIMARY KEY, nome TEXT, tipo TEXT",
    "contas": "id INTEGER PRIMARY KEY, nome TEXT, saldo_referencia REAL, "
    "data_referencia TEXT, ativa INTEGER",
}

# As 11 tabelas do modelo (`Base.metadata.sorted_tables`), escritas à mão.
TABELAS_DO_MODELO = {
    "ativos",
    "categorias",
    "configuracao",
    "contas",
    "movimentos_ativo",
    "perfis_importacao",
    "precos_ativo",
    "regras_categorizacao",
    "subcategorias",
    "tipos_ativo",
    "transacoes",
}

# As frases que o endpoint devolve a um problema de estrutura (tabela ou coluna
# em falta). Escritas à mão de propósito: se o router mudar o texto, estes
# testes têm de ser actualizados por uma pessoa. A genérica é para um ficheiro
# a que falta `transacoes`, `categorias` ou `contas`; a de versão anterior,
# para um que tem as três e lhe falta outra coisa (achado 6.1).
MENSAGEM_ESTRUTURA = "O ficheiro não corresponde a um backup válido do Rastreio-DB"
MENSAGEM_VERSAO_ANTERIOR = (
    "Este backup é de uma versão anterior do Rastreio-DB e já não pode ser "
    "actualizado para esta versão. A base de dados actual não foi alterada."
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
        db.add(Conta(nome=CONTA_REAL, saldo_referencia=100.0, data_referencia=date(2024, 1, 1)))
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

    O endpoint monta `DB_PATH + ".tmp"`, pelo que é aqui que se vai procurar o
    que ficou. As cópias `.anterior-<data>` procuram-se com `anteriores`.
    """
    return Path(str(bd) + sufixo)


def existe(caminho_bd: Path, sufixo: str) -> bool:
    """Se existe o ficheiro que o endpoint usa com aquele sufixo."""
    return caminho_do(caminho_bd, sufixo).exists()


def anteriores(bd: Path) -> list[Path]:
    """As cópias `.anterior-<data>` terminadas, da mais antiga para a mais recente.

    O nome tem a data e a hora (`rastreio.db.anterior-AAAA-MM-DD-HHMMSS`, com
    `-2`, `-3` se houver mais de um restauro no mesmo segundo), por isso a ordem
    dos nomes é a ordem dos restauros.
    """
    return sorted(c for c in bd.parent.glob(bd.name + ".anterior-*") if c.suffix != ".tmp")


def ultimo_anterior(bd: Path) -> Path:
    """A cópia do restauro mais recente."""
    copias = anteriores(bd)
    assert copias, "Não há nenhuma cópia `.anterior-<data>`."
    return copias[-1]


def anteriores_tmp(bd: Path) -> list[Path]:
    """As cópias a meio (`.anterior-<data>.tmp`) que tenham ficado no disco."""
    return list(bd.parent.glob(bd.name + ".anterior-*.tmp"))


def contas_em(caminho: Path) -> list[str]:
    """Nomes das contas de um `.db` qualquer, lidos sem abrir em escrita.

    Usado sobre o `.anterior` para afirmar que ele guarda o estado anterior ao
    restauro. A leitura é `mode=ro`, como a própria validação do endpoint.
    """
    con = sqlite3.connect(Path(caminho).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return [linha[0] for linha in con.execute("SELECT nome FROM contas ORDER BY nome")]
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
    assert resposta.json()["detail"].startswith("O ficheiro não é uma base de dados SQLite válida")
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores(bd_em_ficheiro) == []
    assert nomes_das_contas() == [CONTA_REAL]


def test_sqlite_sem_as_tabelas_do_modelo_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um SQLite válido sem nenhuma tabela do modelo é recusado, sem detalhes.

    Cálculo à mão: o ficheiro tem só a tabela `lixo`, pelo que falham as onze
    tabelas de `TABELAS_DO_MODELO`. A validação de estrutura responde com o 400
    genérico e **não** lista o que falta — a lista
    `['categorias', 'contas', 'transacoes']` que este teste fixava antes da correcção
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
    assert anteriores(bd_em_ficheiro) == []
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
        assert resposta.json()["detail"] == ("Base de dados corrompida (integrity_check).")
    assert not existe(bd_em_ficheiro, ".tmp")
    assert nomes_das_contas() == [CONTA_REAL]


def test_ida_e_volta_sem_alteracoes_preserva_os_dados(client, bd_em_ficheiro):
    """Exportar e reimportar o export, sem mexer em nada, não perde nada.

    Cálculo à mão: o `.db` exportado tem as 11 tabelas — é a BD da fixture, com
    o esquema inteiro —, logo a validação de tabelas e colunas passa e o
    `os.replace` substitui o ficheiro por ele próprio, byte a byte. A `Conta Real`
    continua lá, com a mesma linha.

    O `.anterior` é criado antes do swap e **fica**: nunca é
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
    assert len(anteriores(bd_em_ficheiro)) == 1
    assert contas_em(ultimo_anterior(bd_em_ficheiro)) == [CONTA_REAL]
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
        db.add(Conta(nome="Conta Nova", saldo_referencia=50.0, data_referencia=date(2024, 2, 1)))
        db.commit()
        assert len(db.query(Conta).all()) == 2
    finally:
        db.close()

    resposta = importar(client, exportado.content)

    assert resposta.status_code == 200
    assert resposta.json()["ok"] is True
    assert len(anteriores(bd_em_ficheiro)) == 1
    assert contas_em(ultimo_anterior(bd_em_ficheiro)) == [
        "Conta Nova",
        "Conta Real",
    ]
    assert nomes_das_contas() == [CONTA_REAL]


def test_a_lista_validada_e_a_do_modelo(tmp_path):
    """A lista de tabelas que o endpoint valida é exatamente a do modelo.

    `colunas_em_falta` percorre `Base.metadata.sorted_tables`, e esta asserção
    falha se alguém voltar a escrever o conjunto à mão com menos nomes — que
    foi exactamente o defeito original: 3 nomes fixos em vez das 11 tabelas do
    modelo. Num ficheiro SQLite sem tabelas, faltam as 11, e só elas.

    As 11 tabelas, escritas à mão e por ordem alfabética, são
    `TABELAS_DO_MODELO`; a comparação com o modelo está logo abaixo, e a
    diferença que o teste antigo fixava (`transacoes`, `categorias` e `contas`
    só) passaria a ter oito nomes a menos.
    """
    do_modelo = {tabela.name for tabela in Base.metadata.sorted_tables}

    assert do_modelo == TABELAS_DO_MODELO, (
        f"O modelo mudou: {sorted(do_modelo ^ TABELAS_DO_MODELO)}. "
        "Actualiza TABELAS_DO_MODELO e o comentário deste teste."
    )
    vazia = tmp_path / "vazia.db"
    sqlite3.connect(vazia).close()
    assert set(colunas_em_falta(str(vazia))) == TABELAS_DO_MODELO


# ---------------------------------------------------------------------------
# Regressões da validação
# ---------------------------------------------------------------------------


def test_so_as_tres_tabelas_e_rejeitado_e_a_bd_fica_intacta(client, bd_em_ficheiro, tmp_path):
    """Um `.db` com as 3 tabelas e mais nada é recusado; a BD fica como estava.

    Histórico: era aceite com `200 {"ok": True, "mensagem": "Base de dados
    restaurada"}`, a BD perdia as outras oito tabelas e o `.anterior` era
    apagado no fim, sem recuperação possível.

    Cálculo à mão: o ficheiro tem `transacoes`, `categorias` e `contas`, e
    faltam as outras oito de `TABELAS_DO_MODELO` — escritas à mão, por ordem
    alfabética: ativos, configuracao, movimentos_ativo, perfis_importacao,
    precos_ativo, regras_categorizacao, subcategorias, tipos_ativo. Como as três
    tabelas de sempre estão lá, as oito são criadas vazias no temporário (6.4),
    mas as três têm colunas a menos (`MINIMO_3`): a validação responde 400 com a
    mensagem de versão anterior, o `.tmp` é apagado e o `.anterior` não chega a
    ser criado.

    A BD fica como estava, e lê-se pelas duas pontas: a `Conta Real` continua
    lá, e a tabela `ativos` existe e vem vazia (era uma das oito que ninguém
    validava).
    """
    semear_conta_real()
    conteudo = criar_sqlite(tmp_path / "tres.db", MINIMO_3)

    resposta = importar(client, conteudo)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_VERSAO_ANTERIOR
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores(bd_em_ficheiro) == []
    assert nomes_das_contas() == [CONTA_REAL]

    db = sessao_nova()
    try:
        assert db.query(Ativo).all() == []
    finally:
        db.close()


def test_tres_tabelas_com_colunas_erradas_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um `.db` com os 3 nomes certos e as colunas erradas também é recusado.

    Histórico: era o `xfail(strict=True)` antigo, depois teste de
    caracterização — aceite com 200, deixava uma BD ilegível e o `.anterior`
    apagado.

    Cálculo à mão: o ficheiro tem as tabelas `transacoes`, `categorias` e
    `contas`, cada uma só com a coluna `id`. As três tabelas de sempre estão lá,
    pelo que a validação de estrutura responde 400 com a mensagem de versão
    anterior. As oito tabelas em falta são criadas no temporário (6.4), por isso
    a recusa vem mesmo das colunas; ainda assim, o teste de uma só coluna em
    falta é
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
    assert resposta.json()["detail"] == MENSAGEM_VERSAO_ANTERIOR
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores(bd_em_ficheiro) == []
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
    tabelas, rejeitado com 400 (mensagem de versão anterior, porque tem as três
    tabelas de sempre): a limpeza inicial tira do caminho só o `.tmp`,
    e a cópia do `.anterior` está depois da validação, pelo que nenhum dos
    caminhos de rejeição chega a tocar naquele ficheiro. Os bytes têm de ser
    os mesmos.
    """
    semear_conta_real()

    exportado = client.get("/api/backups/exportar")
    assert exportado.status_code == 200
    primeiro = importar(client, exportado.content)
    assert primeiro.status_code == 200

    anterior = ultimo_anterior(bd_em_ficheiro)
    bytes_antes = anterior.read_bytes()

    conteudo = criar_sqlite(tmp_path / "tres.db", MINIMO_3)
    resposta = importar(client, conteudo)

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == MENSAGEM_VERSAO_ANTERIOR
    assert anteriores(bd_em_ficheiro) == [anterior], (
        "A rejeição apagou o `.anterior` pré-existente ou criou outro."
    )
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
    assert len(anteriores(bd_em_ficheiro)) == 1
    assert contas_em(ultimo_anterior(bd_em_ficheiro)) == [CONTA_REAL]
    assert nomes_das_contas() == ["Conta Extra"]


def test_backup_antigo_com_reembolso_e_aceite_e_perde_a_coluna(client, bd_em_ficheiro, tmp_path):
    """Um backup de antes do 4.3, com `transacoes.reembolso`, é restaurado sem ela.

    Cálculo à mão: o ficheiro tem o modelo completo mais a coluna antiga (uma
    coluna a mais é aceite pela validação). Depois da troca,
    `remover_coluna_reembolso` apaga-a: a BD restaurada não tem a coluna e
    guarda a única transacção do backup.
    """
    caminho = tmp_path / "antigo.db"
    criar_bd_do_modelo(caminho)
    con = sqlite3.connect(caminho)
    try:
        con.execute("ALTER TABLE transacoes ADD COLUMN reembolso BOOLEAN NOT NULL DEFAULT 0")
        con.execute(
            "INSERT INTO transacoes (data, descricao, valor, reembolso) "
            "VALUES ('2025-03-18', 'Reembolso seguros', 50.0, 1)"
        )
        con.commit()
    finally:
        con.close()

    resposta = importar(client, caminho.read_bytes())

    assert resposta.status_code == 200
    con = sqlite3.connect(bd_em_ficheiro)
    try:
        nomes = [linha[1] for linha in con.execute("PRAGMA table_info(transacoes)")]
        transacoes = con.execute("SELECT descricao, valor FROM transacoes").fetchall()
    finally:
        con.close()
    assert "reembolso" not in nomes
    assert transacoes == [("Reembolso seguros", 50.0)]


def test_coluna_em_falta_numa_so_tabela_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um `.db` completo com UMA coluna em falta numa só tabela é recusado.

    Cálculo à mão: o ficheiro tem as 11 tabelas com todas as colunas do modelo,
    à excepção de `transacoes.valor` (`database.py`, coluna `valor` da
    `Transacao`), removida com `ALTER TABLE transacoes DROP COLUMN valor`. As
    onze tabelas estão presentes, portanto só a comparação de colunas pode
    apanhar a falta — é este o teste que prova que as colunas são mesmo
    validadas (o das colunas erradas tem 8 tabelas a menos e seria recusado de
    qualquer modo).

    É o caso de um backup de uma versão anterior: a recusa é 400 com a mensagem
    de versão anterior, sem dizer a tabela nem a coluna, e a BD fica como
    estava.
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
    assert resposta.json()["detail"] == MENSAGEM_VERSAO_ANTERIOR
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores(bd_em_ficheiro) == []
    assert nomes_das_contas() == [CONTA_REAL]


def _completo_sem(tmp_path: Path, completo: bytes, nome: str) -> bytes:
    """O `.db` completo sem a tabela `nome` (`DROP TABLE`; o `sqlite3` dos
    testes não impõe chaves estrangeiras, pelo que o `DROP` corre)."""
    caminho = tmp_path / f"sem_{nome}.db"
    caminho.write_bytes(completo)
    con = sqlite3.connect(caminho)
    try:
        con.execute(f"DROP TABLE {nome}")
        con.commit()
    finally:
        con.close()
    return caminho.read_bytes()


TABELAS_DE_SEMPRE = ("categorias", "contas", "transacoes")


def test_ficheiro_sem_uma_das_tres_tabelas_de_sempre_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Sem `transacoes`, `categorias` ou `contas`, o ficheiro é recusado.

    Cálculo à mão: para cada uma das três, copia-se o `.db` completo e apaga-se
    só essa tabela; as outras dez continuam. Sem uma das três de sempre, o
    ficheiro não parece um backup do Rastreio-DB: as tabelas em falta não são
    criadas (6.4) e a resposta é 400 com a mensagem genérica (6.1). Duas das
    três não chegam. No fim, a BD continua com a `Conta Real`, sem restos.
    """
    semear_conta_real()
    completo = criar_bd_do_modelo(tmp_path / "completo.db")

    for nome in TABELAS_DE_SEMPRE:
        resposta = importar(client, _completo_sem(tmp_path, completo, nome))

        assert (resposta.status_code, resposta.json()["detail"]) == (400, MENSAGEM_ESTRUTURA), nome

    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores(bd_em_ficheiro) == []
    assert nomes_das_contas() == [CONTA_REAL]


def test_backup_sem_uma_tabela_nova_e_aceite_com_ela_vazia(client, bd_em_ficheiro, tmp_path):
    """A um backup que só não tem uma das outras oito tabelas, ela é criada vazia.

    É o caso do achado 6.4: uma tabela nova não tem migração, e o restauro faz
    o que o arranque faz, cria-a vazia. Para cada uma das oito, copia-se o
    `.db` completo, com a conta «Conta do backup», e apaga-se só essa tabela.

    Cálculo à mão, por restauro: 200; a BD passa a ser o backup (a única conta
    é «Conta do backup»); a tabela apagada existe outra vez e está vazia; e não
    falta nenhuma tabela nem coluna. São 8 restauros bons, cada um com a sua
    cópia `.anterior-<data>`, e ficam as 5 mais recentes (6.3).
    """
    semear_conta_real()
    caminho_completo = tmp_path / "completo.db"
    criar_bd_do_modelo(caminho_completo)
    con = sqlite3.connect(caminho_completo)
    try:
        con.execute(
            "INSERT INTO contas (nome, saldo_referencia, data_referencia, ativa) "
            "VALUES ('Conta do backup', 1.0, '2024-03-01', 1)"
        )
        con.commit()
    finally:
        con.close()
    completo = caminho_completo.read_bytes()

    outras = sorted(TABELAS_DO_MODELO - set(TABELAS_DE_SEMPRE))
    assert len(outras) == 8
    for nome in outras:
        resposta = importar(client, _completo_sem(tmp_path, completo, nome))

        assert resposta.status_code == 200, (nome, resposta.text)
        assert nomes_das_contas() == ["Conta do backup"], nome
        con = sqlite3.connect(bd_em_ficheiro)
        try:
            assert con.execute(f"SELECT count(*) FROM {nome}").fetchone() == (0,), nome
        finally:
            con.close()
        assert colunas_em_falta(str(bd_em_ficheiro)) == [], nome

    assert len(anteriores(bd_em_ficheiro)) == 5
    assert not existe(bd_em_ficheiro, ".tmp")


# ---------------------------------------------------------------------------
# Valores inválidos (achado 6.2)
# ---------------------------------------------------------------------------

MENSAGEM_VALORES = (
    "O backup tem valores inválidos e não pode ser restaurado. "
    "A base de dados actual não foi alterada."
)


def _completo_com(tmp_path: Path, *sql: str) -> bytes:
    """O `.db` completo do modelo, com as instruções `sql` corridas sem chaves
    estrangeiras (o `sqlite3` não as impõe por omissão)."""
    caminho = tmp_path / "com_valores.db"
    criar_bd_do_modelo(caminho)
    con = sqlite3.connect(caminho)
    try:
        for instrucao in sql:
            con.execute(instrucao)
        con.commit()
    finally:
        con.close()
    return caminho.read_bytes()


def test_backup_com_tipo_de_categoria_desconhecido_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Um tipo de categoria que a enumeração não tem («poupanca») é recusado.

    Cálculo à mão: `TipoCategoria` tem despesa, receita, investimento e
    transferencia; "poupanca" não é nenhum. Antes da correcção, o restauro dava
    200 e as páginas das categorias, transações e estatísticas davam 500.
    Agora: 400, a BD fica com a `Conta Real` e não há cópias novas.
    """
    semear_conta_real()
    conteudo = _completo_com(
        tmp_path, "INSERT INTO categorias (nome, tipo) VALUES ('Mealheiro', 'poupanca')"
    )

    resposta = importar(client, conteudo)

    assert (resposta.status_code, resposta.json()["detail"]) == (400, MENSAGEM_VALORES)
    assert nomes_das_contas() == [CONTA_REAL]
    assert anteriores(bd_em_ficheiro) == []
    assert not existe(bd_em_ficheiro, ".tmp")


def test_backup_com_chave_estrangeira_partida_e_rejeitado(client, bd_em_ficheiro, tmp_path):
    """Uma transacção que aponta para uma categoria que não existe é recusada.

    Cálculo à mão: a única transacção tem `categoria_id = 999`, e a tabela de
    categorias está vazia -> uma linha no `PRAGMA foreign_key_check` -> 400, e a
    BD fica como estava.
    """
    semear_conta_real()
    conteudo = _completo_com(
        tmp_path,
        "INSERT INTO transacoes (data, descricao, valor, categoria_id) "
        "VALUES ('2025-01-01', 'Café', -1.0, 999)",
    )

    resposta = importar(client, conteudo)

    assert (resposta.status_code, resposta.json()["detail"]) == (400, MENSAGEM_VALORES)
    assert nomes_das_contas() == [CONTA_REAL]
    assert anteriores(bd_em_ficheiro) == []


def test_backup_com_valores_validos_de_todas_as_enumeracoes_e_aceite(
    client, bd_em_ficheiro, tmp_path
):
    """Valores válidos passam: a verificação não recusa um backup bom.

    Cálculo à mão: uma categoria `receita` e uma `transferencia`, com uma
    transacção ligada à primeira -> as enumerações batem e não há chaves
    partidas -> 200.
    """
    semear_conta_real()
    conteudo = _completo_com(
        tmp_path,
        "INSERT INTO categorias (id, nome, tipo) VALUES (1, 'Receita', 'receita')",
        "INSERT INTO categorias (id, nome, tipo) VALUES (2, 'Transf', 'transferencia')",
        "INSERT INTO transacoes (data, descricao, valor, categoria_id) "
        "VALUES ('2025-01-01', 'Salário', 100.0, 1)",
    )

    resposta = importar(client, conteudo)

    assert resposta.status_code == 200, resposta.text


# ---------------------------------------------------------------------------
# A extensão é aceite com qualquer capitalização
# ---------------------------------------------------------------------------


def test_extensao_db_maiuscula_e_aceite(client, bd_em_ficheiro):
    """Um backup válido chamado `BACKUP.DB` é restaurado com 200.

    Cálculo à mão: o nome acaba em `.db` depois de passar a minúsculas
    (`filename.lower().endswith(".db")`), pelo que a primeira verificação não
    recusa. O conteúdo é o próprio export da BD da fixture, que tem as 11
    tabelas com todas as colunas — logo `_validar_sqlite` e `_validar_estrutura`
    passam e o `os.replace` troca a BD por ela própria, byte a byte.

    Estado final da BD: continua só com a `Conta Real`, e o `.anterior` fica no
    disco (comportamento esperado).
    """
    semear_conta_real()

    exportado = client.get("/api/backups/exportar")
    assert exportado.status_code == 200

    resposta = importar(client, exportado.content, nome="BACKUP.DB")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "ok": True,
        "mensagem": "Base de dados restaurada",
    }
    assert len(anteriores(bd_em_ficheiro)) == 1
    assert nomes_das_contas() == [CONTA_REAL]


def test_extensao_db_com_capitalizacao_mista_e_aceite(client, bd_em_ficheiro):
    """Um backup válido chamado `backup.Db` também é restaurado com 200.

    Cálculo à mão: `.lower()` de `backup.Db` dá `backup.db`, que acaba em
    `.db`; o resto do percurso é o do teste anterior — conteúdo válido, 11
    tabelas, `os.replace` atómico.

    Estado final da BD: só a `Conta Real`, e o `.anterior` no disco.
    """
    semear_conta_real()

    exportado = client.get("/api/backups/exportar")
    assert exportado.status_code == 200

    resposta = importar(client, exportado.content, nome="backup.Db")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "ok": True,
        "mensagem": "Base de dados restaurada",
    }
    assert len(anteriores(bd_em_ficheiro)) == 1
    assert nomes_das_contas() == [CONTA_REAL]


def test_extensao_errada_continua_a_ser_rejeitada(client, bd_em_ficheiro):
    """A capitalização só ajuda a `.db`: `.txt` continua a dar 400.

    Cálculo à mão: `.lower()` de `backup.txt` dá `backup.txt`, que não acaba em
    `.db`, pelo que a verificação responde 400 `Ficheiro inválido` — a mesma
    mensagem de antes, e ainda antes de se ler o conteúdo (não há `.tmp` no
    disco).

    Estado final da BD: intacta, com a `Conta Real`.
    """
    semear_conta_real()

    exportado = client.get("/api/backups/exportar")
    assert exportado.status_code == 200

    resposta = importar(client, exportado.content, nome="backup.txt")

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "Ficheiro inválido"
    assert not existe(bd_em_ficheiro, ".tmp")
    assert nomes_das_contas() == [CONTA_REAL]


# ---------------------------------------------------------------------------
# Várias cópias `.anterior-<data>` (achado 6.3)
# ---------------------------------------------------------------------------


def test_dois_restauros_guardam_duas_copias(client, bd_em_ficheiro):
    """Um segundo restauro não apaga a cópia do primeiro.

    É o caso que perdia dados: restaura-se o backup errado e depois outro para
    corrigir. Com um só `.anterior`, o segundo restauro substituía a BD original
    pelo backup errado.

    Cálculo à mão:
      * a BD tem `Conta Real`; exporta-se (o «backup errado»);
      * cria-se `Conta Nova`: a BD original tem as duas contas;
      * 1.º restauro do export -> a 1.ª cópia guarda a BD original, com as duas
        contas, e a BD fica só com a `Conta Real`;
      * 2.º restauro do mesmo export -> a 2.ª cópia guarda só a `Conta Real`.
    As duas cópias ficam, por esta ordem, e a original continua recuperável.
    Os dois restauros podem cair no mesmo segundo: o 2.º leva então `-2` no
    nome, que ordena depois do 1.º.
    """
    semear_conta_real()
    exportado = client.get("/api/backups/exportar").content
    db = sessao_nova()
    try:
        db.add(Conta(nome="Conta Nova", saldo_referencia=50.0, data_referencia=date(2024, 2, 1)))
        db.commit()
    finally:
        db.close()

    assert importar(client, exportado).status_code == 200
    assert importar(client, exportado).status_code == 200

    copias = anteriores(bd_em_ficheiro)
    assert [contas_em(c) for c in copias] == [["Conta Nova", CONTA_REAL], [CONTA_REAL]]
    for copia in copias:
        assert re.fullmatch(
            re.escape(bd_em_ficheiro.name) + r"\.anterior-\d{4}-\d{2}-\d{2}-\d{6}(-\d+)?",
            copia.name,
        ), copia.name
    assert nomes_das_contas() == [CONTA_REAL]


def test_ficam_so_as_cinco_copias_mais_recentes(client, bd_em_ficheiro):
    """Um restauro com 5 cópias no disco apaga a mais antiga e fica com 5.

    Cálculo à mão: semeiam-se 5 cópias com datas de 2020 (dias 1 a 5) e um
    `.anterior` sem data, de uma versão anterior da aplicação. O restauro cria
    a 6.ª cópia, com a data de hoje, que ordena depois das de 2020. Ficam as 5
    mais recentes: as de 2020 dos dias 2 a 5 e a de hoje. Sai a do dia 1. O
    `.anterior` sem data não conta para as 5 e fica no disco.
    """
    semear_conta_real()
    antigas = [Path(f"{bd_em_ficheiro}.anterior-2020-01-0{dia}-120000") for dia in range(1, 6)]
    for antiga in antigas:
        antiga.write_bytes(b"copia antiga")
    sem_data = caminho_do(bd_em_ficheiro, ".anterior")
    sem_data.write_bytes(b"copia de uma versao anterior")

    exportado = client.get("/api/backups/exportar").content
    assert importar(client, exportado).status_code == 200

    copias = anteriores(bd_em_ficheiro)
    assert copias[:4] == antigas[1:]
    assert len(copias) == 5
    assert contas_em(copias[4]) == [CONTA_REAL]
    assert not antigas[0].exists()
    assert sem_data.read_bytes() == b"copia de uma versao anterior"


# ---------------------------------------------------------------------------
# Cópia atómica do `.anterior` e rollback
# ---------------------------------------------------------------------------


def _restauro_bom_e_conta_nova(client, bd_em_ficheiro):
    """Prepara o cenário dos testes da cópia atómica e devolve os bytes do `.anterior`.

    1. `Conta Real` na BD; exportar e importar o export (restauro bom), o que
       deixa um `.anterior` só com a `Conta Real`.
    2. Depois disso, cria-se `Conta Nova`: é o dado recente que um rollback
       errado apagaria.

    No fim, a BD tem as duas contas e o `.anterior` só a `Conta Real`.
    """
    semear_conta_real()
    exportado = client.get("/api/backups/exportar")
    assert importar(client, exportado.content).status_code == 200

    db = sessao_nova()
    try:
        db.add(Conta(nome="Conta Nova", saldo_referencia=50.0, data_referencia=date(2024, 2, 1)))
        db.commit()
    finally:
        db.close()

    anterior = ultimo_anterior(bd_em_ficheiro)
    assert contas_em(anterior) == [CONTA_REAL]
    assert nomes_das_contas() == ["Conta Nova", CONTA_REAL]
    return exportado.content, anterior.read_bytes()


def test_falha_a_meio_da_copia_nao_estraga_o_anterior_nem_a_bd(client, bd_em_ficheiro, monkeypatch):
    """Uma cópia do `.anterior` interrompida não toca no `.anterior` bom nem na BD.

    Antes da correcção, a cópia escrevia no próprio `.anterior`, e uma falha a meio
    (disco cheio) deixava-o cortado; o rollback repunha depois a BD a partir
    dessa cópia cortada.

    A falha simulada escreve metade dos bytes no destino e levanta `OSError`,
    como um disco cheio. Só a cópia que parte da BD é sabotada.

    Cálculo à mão:
      * o pedido dá 500, porque a falha está dentro do bloco do rollback;
      * o `.anterior` tem os mesmos bytes que antes (só a `Conta Real`): a cópia
        cortada foi para o `.anterior.tmp`, que o rollback apaga;
      * a BD continua com as duas contas: a troca nunca aconteceu, e o rollback
        não a repõe a partir de um `.anterior` que não é deste pedido — se o
        fizesse, a `Conta Nova` desaparecia;
      * nenhum `.tmp` nem `.anterior.tmp` fica no disco.
    """
    exportado, anterior_antes = _restauro_bom_e_conta_nova(client, bd_em_ficheiro)
    copia_real = shutil.copy2

    def copia_cortada(origem, destino, *args, **kwargs):
        if Path(origem).resolve() == bd_em_ficheiro:
            dados = Path(origem).read_bytes()
            Path(destino).write_bytes(dados[: len(dados) // 2])
            raise OSError("disco cheio (simulado)")
        return copia_real(origem, destino, *args, **kwargs)

    monkeypatch.setattr(backups.shutil, "copy2", copia_cortada)

    resposta = importar(client, exportado)

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == "Falha ao restaurar: disco cheio (simulado)"
    assert [c.read_bytes() for c in anteriores(bd_em_ficheiro)] == [anterior_antes]
    assert nomes_das_contas() == ["Conta Nova", CONTA_REAL]
    assert integridade(bd_em_ficheiro) == ("linha", "ok")
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores_tmp(bd_em_ficheiro) == []


def test_falha_na_troca_remove_o_tmp(client, bd_em_ficheiro, monkeypatch):
    """Se o `os.replace` do `.tmp` para a BD falhar, o `.tmp` não fica no disco.

    Antes da correcção, o rollback não removia o `.tmp`, que só
    desaparecia no pedido seguinte.

    Só a troca `.tmp` → BD é sabotada; a da cópia `.tmp` → cópia final passa.
    Cálculo à mão:
      * 500;
      * a BD continua com as duas contas (o `os.replace` é atómico e falhou);
      * há duas cópias: a do restauro bom (`Conta Real`) e a deste pedido, com
        as duas contas, que fica;
      * o `.tmp` foi removido.
    """
    exportado, _ = _restauro_bom_e_conta_nova(client, bd_em_ficheiro)
    troca_real = os.replace
    tmp = str(caminho_do(bd_em_ficheiro, ".tmp"))

    def troca_falhada(origem, destino, *args, **kwargs):
        if str(origem) == tmp:
            raise OSError("troca falhada (simulado)")
        return troca_real(origem, destino, *args, **kwargs)

    monkeypatch.setattr(backups.os, "replace", troca_falhada)

    resposta = importar(client, exportado)

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == "Falha ao restaurar: troca falhada (simulado)"
    assert nomes_das_contas() == ["Conta Nova", CONTA_REAL]
    assert len(anteriores(bd_em_ficheiro)) == 2
    assert contas_em(ultimo_anterior(bd_em_ficheiro)) == [
        "Conta Nova",
        CONTA_REAL,
    ]
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores_tmp(bd_em_ficheiro) == []


def test_falha_depois_da_troca_repoe_a_bd_a_partir_do_anterior(client, bd_em_ficheiro, monkeypatch):
    """Se a verificação pós-troca falhar, a BD volta ao estado de antes do pedido.

    A troca já aconteceu (a BD passou a ser o export, só com a `Conta Real`), e
    só aqui o rollback tem mesmo de repor a BD a partir do `.anterior` que este
    pedido criou. A verificação pós-troca é sabotada só quando lê a BD; a
    validação do `.tmp`, antes, passa.

    Cálculo à mão:
      * 500;
      * a BD volta a ter as duas contas, tal como antes do pedido;
      * o `.anterior` também tem as duas contas e fica no disco.
    """
    exportado, _ = _restauro_bom_e_conta_nova(client, bd_em_ficheiro)
    validar_real = backups._validar_estrutura

    def validar_falha_na_bd(caminho):
        if Path(caminho).resolve() == bd_em_ficheiro:
            raise RuntimeError("verificação falhada (simulado)")
        return validar_real(caminho)

    monkeypatch.setattr(backups, "_validar_estrutura", validar_falha_na_bd)

    resposta = importar(client, exportado)

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == ("Falha ao restaurar: verificação falhada (simulado)")
    assert nomes_das_contas() == ["Conta Nova", CONTA_REAL]
    assert contas_em(ultimo_anterior(bd_em_ficheiro)) == [
        "Conta Nova",
        CONTA_REAL,
    ]
    assert not existe(bd_em_ficheiro, ".tmp")


def test_falha_a_meio_da_reposicao_nao_corta_a_bd(client, bd_em_ficheiro, monkeypatch):
    """Se a própria reposição do rollback falhar a meio, a BD não fica cortada.

    Como no teste anterior, a verificação pós-troca falha e o rollback tenta
    repor a BD a partir do `.anterior`. Aqui essa cópia também falha a meio
    (metade dos bytes, depois `OSError`). A cópia cortada vai para o
    `.anterior.tmp`, que é apagado; a BD nunca é escrita no lugar.

    Cálculo à mão:
      * 500, com a mensagem da falha **original** (a da verificação): a falha
        do rollback é engolida para não a esconder;
      * a BD é o export que a troca lá pôs (só a `Conta Real`) e está íntegra;
        a reposição não chegou a acontecer, mas também não estragou nada;
      * o `.anterior` está intacto, com as duas contas: é dele que se recupera
        à mão;
      * nenhum `.tmp` nem `.anterior.tmp` fica no disco.
    """
    exportado, _ = _restauro_bom_e_conta_nova(client, bd_em_ficheiro)
    validar_real = backups._validar_estrutura
    copia_real = shutil.copy2

    def validar_falha_na_bd(caminho):
        if Path(caminho).resolve() == bd_em_ficheiro:
            raise RuntimeError("verificação falhada (simulado)")
        return validar_real(caminho)

    def reposicao_cortada(origem, destino, *args, **kwargs):
        # A única cópia que não parte da BD é a da reposição, a partir da
        # cópia deste pedido
        if Path(origem).resolve() != bd_em_ficheiro:
            dados = Path(origem).read_bytes()
            Path(destino).write_bytes(dados[: len(dados) // 2])
            raise OSError("disco cheio (simulado)")
        return copia_real(origem, destino, *args, **kwargs)

    monkeypatch.setattr(backups, "_validar_estrutura", validar_falha_na_bd)
    monkeypatch.setattr(backups.shutil, "copy2", reposicao_cortada)

    resposta = importar(client, exportado)

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == ("Falha ao restaurar: verificação falhada (simulado)")
    assert integridade(bd_em_ficheiro) == ("linha", "ok")
    assert nomes_das_contas() == [CONTA_REAL]
    assert contas_em(ultimo_anterior(bd_em_ficheiro)) == ["Conta Nova", CONTA_REAL]
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores_tmp(bd_em_ficheiro) == []


# ---------------------------------------------------------------------------
# Um backup antigo traz as chaves para `ativos_old`
# ---------------------------------------------------------------------------


def _ddl_em(caminho: Path, tabela: str) -> str:
    con = sqlite3.connect(caminho)
    try:
        return con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (tabela,)).fetchone()[0]
    finally:
        con.close()


def test_restaurar_backup_com_fk_partida_repara_o_schema(
    client, bd_em_ficheiro, tmp_path, criar_bd_com_fk_partida
):
    """Um backup com as chaves para `ativos_old` é aceite e fica com as chaves certas.

    Cálculo à mão: o backup tem todas as tabelas e colunas do modelo, logo
    passa a validação (200). Depois da troca, a reparação põe as duas tabelas a
    apontar para `ativos`, e as linhas da semente da fixture continuam lá: 3
    preços e 2 movimentos.
    """
    backup = tmp_path / "antigo.db"
    criar_bd_com_fk_partida(backup)
    assert "ativos_old" in _ddl_em(backup, "precos_ativo")

    resposta = importar(client, backup.read_bytes())

    assert resposta.status_code == 200
    for tabela in ("precos_ativo", "movimentos_ativo"):
        assert "ativos_old" not in _ddl_em(bd_em_ficheiro, tabela)
    con = sqlite3.connect(bd_em_ficheiro)
    try:
        assert con.execute("SELECT count(*) FROM precos_ativo").fetchone() == (3,)
        assert con.execute("SELECT count(*) FROM movimentos_ativo").fetchone() == (2,)
    finally:
        con.close()


def test_falha_na_reparacao_repoe_a_bd_anterior(
    client, bd_em_ficheiro, tmp_path, criar_bd_com_fk_partida, monkeypatch
):
    """Se a reparação falhar, a BD actual não chega a ser tocada.

    Cálculo à mão: a BD tem a `Conta Real` e o backup não tem contas. A
    reparação corre no `.tmp`, antes da troca, e falha: 500 com a mensagem da
    falha, a `Conta Real` continua lá, e não há `.tmp` nem `.anterior`.
    """
    semear_conta_real()
    backup = tmp_path / "antigo.db"
    criar_bd_com_fk_partida(backup)

    def reparar_falha(caminho):
        raise RuntimeError("reparação falhada (simulado)")

    monkeypatch.setattr(database, "MIGRACOES", (("reparação", reparar_falha),))

    resposta = importar(client, backup.read_bytes())

    assert resposta.status_code == 500
    assert resposta.json()["detail"] == ("Falha ao restaurar: reparação falhada (simulado)")
    assert nomes_das_contas() == [CONTA_REAL]
    assert not existe(bd_em_ficheiro, ".tmp")
    assert anteriores(bd_em_ficheiro) == []


def test_arranque_repara_o_schema_partido(bd_em_ficheiro, criar_bd_com_fk_partida):
    """`criar_tabelas()`, que corre no arranque, repara uma BD com as chaves para `ativos_old`.

    Está aqui, e não em `test_reparar_fk_ativos.py`, porque precisa da BD em
    ficheiro do `DB_PATH` temporário que esta pasta prepara.
    """
    import database

    engine.dispose()
    bd_em_ficheiro.unlink()
    criar_bd_com_fk_partida(bd_em_ficheiro)

    database.criar_tabelas()

    for tabela in ("precos_ativo", "movimentos_ativo"):
        assert "ativos_old" not in _ddl_em(bd_em_ficheiro, tabela)
    assert _versao_em(bd_em_ficheiro) == 2


# ---------------------------------------------------------------------------
# Versão do schema e colunas em falta (achado 1.1)
# ---------------------------------------------------------------------------


def _versao_em(caminho: Path) -> int:
    con = sqlite3.connect(caminho)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


def _sem_coluna_fee(caminho: Path) -> None:
    """Tira `perfis_importacao.coluna_fee`, como numa BD de antes de Junho."""
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute("ALTER TABLE perfis_importacao DROP COLUMN coluna_fee")
    finally:
        con.close()


def _acrescentar_coluna_fee(caminho):
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        colunas = {linha[1] for linha in con.execute("PRAGMA table_info(perfis_importacao)")}
        if "coluna_fee" in colunas:
            return False
        con.execute("ALTER TABLE perfis_importacao ADD COLUMN coluna_fee INTEGER")
    finally:
        con.close()
    return True


def test_backup_antigo_e_migrado_antes_de_ser_validado(
    client, bd_em_ficheiro, tmp_path, monkeypatch
):
    """Um backup sem uma coluna que uma migração acrescenta é aceite.

    Cálculo à mão: o backup está na versão 0 e não tem `coluna_fee`. Com uma
    3.ª migração que a acrescenta, a migração corre no `.tmp` antes da
    validação, que passa: 200, a coluna existe e a BD fica na versão 3. Sem a
    migração, o mesmo ficheiro é recusado
    (`test_coluna_em_falta_numa_so_tabela_e_rejeitado`).
    """
    backup = tmp_path / "antigo.db"
    criar_bd_do_modelo(backup)
    _sem_coluna_fee(backup)
    monkeypatch.setattr(
        database, "MIGRACOES", database.MIGRACOES + (("coluna_fee", _acrescentar_coluna_fee),)
    )

    resposta = importar(client, backup.read_bytes())

    assert resposta.status_code == 200
    assert colunas_em_falta(str(bd_em_ficheiro)) == []
    assert _versao_em(bd_em_ficheiro) == 3


def test_backup_restaurado_fica_na_ultima_versao(client, bd_em_ficheiro, tmp_path):
    """Cálculo à mão: um backup na versão 0, com as 2 migrações, fica na 2."""
    backup = tmp_path / "antigo.db"
    criar_bd_do_modelo(backup)
    assert _versao_em(backup) == 0

    resposta = importar(client, backup.read_bytes())

    assert resposta.status_code == 200
    assert _versao_em(bd_em_ficheiro) == 2


def test_arranque_com_bd_nova_fica_na_ultima_versao_sem_migrar(bd_em_ficheiro, monkeypatch):
    """Uma BD criada agora já tem o schema final: nenhuma migração corre.

    Cálculo à mão: duas migrações falsas, que registariam se corressem; a BD
    fica na versão 2 e a lista fica vazia.
    """
    corridas = []

    def migracao(caminho):
        corridas.append(caminho)
        return True

    monkeypatch.setattr(database, "MIGRACOES", (("um", migracao), ("dois", migracao)))
    engine.dispose()
    bd_em_ficheiro.unlink()

    database.criar_tabelas()

    assert corridas == []
    assert _versao_em(bd_em_ficheiro) == 2


def test_arranque_com_bd_antiga_corre_as_migracoes(bd_em_ficheiro, monkeypatch):
    """Cálculo à mão: uma BD na versão 0 com a 3.ª migração falsa corre-a, e fica na 3."""
    monkeypatch.setattr(
        database, "MIGRACOES", database.MIGRACOES + (("coluna_fee", _acrescentar_coluna_fee),)
    )
    engine.dispose()
    _sem_coluna_fee(bd_em_ficheiro)

    database.criar_tabelas()

    assert colunas_em_falta(str(bd_em_ficheiro)) == []
    assert _versao_em(bd_em_ficheiro) == 3


def test_arranque_recusa_bd_com_colunas_em_falta(bd_em_ficheiro):
    """Sem migração que a acrescente, falta `coluna_fee`: o arranque recusa.

    Antes do 1.1, a aplicação abria e `/api/perfis-importacao/` dava 500.
    """
    engine.dispose()
    _sem_coluna_fee(bd_em_ficheiro)

    with pytest.raises(RuntimeError) as erro:
        database.criar_tabelas()

    assert str(erro.value) == (
        "A base de dados é de uma versão anterior do Rastreio-DB que não se "
        "consegue actualizar automaticamente.\n"
        f"  {database.DB_PATH}\n"
        "Falta: perfis_importacao.coluna_fee"
    )

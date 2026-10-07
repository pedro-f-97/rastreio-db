"""Configuração dos testes de backup, que precisam de uma BD em ficheiro.

Porque uma sub-pasta com conftest próprio
-----------------------------------------
`backend/routers/backups.py:7` faz `from database import Base, DB_PATH, engine`, e
`importar_backup` não usa `get_db`: trabalha com a `engine` e com o `DB_PATH` do
módulo. Por isso a fixture `session` do conftest pai, que põe uma BD SQLite
**em memória** e lha injecta por `get_db`, não chega: o `os.replace` do endpoint
(`backups.py:141`) substitui um ficheiro, e não há ficheiro para substituir.

A boa notícia é que não é preciso remapear nada. O conftest pai põe
`RASTREIO_DB_DIR` num directório temporário antes de `database` ser importado, e
`database.py` resolve o caminho ao nível do módulo. Logo `database.DB_PATH` já
aponta para `<tmp>/dados/rastreio.db`: uma BD em ficheiro descartável. E como
`DB_PATH` e `engine` foram ligados no import de `backups`, remapear um ou o
outro não funcionaria sequer — `monkeypatch.setattr(database, "DB_PATH", ...)`
deixaria `backups.DB_PATH` como estava.

Os três asserções de caminho vêm **antes** de qualquer escrita
--------------------------------------------------------------
`bd_em_ficheiro` é a fixture que vai mesmo apagar e recriar um ficheiro, e por
isso confirma primeiro, e nesta ordem, que o ficheiro que vai apagar:

1. está dentro do directório temporário preparado pelo conftest pai;
2. não está dentro da pasta `backend/` de onde esta cópia corre;
3. não é a BD de produção, `backend/dados/rastreio.db`.

O ponto 2 é calculado a partir deste ficheiro (`parents[2]`), e não a partir da
raiz do repositório, para que a guarda valha tanto aqui como numa cópia dos
testes feita noutro sítio — o que é exactamente o que se faz para medir uma
mutação.

Se alguma asserção falhar, a fixture falha antes de qualquer pedido e antes de
qualquer escrita em disco. São as mesmas três verificações de
`test_seguranca_bd.py:22`, repetidas aqui porque este é o fixture que toca no
ficheiro — aquele teste observa, este age.

O que cada fixture faz
----------------------
* `bd_em_ficheiro` — `engine.dispose()`, apaga o ficheiro da BD e os irmãos
  (`-journal`, `-wal`, `-shm`), e recria o esquema com `create_all`. Começa do
  zero a cada teste, sem `drop_all`: um `drop_all` sobre uma BD deixada pelo
  cenário das colunas erradas tem de funcionar, e recomeçar do ficheiro é mais
  simples de raciocinar.
* `client` — a app com **só** `backups.router`. Estes testes não usam nenhum
  outro endpoint, e a leitura da base de dados faz-se com uma sessão nova sobre
  a engine de ficheiro, depois do pedido. Sem `get_db`, sem lista de routers.
* `guarda_ficheiros` (autouse, por teste) — ver o docstring da própria fixture.
"""

import glob
import os
from pathlib import Path

import pytest

# O directório que o conftest pai preparou. Lido do ambiente porque é de lá que
# `database` o tirou, e é o único sítio onde a BD de teste pode estar.
RASTREIO_DB_DIR = Path(os.environ["RASTREIO_DB_DIR"]).resolve()

# A pasta `backend/` de onde esta cópia corre. Calculada a partir do ficheiro,
# e não a partir da raiz do repositório, para que a guarda valha tanto no
# repositório como numa cópia dos testes feita noutro sítio.
BACKEND = Path(__file__).resolve().parents[2]
BD_DE_PRODUCAO = (BACKEND / "dados" / "rastreio.db").resolve()

# Os ficheiros que uma importação de backup pode deixar para trás, e que não
# podem sobreviver a um teste: o temporário e os arquivos de lado do SQLite.
# O `.anterior` ficou de fora de propósito: depois do D6 ele é o estado
# anterior ao restauro, criado a cada sucesso e substituído no seguinte, e por
# isso sobreviver a um teste é comportamento esperado — quem o limpa entre
# testes é a fixture `bd_em_ficheiro` (ver `limpar_bd_e_irmaos`).
LIXO = ("*.tmp", "*.tmp-wal", "*.tmp-shm", "*-wal", "*-shm",
        "*-journal", "_fixture_*")


def listar_tudo(directorio: Path) -> set[str]:
    """Todos os ficheiros sob `directorio`, com caminho relativo e ordenados."""
    return {
        str(p.relative_to(directorio))
        for p in directorio.rglob("*")
        if p.is_file()
    }


def sem_anteriores(ficheiros: set[str]) -> set[str]:
    """Fica só com o que não é `.anterior` (ver o docstring de `guarda_ficheiros`)."""
    return {nome for nome in ficheiros if not nome.endswith(".anterior")}


def limpar_bd_e_irmaos(caminho: Path) -> None:
    """Apaga a BD, os arquivos de lado e o que o endpoint deixou atrás.

    Vale a pena limpar também `rastreio.db.tmp` e `rastreio.db.anterior`: se um
    pedido falhar a meio e deixar um deles para trás, esse ficheiro não é culpa do
    teste seguinte, e deixá-lo contaminaria a leitura da guarda de ficheiros. O
    `.anterior` é limpo aqui mesmo depois de um restauro bem sucedido (depois do
    D6 ele é esperado e fica no disco) — é esta limpeza entre testes que permite
    à `guarda_ficheiros` ignorar os `.anterior` sem ficar cega a outro lixo.
    """
    for sufixo in ("", "-journal", "-wal", "-shm", ".tmp", ".anterior"):
        alvo = Path(str(caminho) + sufixo)
        if alvo.exists():
            alvo.unlink()
    for alvo in caminho.parent.glob(caminho.name + ".*-journal"):
        alvo.unlink()


@pytest.fixture
def bd_em_ficheiro():
    """BD em ficheiro, recriada do zero, dentro do directório temporário.

    Devolve o `DB_PATH` em uso, que é o caminho que os ficheiros `.tmp` e
    `.anterior` do endpoint vão ter (`backups.py:111-112`).
    """
    import database

    caminho = Path(database.DB_PATH).resolve()

    # Antes de qualquer escrita. A ordem é a da leitura: primeiro que está no
    # temporário, depois que não está na pasta backend/, e só então se toca.
    assert RASTREIO_DB_DIR in caminho.parents, (
        f"A BD de teste não está dentro do directório temporário: {caminho}. "
        f"Esperado dentro de: {RASTREIO_DB_DIR}."
    )
    assert BACKEND not in caminho.parents, (
        f"A BD de teste está dentro da pasta backend/: {caminho}. "
        f"Isto arriscaria tocar em {BD_DE_PRODUCAO}."
    )
    assert caminho != BD_DE_PRODUCAO, (
        f"A BD de teste é a BD de produção: {caminho}."
    )

    database.garantir_pasta_dados()
    database.engine.dispose()
    limpar_bd_e_irmaos(caminho)
    database.Base.metadata.create_all(bind=database.engine)

    try:
        yield caminho
    finally:
        database.engine.dispose()
        limpar_bd_e_irmaos(caminho)


@pytest.fixture
def client(bd_em_ficheiro):
    """TestClient só com o router de backups, sobre a BD em ficheiro.

    Não há override de `get_db` porque o router de backups não o usa. O lifespan
    não é preciso: `create_all` já correu na fixture `bd_em_ficheiro`.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from routers import backups

    app = FastAPI()
    app.include_router(backups.router, prefix="/api")

    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def guarda_ficheiros(bd_em_ficheiro):
    """Falha se um teste deixar um `.tmp` ou outro ficheiro novo.

    Compara a listagem completa do directório temporário antes e depois do teste.
    É mais forte do que verificar os dois nomes conhecidos: apanha também um
    ficheiro de fixture criado no sítio errado.

    Os `.anterior` ficam de fora da comparação e do `LIXO`: depois do D6 um
    `.anterior` após um restauro bem sucedido é artefacto esperado (fica no
    disco até ao restauro seguinte), e a `bd_em_ficheiro` o limpa entre testes
    para não contaminar a leitura. Um `.anterior` deixado por uma tentativa
    falhada escapa a esta guarda, mas não escapa a `test_rejeicao_nao_toca_no_anterior_pre_existente`.

    A listagem é tirada depois de `bd_em_ficheiro`, porque a fixture destrói o
    ficheiro da BD e a ordem de destruição é a inversa da de criação: a guarda
    é a última a montar e a primeira a desmontar, e por isso vê a BD ainda no
    sítio nos dois lados da comparação.
    """
    antes = sem_anteriores(listar_tudo(RASTREIO_DB_DIR))

    yield

    depois = sem_anteriores(listar_tudo(RASTREIO_DB_DIR))
    assert depois == antes, (
        "O teste alterou os ficheiros do directório temporário. "
        f"Novos: {sorted(depois - antes)}. "
        f"Desaparecidos: {sorted(antes - depois)}."
    )
    for padrao in LIXO:
        assert not glob.glob(str(RASTREIO_DB_DIR / "**" / padrao), recursive=True), (
            f"O teste deixou ficheiros {padrao} no directório temporário."
        )


@pytest.fixture(scope="session", autouse=True)
def guarda_ficheiros_no_fim_da_corrida():
    """No fim da sessão, o directório temporário não pode ter lixo nenhum.

    Rede de segurança para o caso de um teste rebentar a meio e a fixture
    `guarda_ficheiros` não chegar a correr. Os `.anterior` ficaram de fora do
    `LIXO` (ver `guarda_ficheiros`), mas não ficam impunes: a última
    `bd_em_ficheiro` a desmontar limpa-os todos em `limpar_bd_e_irmaos`.
    """
    yield

    for padrao in LIXO:
        assert not glob.glob(str(RASTREIO_DB_DIR / "**" / padrao), recursive=True), (
            f"Ficou lixo {padrao} no directório temporário ao fim da corrida: "
            f"{glob.glob(str(RASTREIO_DB_DIR / '**' / padrao), recursive=True)}"
        )

"""Testes de guarda: garantem que a suite não pode estragar os dados reais.

Estes testes não testam a aplicação. Testam a **integridade do
equipamento de teste**. Se algum deles falhar, a suite deixou de ser segura
para correr e o resultado é para parar e investigar, não para ignorar.

O risco concreto que cobrem: `backend/dados/rastreio.db` é a base de dados de
produção, não está versionada, e o `conftest.py` depende de uma condição de
importação frágil — definir `RASTREIO_DB_DIR` antes de o `database` ser
importado. Se essa ordem se inverter num refactor futuro, a suite passa a
correr contra a BD real sem dar erro nenhum. Daí o teste explícito.
"""

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent


def test_bd_real_esta_fora_do_reachavel():
    """O caminho de destino da BD de testes não pode estar dentro do repo."""
    from database import DB_PATH

    db_path = Path(DB_PATH).resolve()

    assert REPO not in db_path.parents, (
        f"A BD de testes aponta para dentro do repositório: {db_path}. "
        f"Isto arriscaria tocar em {BACKEND / 'dados' / 'rastreio.db'}."
    )
    assert db_path != (BACKEND / "dados" / "rastreio.db").resolve()


def test_RASTREIO_DB_DIR_foi_definido_antes_do_import():
    """O conftest tem de ter ganho a corrida contra o import de `database`.

    Se este teste falhar, a ordem de imports no conftest foi invertida e todos
    os outros testes desta suite estão a correr contra a BD de produção.
    """
    import database

    # A variável tem de existir. Sem este assert, `os.environ[...]` levantaria
    # KeyError — mas o caso que interessa não é a variável ausente, é a
    # variável presente *demais tarde*, em que os valores até coincidem.
    assert "RASTREIO_DB_DIR" in os.environ, (
        "RASTREIO_DB_DIR não está definido. O conftest não a preparou."
    )

    esperado = os.path.abspath(os.environ["RASTREIO_DB_DIR"])
    assert database.BASE_DIR == esperado, (
        f"database.BASE_DIR ({database.BASE_DIR}) não corresponde a "
        f"RASTREIO_DB_DIR ({esperado}). O módulo foi importado antes de o "
        "conftest definir a variável de ambiente."
    )

    # Um dos dois pode estar certo por coincidência; tem de ser o temporário.
    # `_resolver_base_dir` sem override devolve `dirname(__file__)`, que é
    # exactamente backend/ — daí este teste separado: sem ele, um
    # BASE_DIR igual ao cwd passaria o assert de cima e o pior ainda
    # aconteceria.
    assert database.BASE_DIR != str(BACKEND), (
        "database.BASE_DIR aponta para backend/ — é o que acontece quando o "
        "override é ignorado. Os testes estão a usar a BD de produção."
    )


def test_nenhum_ficheiro_de_dados_criado_no_backend():
    """A suite não deve criar pastas/ficheiros dentro de backend/."""
    pasta_dados = BACKEND / "dados"
    if not pasta_dados.exists():
        return  # nada a verificar: nem sequer existe pasta de dados

    antes = {p.name for p in pasta_dados.iterdir()}
    assert antes == {"rastreio.db"}, (
        f"Pasta de dados real alterada durante os testes. Antes: {antes}. "
        "Isto não deveria acontecer — ver test_RASTREIO_DB_DIR_foi_definido_antes_do_import."
    )


def test_main_importa_so_com_ambiente_isolado():
    """Importar `main` é seguro, desde que o ambiente aponte para o tmp.

    O `main.py` tem efeitos colaterais no import (cria o ficheiro de log de
    arranque e pode redireccionar streams). Este teste confirma que, com o
    ambiente preparado pelo conftest, nada escapa para o HOME real do
    utilizador. É também a forma de confirmar que `main.ROUTERS` é importável,
    o que o teste seguinte precisa.
    """
    home_real = Path(sys.argv[0]).anchor  # ex. "/" em Linux, "C:\\" em Windows
    tmp_dir = Path(os.environ["HOME"]).resolve()

    assert tmp_dir != home_real, "HOME não foi redireccionado para um tmp"

    import main

    assert main.app is not None
    assert main.LOG_ARRANQUE is None or str(main.LOG_ARRANQUE).startswith(str(tmp_dir)), (
        f"O log de arranque foi criado fora do tmp: {main.LOG_ARRANQUE}"
    )


def test_app_de_testes_cobre_os_mesmos_routers_que_o_main():
    """A app montada nos testes não pode divergir da app real.

    `main.py` é a aplicação que o utilizador executa. Se os testes usarem uma
    lista de routers diferente, podem passar todos enquanto a app real tem um
    router partido. Este teste amarra as duas listas.
    """
    from routers import (
        backups,
        categorias,
        configuracao,
        contas,
        estatisticas,
        importacao,
        patrimonio,
        perfis_importacao,
        regras,
        tipos_ativo,
        transacoes,
    )
    import main

    dos_testes = [
        categorias.router, transacoes.router, regras.router, importacao.router,
        estatisticas.router, backups.router, configuracao.router,
        perfis_importacao.router, patrimonio.router, contas.router,
        tipos_ativo.router,
    ]

    # APIRouter não é hashable, por isso comparam-se as rotas já montadas.
    def _rotas(routers):
        return {
            (rota.path, metodo)
            for router in routers
            for rota in router.routes
            for metodo in (rota.methods or set())
        }

    rotas_testes = _rotas(dos_testes)
    rotas_main = _rotas(main.ROUTERS)

    assert rotas_testes == rotas_main, (
        "As rotas dos testes divergiram das de main.ROUTERS. "
        f"Só nos testes: {sorted(rotas_testes - rotas_main)}. "
        f"Só no main: {sorted(rotas_main - rotas_testes)}."
    )

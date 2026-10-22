"""Testes da API de configuração (`/api/configuracao/`).

Cobre os três endpoints de `backend/routers/configuracao.py`:

* `GET /estado` (`:8-13`) — devolve `inicializado` e `tour_visto` (False/False
  se não houver linha `Configuracao`);
* `POST /inicializar` (`:15-48`) — com parâmetros `com_categorias` (True) e
  `perfil` (completo/minimalista). Ao inicializar com `perfil=completo`,
  semeia **15 categorias** e **53 subcategorias** (constantes lidas de
  `backend/dados_iniciais.py`) e **9 tipos de ativo**, criando só os que faltam
  pelo nome (`semear_dados_iniciais`);
  devolve `200 {"ok": False, ...}` se já `inicializado`, e `200 {"ok": True,
  ...}` caso contrário;
* `POST /tour-visto` (`:50-58`) — marca `tour_visto=True`; **comportamento
  actual:** se não existir linha, cria `Configuracao(inicializado=True,
  tour_visto=True)` (marcando também como inicializado). Este é um efeito
  secundário, anotado.

Valores esperados calculados à mão e escritos como constantes, com a soma por
categoria verificada em `dados_iniciais.py`. Os testes não tocam na base de dados
real (ver `conftest.py`). Como a fixture `client` e a fixture `session`
partilham a sessão SQLAlchemy, as verificações de estado começam por
`session.expire_all()`.

"""

import pytest

from database import Categoria, Configuracao, Subcategoria, TipoAtivo, TipoCategoria

# Constantes obtidas por leitura de `dados_iniciais.py` (perfil completo)
CATEGORIAS_COMPLETO_COUNT = 15
SUBCATEGORIAS_COMPLETO_COUNT = 53
SEED_TIPOS_ATIVO_COUNT = 9


# ---------------------------------------------------------------------------
# GET /estado
# ---------------------------------------------------------------------------


def test_estado_sem_configuracao(client, session):
    session.expire_all()
    r = client.get("/api/configuracao/estado")
    assert r.status_code == 200
    assert r.json() == {"inicializado": False, "tour_visto": False}
    assert session.query(Configuracao).count() == 0


def test_estado_com_configuracao(client, session):
    session.add(Configuracao(inicializado=True, tour_visto=True))
    session.commit()
    r = client.get("/api/configuracao/estado")
    assert r.status_code == 200
    assert r.json() == {"inicializado": True, "tour_visto": True}
    assert session.query(Configuracao).count() == 1


# ---------------------------------------------------------------------------
# POST /inicializar
# ---------------------------------------------------------------------------


def test_inicializar_default_cria_categorias_tipos_e_configuracao(client, session):
    r = client.post("/api/configuracao/inicializar")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "mensagem": "Categorias e subcategorias criadas com sucesso"}
    session.expire_all()
    assert session.query(Configuracao).count() == 1
    config = session.query(Configuracao).first()
    assert config.inicializado is True
    assert config.tour_visto is False
    assert session.query(Categoria).count() == CATEGORIAS_COMPLETO_COUNT
    assert session.query(Subcategoria).count() == SUBCATEGORIAS_COMPLETO_COUNT
    assert session.query(TipoAtivo).count() == SEED_TIPOS_ATIVO_COUNT


@pytest.mark.parametrize("perfil", ["completo", "minimalista"])
def test_inicializar_a_prestacao_da_casa_nao_trata_patrimonio(client, session, perfil):
    """A subcategoria predefinida «Casa › Prestação» não é marcada como património.

    Cálculo à mão: em `dados_iniciais.py`, a «Casa» dos dois perfis tem
    `("Prestação", False)`. Marcada, cada prestação somava ao custo do imóvel o
    valor inteiro, juros incluídos, e a dívida não existe na aplicação.
    """
    r = client.post("/api/configuracao/inicializar", params={"perfil": perfil})
    assert r.status_code == 200

    session.expire_all()
    prestacao = (
        session.query(Subcategoria)
        .join(Categoria)
        .filter(Categoria.nome == "Casa", Subcategoria.nome == "Prestação")
        .one()
    )
    assert prestacao.trata_patrimonio is False


def test_inicializar_cria_os_tipos_de_ativo_com_e_sem_unidades(client, session):
    """Os tipos iniciais e o `tem_unidades` de cada um, escritos à mão.

    Com unidades (FIFO): ETF, Ações, Crypto, Ouro, Obrigações e Certificados de
    Aforro, que são subscritos em unidades e podem ser resgatados em parte (antes
    estavam sem unidades). Sem unidades (bens): Veículo, Imóvel, Outro.
    """
    r = client.post("/api/configuracao/inicializar?com_categorias=false")
    assert r.status_code == 200

    session.expire_all()
    assert {t.nome: t.tem_unidades for t in session.query(TipoAtivo).all()} == {
        "ETF": True,
        "Ações": True,
        "Crypto": True,
        "Ouro": True,
        "Obrigações": True,
        "Certificados de Aforro": True,
        "Veículo": False,
        "Imóvel": False,
        "Outro": False,
    }


def test_inicializar_sem_categorias_apenas_inicializa(client, session):
    r = client.post("/api/configuracao/inicializar?com_categorias=false")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "mensagem": "Base de dados inicializada sem categorias"}
    session.expire_all()
    assert session.query(Categoria).count() == 0
    assert session.query(Subcategoria).count() == 0
    assert session.query(TipoAtivo).count() == SEED_TIPOS_ATIVO_COUNT
    assert session.query(Configuracao).first().inicializado is True


def test_inicializar_ja_inicializada_nao_faz_nada(client, session):
    session.add(Configuracao(inicializado=True))
    session.commit()
    r = client.post("/api/configuracao/inicializar")
    assert r.status_code == 200
    assert r.json() == {"ok": False, "mensagem": "Base de dados já inicializada"}
    session.expire_all()
    assert session.query(Categoria).count() == 0
    assert session.query(Subcategoria).count() == 0
    assert session.query(TipoAtivo).count() == 0
    assert session.query(Configuracao).count() == 1


def test_inicializar_com_dados_existentes_cria_so_o_que_falta(client, session):
    """Sem linha `Configuracao` mas com dados, o `/inicializar` completa-os.

    Antes da correcção, com uma categoria "Casa" e sem configuração, o pedido
    rebentava com `IntegrityError` (nome duplicado) e nada ficava inicializado.
    Agora `semear_dados_iniciais` cria só o que falta, pelo nome.

    Semente: categoria Casa com as subcategorias Renda (que está na lista) e
    Jardim (que não está); tipos de ativo ETF (na lista) e Arte (fora dela).

    Cálculo à mão, perfil completo (15 categorias, 53 subcategorias, 9 tipos):
      categorias:    Casa já existe -> criadas 14 -> total 15, Casa com o mesmo id
      subcategorias: a Casa da lista tem 9; Renda já existe -> criadas 8 na Casa;
                     as outras 14 categorias trazem 53 - 9 = 44 -> criadas 52;
                     total = 2 (Renda, Jardim) + 52 = 54; Casa fica com 10
      tipos:         ETF já existe -> criados 8 -> total 2 + 8 = 10
      configuração:  1 linha, inicializado = True
    """
    casa = Categoria(nome="Casa", tipo=TipoCategoria.despesa)
    session.add(casa)
    session.commit()
    session.add_all(
        [
            Subcategoria(nome="Renda", categoria_id=casa.id),
            Subcategoria(nome="Jardim", categoria_id=casa.id),
            TipoAtivo(nome="ETF", tem_unidades=True),
            TipoAtivo(nome="Arte", tem_unidades=False),
        ]
    )
    session.commit()
    casa_id = casa.id

    r = client.post("/api/configuracao/inicializar")

    assert r.status_code == 200
    assert r.json() == {"ok": True, "mensagem": "Categorias e subcategorias criadas com sucesso"}
    session.expire_all()
    assert session.query(Categoria).count() == 15
    assert session.query(Categoria).filter_by(nome="Casa").one().id == casa_id
    assert session.query(Subcategoria).count() == 54
    assert session.query(Subcategoria).filter_by(categoria_id=casa_id).count() == 10
    assert session.query(Subcategoria).filter_by(categoria_id=casa_id, nome="Renda").count() == 1
    assert session.query(TipoAtivo).count() == 10
    assert session.query(TipoAtivo).filter_by(nome="ETF").count() == 1
    assert session.query(Configuracao).count() == 1
    assert session.query(Configuracao).first().inicializado is True


# ---------------------------------------------------------------------------
# POST /tour-visto
# ---------------------------------------------------------------------------


def test_tour_visto_sem_configuracao_marca_inicializado_e_tour_visto(client, session):
    r = client.post("/api/configuracao/tour-visto")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    session.expire_all()
    config = session.query(Configuracao).first()
    assert config.inicializado is True
    assert config.tour_visto is True
    assert session.query(Configuracao).count() == 1


def test_tour_visto_com_configuracao_marca_apenas_tour_visto(client, session):
    session.add(Configuracao(inicializado=False, tour_visto=False))
    session.commit()
    r = client.post("/api/configuracao/tour-visto")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    session.expire_all()
    config = session.query(Configuracao).first()
    assert config.inicializado is False
    assert config.tour_visto is True
    assert session.query(Configuracao).count() == 1

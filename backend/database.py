import enum
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum as SAEnum,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


def _resolver_base_dir() -> str:
    """Pasta a partir da qual 'dados/' é resolvida.

    - PyInstaller: pasta do executável.
    - Dev: pasta do backend/.
    - Override: RASTREIO_DB_DIR (usado para instalações sem permissões de escrita,
      ex. C:\\Program Files ou /opt).
    """
    env = os.environ.get("RASTREIO_DB_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _resolver_base_dir()
PASTA_DADOS = os.path.join(BASE_DIR, "dados")
DB_PATH = os.path.join(PASTA_DADOS, "rastreio.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"


def garantir_pasta_dados() -> None:
    """Cria a pasta de dados. Idempotente.

    NÃO é chamado no import — o main.py chama-o no arranque, dentro de um
    try/except, para que um PermissionError produza uma mensagem útil em vez
    de um traceback cru (ver B4).
    """
    try:
        os.makedirs(PASTA_DADOS, exist_ok=True)
    except PermissionError as e:
        raise RuntimeError(
            f"Sem permissões para criar a pasta de dados em:\n  {PASTA_DADOS}\n\n"
            "Soluções:\n"
            "  1. Move a aplicação para uma pasta onde tenhas permissões de escrita\n"
            "     (ex.: Documentos).\n"
            "  2. Ou define a variável de ambiente RASTREIO_DB_DIR para uma pasta\n"
            "     com permissões de escrita, por exemplo:\n"
            "       set RASTREIO_DB_DIR=%LOCALAPPDATA%\\rastreio-db\n\n"
            f"Detalhe: {e}"
        ) from e
    except OSError as e:
        raise RuntimeError(
            f"Não foi possível preparar a pasta de dados em:\n  {PASTA_DADOS}\n\n"
            f"Confirma que o caminho é válido. Detalhe: {e}"
        ) from e


def anunciar_bd_ativa() -> None:
    """Imprime o caminho da BD. Chamado pelo main.py DEPOIS de
    garantir_pasta_dados(), para a mensagem só aparecer quando é verdade."""
    msg = f"✅ BD ativa em: {DB_PATH}"
    try:
        print(msg, flush=True)
    except AttributeError, OSError:
        try:
            print(msg, file=sys.stderr, flush=True)
        except Exception:
            pass


def ligar_chaves_estrangeiras(con, _registo) -> None:
    """O SQLite só aplica as chaves estrangeiras com esta pragma, e é por
    conexão. Sem `ON DELETE`, o SQLite recusa apagar um pai com filhos. Mas,
    numa `relationship` sem `cascade` de delete, o SQLAlchemy põe antes a chave
    dos filhos a NULL e o `DELETE` passa; por isso cada endpoint trata dos
    filhos antes."""
    con.execute("PRAGMA foreign_keys = ON")


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
event.listen(engine, "connect", ligar_chaves_estrangeiras)


class Base(DeclarativeBase):
    pass


# SessionLocal definido UMA vez (antes estava duplicado — a segunda
# declaração tornava a primeira inútil e é armadilha para quem mexer aqui).
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """Gerador de dependência FastAPI para sessões de base de dados."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Configuracao(Base):
    __tablename__ = "configuracao"

    id: Mapped[int] = mapped_column(primary_key=True)
    inicializado: Mapped[bool] = mapped_column(Boolean, default=False)
    tour_visto: Mapped[bool] = mapped_column(Boolean, default=False)


class TipoCategoria(enum.Enum):
    despesa = "despesa"
    receita = "receita"
    investimento = "investimento"
    transferencia = "transferencia"


class TipoAtivo(Base):
    __tablename__ = "tipos_ativo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tem_unidades: Mapped[bool] = mapped_column(Boolean, default=False)

    ativos: Mapped[List["Ativo"]] = relationship("Ativo", back_populates="tipo")


class TipoMovimento(enum.Enum):
    compra = "compra"
    venda = "venda"
    dividendo = "dividendo"


class TipoContabilizacao(enum.Enum):
    investimento = "investimento"
    patrimonio = "patrimonio"


class Conta(Base):
    __tablename__ = "contas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    saldo_referencia: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    transacoes: Mapped[List["Transacao"]] = relationship("Transacao", back_populates="conta")
    perfis_importacao: Mapped[List["PerfilImportacao"]] = relationship(
        "PerfilImportacao", back_populates="conta"
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tipo: Mapped[TipoCategoria] = mapped_column(SAEnum(TipoCategoria), nullable=False)
    # Tipagem forte para as relações
    subcategorias: Mapped[List["Subcategoria"]] = relationship(
        "Subcategoria", back_populates="categoria"
    )


class Subcategoria(Base):
    __tablename__ = "subcategorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    trata_patrimonio: Mapped[bool] = mapped_column(Boolean, default=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)

    categoria: Mapped["Categoria"] = relationship("Categoria", back_populates="subcategorias")
    transacoes: Mapped[List["Transacao"]] = relationship("Transacao", back_populates="subcategoria")


class Transacao(Base):
    __tablename__ = "transacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    saldo: Mapped[Optional[float]] = mapped_column(
        Float
    )  # Optional[] define automaticamente nullable=True
    notas: Mapped[Optional[str]] = mapped_column(String(500))

    categoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categorias.id"))
    subcategoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subcategorias.id"))

    conta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contas.id"))
    conta: Mapped[Optional["Conta"]] = relationship("Conta", back_populates="transacoes")

    categoria: Mapped[Optional["Categoria"]] = relationship("Categoria")
    subcategoria: Mapped[Optional["Subcategoria"]] = relationship(
        "Subcategoria", back_populates="transacoes"
    )


class RegraCategorizacao(Base):
    __tablename__ = "regras_categorizacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    palavra_chave: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    categoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categorias.id"))
    subcategoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subcategorias.id"))

    categoria: Mapped[Optional["Categoria"]] = relationship("Categoria")
    subcategoria: Mapped[Optional["Subcategoria"]] = relationship("Subcategoria")


class ModoValor(enum.Enum):
    coluna_unica = "coluna_unica"
    duas_colunas = "duas_colunas"


class TipoFicheiro(enum.Enum):
    xlsx = "xlsx"
    csv = "csv"


class PerfilImportacao(Base):
    __tablename__ = "perfis_importacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tipo_ficheiro: Mapped[TipoFicheiro] = mapped_column(
        SAEnum(TipoFicheiro), nullable=False, default=TipoFicheiro.xlsx
    )

    linha_inicio_dados: Mapped[int] = mapped_column(nullable=False)
    coluna_data: Mapped[int] = mapped_column(nullable=False)
    formato_data: Mapped[str] = mapped_column(String(50), nullable=False)

    coluna_descricao: Mapped[int] = mapped_column(nullable=False)

    modo_valor: Mapped[ModoValor] = mapped_column(SAEnum(ModoValor), nullable=False)
    coluna_valor: Mapped[Optional[int]] = mapped_column()
    coluna_debito: Mapped[Optional[int]] = mapped_column()
    coluna_credito: Mapped[Optional[int]] = mapped_column()

    separador_decimal: Mapped[str] = mapped_column(String(1), nullable=False, default=".")

    tem_saldo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    coluna_saldo: Mapped[Optional[int]] = mapped_column()
    coluna_fee: Mapped[Optional[int]] = mapped_column()
    conta_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contas.id"))
    conta: Mapped[Optional["Conta"]] = relationship("Conta", back_populates="perfis_importacao")


class Ativo(Base):
    __tablename__ = "ativos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo_id: Mapped[int] = mapped_column(ForeignKey("tipos_ativo.id"), nullable=False)
    simbolo: Mapped[Optional[str]] = mapped_column(String(20), unique=True)
    moeda: Mapped[str] = mapped_column(String(10), default="EUR")
    notas: Mapped[Optional[str]] = mapped_column(String(500))
    contabilizacao: Mapped[TipoContabilizacao] = mapped_column(
        SAEnum(TipoContabilizacao), nullable=False
    )

    tipo: Mapped["TipoAtivo"] = relationship("TipoAtivo", back_populates="ativos")
    movimentos: Mapped[List["MovimentoAtivo"]] = relationship(
        "MovimentoAtivo", back_populates="ativo"
    )
    precos: Mapped[List["PrecoAtivo"]] = relationship("PrecoAtivo", back_populates="ativo")


class MovimentoAtivo(Base):
    __tablename__ = "movimentos_ativo"

    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativos.id"), nullable=False)
    transacao_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transacoes.id"))
    tipo_movimento: Mapped[TipoMovimento] = mapped_column(SAEnum(TipoMovimento), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    quantidade: Mapped[Optional[float]] = mapped_column(Float)
    preco_unitario: Mapped[Optional[float]] = mapped_column(Float)
    comissao: Mapped[Optional[float]] = mapped_column(Float, default=0)
    valor_total: Mapped[float] = mapped_column(Float, nullable=False)
    notas: Mapped[Optional[str]] = mapped_column(String(500))

    ativo: Mapped["Ativo"] = relationship("Ativo", back_populates="movimentos")
    transacao: Mapped[Optional["Transacao"]] = relationship("Transacao")


class PrecoAtivo(Base):
    __tablename__ = "precos_ativo"

    id: Mapped[int] = mapped_column(primary_key=True)
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativos.id"), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    preco: Mapped[float] = mapped_column(Float, nullable=False)

    ativo: Mapped["Ativo"] = relationship("Ativo", back_populates="precos")

    __table_args__ = (UniqueConstraint("ativo_id", "data", name="uq_preco_ativo_data"),)


# Uma migração antiga renomeou `ativos` para `ativos_old` e depois apagou-a.
# No RENAME o SQLite reescreveu as chaves destas tabelas para `ativos_old`, e
# no DROP não as repôs. Uma BD dessa altura, ou um backup dela,
# ainda tem o schema assim.
TABELAS_COM_FK_PARA_ATIVOS_OLD = ("precos_ativo", "movimentos_ativo")


def reparar_fk_ativos(caminho: str = DB_PATH) -> list[str]:
    """Repõe `REFERENCES ativos` onde o schema aponta para `ativos_old`.

    Idempotente: se nenhuma tabela mencionar `ativos_old`, não escreve nada.
    Cada tabela é recriada com o seu próprio DDL, só com a referência mudada, e
    com os mesmos IDs e dados. Tudo numa transacção: se a cópia não for igual à
    original, nada fica feito. Devolve as tabelas reparadas.
    """
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        partidas = {
            nome: sql
            for nome, sql in con.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'")
            if sql and "ativos_old" in sql
        }
        if not partidas:
            return []
        inesperadas = partidas.keys() - set(TABELAS_COM_FK_PARA_ATIVOS_OLD)
        if inesperadas:
            raise RuntimeError(
                f"Referência a ativos_old em tabelas inesperadas: {sorted(inesperadas)}"
            )

        # Fora da transacção, porque lá dentro a pragma não muda. É o
        # procedimento da documentação do SQLite para alterar uma tabela: a
        # tabela antiga nunca é renomeada, só a nova, e nada aponta para ela.
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("BEGIN IMMEDIATE")
        try:
            reparadas = [n for n in TABELAS_COM_FK_PARA_ATIVOS_OLD if n in partidas]
            for nome in reparadas:
                _recriar_com_fk_para_ativos(con, nome, partidas[nome])
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
    finally:
        con.close()
    return reparadas


def _recriar_com_fk_para_ativos(con: sqlite3.Connection, nome: str, sql: str) -> None:
    nova = f"{nome}_new"
    sql_novo, n_nome = re.subn(rf'^CREATE TABLE\s+"?{nome}"?', f"CREATE TABLE {nova}", sql)
    sql_novo, n_ref = re.subn(r'REFERENCES\s+"?ativos_old"?', "REFERENCES ativos", sql_novo)
    if n_nome != 1 or n_ref != 1:
        raise RuntimeError(f"DDL inesperado em {nome}: {sql}")

    antes = con.execute(f"SELECT * FROM {nome} ORDER BY id").fetchall()
    con.execute(sql_novo)
    con.execute(f"INSERT INTO {nova} SELECT * FROM {nome}")
    con.execute(f"DROP TABLE {nome}")
    con.execute(f"ALTER TABLE {nova} RENAME TO {nome}")
    depois = con.execute(f"SELECT * FROM {nome} ORDER BY id").fetchall()
    if depois != antes:
        raise RuntimeError(f"A cópia de {nome} não é igual à original")


def remover_coluna_reembolso(caminho: str = DB_PATH) -> bool:
    """Apaga a coluna `transacoes.reembolso`, se ainda existir.

    A marca de reembolso foi retirada (achado 4.3): só tinha efeito nas
    receitas, e só nalguns ecrãs. A coluna era `NOT NULL` sem valor por
    omissão, por isso não pode ficar na BD sem o modelo a preencher.
    Idempotente: sem a coluna, não escreve nada. Devolve se a apagou.
    """
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        colunas = {linha[1] for linha in con.execute("PRAGMA table_info(transacoes)")}
        if "reembolso" not in colunas:
            return False
        con.execute("ALTER TABLE transacoes DROP COLUMN reembolso")
    finally:
        con.close()
    return True


# As migrações do schema, por ordem: a posição na lista é a versão a que cada
# uma leva a BD. A BD guarda em `PRAGMA user_version` a última que já levou, e
# no arranque e no restauro de um backup correm as que faltam. Uma BD nova é
# criada pelo modelo já com o schema final, e fica logo na última versão.
#
# Para mudar o schema: mudar o modelo e acrescentar aqui, no fim, a função que
# leva uma BD antiga ao mesmo estado. Recebe o caminho da BD, devolve se mudou
# alguma coisa, e tem de ser idempotente: se falhar depois de fazer o trabalho e
# antes de a versão subir, volta a correr. Uma tabela nova não precisa de
# migração, porque o `create_all` cria-a. Nunca se tira nem se troca a ordem de
# uma migração que já saiu: a versão das BDs existentes aponta para ela.
MIGRACOES = (
    ("chaves para ativos_old reparadas", reparar_fk_ativos),
    ("coluna transacoes.reembolso removida", remover_coluna_reembolso),
)


def _versao_schema(caminho: str) -> int:
    con = sqlite3.connect(caminho)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


def _marcar_versao_schema(caminho: str, versao: int) -> None:
    con = sqlite3.connect(caminho, autocommit=True)
    try:
        con.execute(f"PRAGMA user_version = {int(versao)}")
    finally:
        con.close()


def aplicar_migracoes(caminho: str = DB_PATH) -> list[str]:
    """Corre, por ordem, as migrações que a BD ainda não levou.

    A versão sobe a seguir a cada migração: se uma falhar, a BD fica na versão
    da anterior e as seguintes não correm. Uma BD de uma versão mais recente do
    que a lista (um backup de uma aplicação mais nova) não é tocada. Devolve as
    descrições das migrações que mudaram alguma coisa.
    """
    feitas = []
    versao = _versao_schema(caminho)
    for numero, (descricao, migracao) in enumerate(MIGRACOES, start=1):
        if numero <= versao:
            continue
        if migracao(caminho):
            feitas.append(descricao)
        _marcar_versao_schema(caminho, numero)
    return feitas


def colunas_em_falta(caminho: str = DB_PATH) -> list[str]:
    """As tabelas e as colunas do modelo que a BD em `caminho` não tem.

    Uma tabela em falta aparece como `tabela`, uma coluna como `tabela.coluna`.
    Tabelas e colunas a mais não contam. Só leitura: o ficheiro é aberto com
    `mode=ro` (URI), e um ficheiro que não é SQLite levanta `sqlite3.Error`.
    """
    con = sqlite3.connect(Path(caminho).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        linhas = con.execute(
            "SELECT m.name, p.name FROM sqlite_master AS m "
            "JOIN pragma_table_info(m.name) AS p WHERE m.type = 'table'"
        ).fetchall()
    finally:
        con.close()

    reais: dict[str, set[str]] = {}
    for nome_tabela, nome_coluna in linhas:
        reais.setdefault(nome_tabela, set()).add(nome_coluna)

    em_falta = []
    for tabela in Base.metadata.sorted_tables:
        if tabela.name not in reais:
            em_falta.append(tabela.name)
            continue
        em_falta += [
            f"{tabela.name}.{coluna.name}"
            for coluna in tabela.columns
            if coluna.name not in reais[tabela.name]
        ]
    return em_falta


def criar_tabelas():
    garantir_pasta_dados()
    with engine.connect() as con:
        nova = not con.exec_driver_sql("SELECT 1 FROM sqlite_master WHERE type = 'table'").first()
    Base.metadata.create_all(bind=engine)
    if nova:
        _marcar_versao_schema(DB_PATH, len(MIGRACOES))
    for descricao in aplicar_migracoes():
        print(f"Schema actualizado: {descricao}", flush=True)

    # Uma BD mais antiga do que as migrações conhecem abria sem erro e dava
    # erros 500 nas páginas que precisam do que lhe falta (achado 1.1)
    em_falta = colunas_em_falta()
    if em_falta:
        raise RuntimeError(
            "A base de dados é de uma versão anterior do Rastreio-DB que não se "
            "consegue actualizar automaticamente.\n"
            f"  {DB_PATH}\n"
            f"Falta: {', '.join(em_falta)}"
        )


if __name__ == "__main__":
    try:
        criar_tabelas()
    except RuntimeError as e:
        print(f"\n{e}\n", file=sys.stderr)
        sys.exit(2)
    print("Tabelas criadas com sucesso no novo estilo Mapped!")

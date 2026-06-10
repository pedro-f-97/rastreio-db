from datetime import date
from typing import List, Optional
from sqlalchemy import create_engine, String, Float, Date, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
import os
import sys
import enum

# Determina a pasta base conforme o contexto de execução
if getattr(sys, 'frozen', False):
    # A correr como executável PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Desenvolvimento normal
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# A BD fica numa pasta 'dados/' junto ao executável (ou junto ao backend/ em dev)
PASTA_DADOS = os.path.join(BASE_DIR, "dados")
os.makedirs(PASTA_DADOS, exist_ok=True)

DB_PATH = os.path.join(PASTA_DADOS, "rastreio.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"✅ BD ativa em: {DB_PATH}")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# Em 2.0, criamos uma classe que herda de DeclarativeBase
class Base(DeclarativeBase):
    pass

# Sessão para interagir com a base de dados
SessionLocal = sessionmaker(bind=engine)

class TipoCategoria(enum.Enum):
    despesa = "despesa"
    receita = "receita"
    investimento = "investimento"
    transferencia = "transferencia"

class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tipo: Mapped[TipoCategoria] = mapped_column(SAEnum(TipoCategoria), nullable=False)
    # Tipagem forte para as relações
    subcategorias: Mapped[List["Subcategoria"]] = relationship("Subcategoria", back_populates="categoria")


class Subcategoria(Base):
    __tablename__ = "subcategorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)

    categoria: Mapped["Categoria"] = relationship("Categoria", back_populates="subcategorias")
    transacoes: Mapped[List["Transacao"]] = relationship("Transacao", back_populates="subcategoria")


class Transacao(Base):
    __tablename__ = "transacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    saldo: Mapped[Optional[float]] = mapped_column(Float) # Optional[] define automaticamente nullable=True
    reembolso: Mapped[bool] = mapped_column(Boolean, default=False)
    notas: Mapped[Optional[str]] = mapped_column(String(500))
    
    categoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categorias.id"))
    subcategoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subcategorias.id"))

    categoria: Mapped[Optional["Categoria"]] = relationship("Categoria")
    subcategoria: Mapped[Optional["Subcategoria"]] = relationship("Subcategoria", back_populates="transacoes")


class RegraCategorizacao(Base):
    __tablename__ = "regras_categorizacao"

    id: Mapped[int] = mapped_column(primary_key=True)
    palavra_chave: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)
    subcategoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("subcategorias.id"))

    categoria: Mapped["Categoria"] = relationship("Categoria")
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
    tipo_ficheiro: Mapped[TipoFicheiro] = mapped_column(SAEnum(TipoFicheiro), nullable=False, default=TipoFicheiro.xlsx)

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

def criar_tabelas():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    criar_tabelas()
    print("Tabelas criadas com sucesso no novo estilo Mapped!")


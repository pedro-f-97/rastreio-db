from datetime import date
from typing import List, Optional
from sqlalchemy import create_engine, String, Float, Date, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

# Ligação à base de dados SQLite
DATABASE_URL = "sqlite:///./rastreio.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Em 2.0, criamos uma classe que herda de DeclarativeBase
class Base(DeclarativeBase):
    pass

# Sessão para interagir com a base de dados
SessionLocal = sessionmaker(bind=engine)

class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

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
    

def criar_tabelas():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    criar_tabelas()
    print("Tabelas criadas com sucesso no novo estilo Mapped!")
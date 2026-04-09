from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Ligação à base de dados SQLite
DATABASE_URL = "sqlite:///./rastreio.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Base para os modelos
Base = declarative_base()

# Sessão para interagir com a base de dados
SessionLocal = sessionmaker(bind=engine)

class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False, unique=True)

    subcategorias = relationship("Subcategoria", back_populates="categoria")


class Subcategoria(Base):
    __tablename__ = "subcategorias"

    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)

    categoria = relationship("Categoria", back_populates="subcategorias")
    transacoes = relationship("Transacao", back_populates="subcategoria")


class Transacao(Base):
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True)
    data = Column(Date, nullable=False)
    descricao = Column(String, nullable=False)
    valor = Column(Float, nullable=False)
    saldo = Column(Float)
    reembolso = Column(Boolean, default=False)
    notas = Column(String)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=True)
    subcategoria_id = Column(Integer, ForeignKey("subcategorias.id"), nullable=True)

    categoria = relationship("Categoria")
    subcategoria = relationship("Subcategoria", back_populates="transacoes")

class RegraCategorizacao(Base):
    __tablename__ = "regras_categorizacao"

    id = Column(Integer, primary_key=True)
    palavra_chave = Column(String, nullable=False, unique=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    subcategoria_id = Column(Integer, ForeignKey("subcategorias.id"), nullable=True)

    categoria = relationship("Categoria")
    subcategoria = relationship("Subcategoria")
    
def criar_tabelas():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    criar_tabelas()
    print("Tabelas criadas com sucesso!")
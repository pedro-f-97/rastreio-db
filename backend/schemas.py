from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date

# --- SCHEMAS DE CATEGORIA ---
class CategoriaBase(BaseModel):
    nome: str

class CategoriaCreate(CategoriaBase):
    pass

class Categoria(CategoriaBase):
    id: int
    # Ativa a leitura de modelos ORM (SQLAlchemy) no Pydantic V2
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE SUBCATEGORIA ---
class SubcategoriaBase(BaseModel):
    nome: str
    categoria_id: int

class SubcategoriaCreate(BaseModel):
    nome: str

class Subcategoria(SubcategoriaBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE TRANSAÇÃO ---
class TransacaoBase(BaseModel):
    data: date
    descricao: str
    valor: float
    saldo: Optional[float] = None
    reembolso: bool = False
    notas: Optional[str] = None
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None

class TransacaoUpdate(BaseModel):
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    reembolso: Optional[bool] = None
    notas: Optional[str] = None

class Transacao(TransacaoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE REGRAS ---
class RegraBase(BaseModel):
    palavra_chave: str
    categoria_id: int
    subcategoria_id: Optional[int] = None

class RegraCreate(RegraBase):
    pass

class Regra(RegraBase):
    id: int
    model_config = ConfigDict(from_attributes=True)